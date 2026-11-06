import unittest

from aedt_close_watcher import AedtCloseWatcher, WindowState


class AedtCloseWatcherTests(unittest.TestCase):
    def test_visible_to_hidden_transition_triggers_close_once(self):
        states = iter(
            [
                WindowState(False, False),
                WindowState(True, False),
                WindowState(True, False),
                WindowState(False, False),
                WindowState(False, False),
            ]
        )
        reasons = []
        watcher = AedtCloseWatcher(
            session_pid=lambda: 4321,
            window_state=lambda pid: next(states),
            on_close_intent=reasons.append,
        )

        for _ in range(5):
            watcher.poll_once()

        self.assertEqual(reasons, ["main_window_closed"])

    def test_busy_dialog_with_visible_main_window_is_not_a_close_request(self):
        """Regression guard for the long-call stability fix.

        A busy dialog while the main window is still on screen is the normal
        symptom of another AEDT client holding the session. It must never be
        read as a close request: doing so made the broker call
        QuitApplication() mid-operation. This replaces the previous behaviour,
        which triggered on the very first poll.
        """
        reasons = []
        watcher = AedtCloseWatcher(
            session_pid=lambda: 4321,
            window_state=lambda pid: WindowState(True, True),
            on_close_intent=reasons.append,
        )

        for _ in range(50):
            watcher.poll_once()

        self.assertEqual(reasons, [])

    def test_busy_dialog_without_main_window_requires_consecutive_polls(self):
        reasons = []
        watcher = AedtCloseWatcher(
            session_pid=lambda: 4321,
            window_state=lambda pid: WindowState(False, True),
            on_close_intent=reasons.append,
            busy_dialog_confirmations=5,
        )

        for _ in range(4):
            watcher.poll_once()
        self.assertEqual(reasons, [])

        watcher.poll_once()
        self.assertEqual(reasons, ["busy_dialog"])

    def test_busy_dialog_counter_resets_when_the_dialog_clears(self):
        states = iter(
            [WindowState(False, True)] * 3
            + [WindowState(False, False)]
            + [WindowState(False, True)] * 3
        )
        reasons = []
        watcher = AedtCloseWatcher(
            session_pid=lambda: 4321,
            window_state=lambda pid: next(states),
            on_close_intent=reasons.append,
            busy_dialog_confirmations=5,
        )

        for _ in range(7):
            watcher.poll_once()

        self.assertEqual(reasons, [])

    def test_missing_session_resets_visible_state(self):
        pids = iter([4321, None, 4321])
        states = iter([WindowState(True, False), WindowState(False, False)])
        reasons = []
        watcher = AedtCloseWatcher(
            session_pid=lambda: next(pids),
            window_state=lambda pid: next(states),
            on_close_intent=reasons.append,
        )

        watcher.poll_once()
        watcher.poll_once()
        watcher.poll_once()

        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
