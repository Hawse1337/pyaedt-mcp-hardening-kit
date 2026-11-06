from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import threading
from typing import Callable


BUSY_DIALOG_TEXT = "being used by another application, script or extension wizard"

# How many consecutive polls (at ``poll_interval``, 0.2 s by default) a busy
# dialog must persist WITH the main window already gone before it counts as a
# user close request.
#
# Why the qualifier matters: the same dialog also appears whenever a *second*
# client attaches to the same AEDT while the first still holds it -- exactly what
# happens after a tool-call timeout kills the broker and the next call starts a
# fresh one. Treating that as "the user wants to close" used to make the broker
# call AEDT QuitApplication() in the middle of an operation, which is the most
# destructive step in the long-call -> gRPC-instability chain.
DEFAULT_BUSY_DIALOG_CONFIRMATIONS = 5


@dataclass(frozen=True)
class WindowState:
    main_visible: bool
    busy_dialog: bool


def get_aedt_window_state(pid: int) -> WindowState:
    if os.name != "nt":
        return WindowState(False, False)

    user32 = ctypes.windll.user32
    main_visible = False
    busy_dialog = False
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def window_text(hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    @callback_type
    def child_callback(hwnd, _):
        nonlocal busy_dialog
        if BUSY_DIALOG_TEXT in window_text(hwnd):
            busy_dialog = True
        return True

    @callback_type
    def top_callback(hwnd, _):
        nonlocal main_visible, busy_dialog
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        text = window_text(hwnd)
        if BUSY_DIALOG_TEXT in text:
            busy_dialog = True
        if user32.IsWindowVisible(hwnd) and "Electronics Desktop" in text:
            main_visible = True
        user32.EnumChildWindows(hwnd, child_callback, 0)
        return True

    user32.EnumWindows(top_callback, 0)
    return WindowState(main_visible, busy_dialog)


class AedtCloseWatcher:
    def __init__(
        self,
        *,
        session_pid: Callable[[], int | None],
        on_close_intent: Callable[[str], None],
        window_state: Callable[[int], WindowState] = get_aedt_window_state,
        poll_interval: float = 0.2,
        busy_dialog_confirmations: int = DEFAULT_BUSY_DIALOG_CONFIRMATIONS,
    ) -> None:
        self._session_pid = session_pid
        self._on_close_intent = on_close_intent
        self._window_state = window_state
        self._poll_interval = poll_interval
        self._busy_dialog_confirmations = max(1, int(busy_dialog_confirmations))
        self._busy_dialog_polls = 0
        self._seen_pid: int | None = None
        self._seen_main_window = False
        self._triggered = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _reset(self) -> None:
        self._seen_pid = None
        self._seen_main_window = False
        self._busy_dialog_polls = 0

    def poll_once(self) -> None:
        if self._triggered:
            return
        pid = self._session_pid()
        if pid is None:
            self._reset()
            return
        if pid != self._seen_pid:
            self._reset()
            self._seen_pid = pid

        state = self._window_state(pid)
        if state.main_visible:
            self._seen_main_window = True

        # A busy dialog WITH the main window still up is the normal symptom of
        # another AEDT client holding the session. It is NOT a close request:
        # acting on it killed AEDT in the middle of long operations. Only a
        # dialog that outlives the main window AND keeps persisting counts as a
        # user-initiated close.
        if state.busy_dialog and not state.main_visible:
            self._busy_dialog_polls += 1
            if self._busy_dialog_polls >= self._busy_dialog_confirmations:
                self._trigger("busy_dialog")
            return

        self._busy_dialog_polls = 0
        if not state.main_visible and self._seen_main_window:
            self._trigger("main_window_closed")

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="aedt-close-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.wait(self._poll_interval):
            try:
                self.poll_once()
            except Exception:
                continue

    def _trigger(self, reason: str) -> None:
        self._triggered = True
        self._on_close_intent(reason)
