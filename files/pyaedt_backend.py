from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from collections.abc import Callable, Mapping
from typing import Any

from aedt_target import AedtTarget
from maxwell_capabilities import MAXWELL_COMMANDS, MaxwellCapabilities
from pyaedt_capabilities import (
    OFFICIAL_BACKEND_COMMANDS,
    CapabilityError,
    OfficialCapabilities,
)


class BackendCommandError(ValueError):
    pass


_DESKTOP_COMMANDS = {
    "ping",
    "project_info",
    "close_projects",
} | OFFICIAL_BACKEND_COMMANDS | MAXWELL_COMMANDS
_HFSS_COMMANDS = {
    "create_hfss_design",
    "start_analysis",
    "analysis_status",
    "build_wr90_waveguide",
}
_SOLUTION_TYPES = {
    "DrivenModal": "Modal",
    "DrivenTerminal": "Terminal",
    "Modal": "Modal",
    "Terminal": "Terminal",
    "SBR+": "SBR+",
    "Transient": "Transient",
    "Eigenmode": "Eigenmode",
}


_ATTACH_LOCK = threading.RLock()
_AUDITED_PYAEDT_VERSION = "1.9.0"


def _existing_target_owner(kwargs: Mapping[str, Any]) -> tuple[int, float]:
    """Prove the explicit local target exists without invoking a vendor client."""
    import psutil

    pid, port = kwargs.get("aedt_process_id"), kwargs.get("port")
    if kwargs.get("new_desktop") is not False or bool(pid) == bool(port):
        raise BackendCommandError("attach requires new_desktop=False and exactly one explicit PID or port")
    if kwargs.get("machine") not in (None, "", "localhost", "127.0.0.1", "::1"):
        raise BackendCommandError("this attach-only broker supports local AEDT targets only")
    if pid:
        if type(pid) is not int or pid <= 0:
            raise BackendCommandError("invalid explicit AEDT PID")
    else:
        if type(port) is not int or not 0 < port <= 65535:
            raise BackendCommandError("invalid explicit AEDT port")
        try:
            owners = set()
            for connection in psutil.net_connections(kind="tcp"):
                address = connection.laddr
                address_port = getattr(address, "port", None)
                if address_port is None and isinstance(address, tuple) and len(address) >= 2:
                    address_port = address[1]
                if str(connection.status).upper() == "LISTEN" and address_port == port:
                    if type(connection.pid) is not int or connection.pid <= 0:
                        raise BackendCommandError("listener owner is unknown; use a verified explicit AEDT PID")
                    owners.add(connection.pid)
            if len(owners) != 1:
                raise BackendCommandError(
                    f"cannot prove a unique AEDT listener on port {port}; inspect sessions and use an explicit PID"
                )
            pid = owners.pop()
        except BackendCommandError:
            raise
        except Exception as exc:
            raise BackendCommandError("cannot inspect listener ownership; use a verified explicit AEDT PID") from exc
    try:
        process = psutil.Process(pid)
        if process.name().lower() not in {"ansysedt.exe", "ansysedt"}:
            raise BackendCommandError(f"PID {pid} does not belong to AEDT")
        return pid, process.create_time()
    except BackendCommandError:
        raise
    except Exception as exc:
        raise BackendCommandError(f"cannot verify existing AEDT PID {pid}; no attach or launch was attempted") from exc


def _audited_desktop_module() -> Any:
    from importlib.metadata import version
    if version("pyaedt") != _AUDITED_PYAEDT_VERSION:
        raise BackendCommandError(
            f"attach-only protection was audited for PyAEDT {_AUDITED_PYAEDT_VERSION}; "
            "use that version or review the changed Desktop launch paths before enabling another version"
        )
    import ansys.aedt.core.desktop as desktop_module
    return desktop_module


def _pid_launch_hints(pid: int) -> tuple[int | None, bool]:
    """Read the verified process's command line, without treating it as readiness.

    Windows socket enumeration may omit an AEDT listener. The explicit PID and
    its -grpcsrv argument let us make one attach-only handshake; the native
    result must still report the same PID and port before this factory returns.
    """
    import psutil
    try:
        command_line = psutil.Process(pid).cmdline()
    except Exception:
        return None, False
    if not isinstance(command_line, (tuple, list)):
        return None, False
    non_graphical = any(isinstance(value,str) and value.lower() == "-ng" for value in command_line)
    for index, argument in enumerate(command_line[:-1]):
        if isinstance(argument,str) and argument.lower() == "-grpcsrv":
            value = command_line[index+1]
            if isinstance(value,str) and value.isascii() and value.isdecimal() and 0 < int(value) <= 65535:
                return int(value), non_graphical
    return None, non_graphical


@contextmanager
def _attach_only_desktop(module: Any, kwargs: Mapping[str, Any], *,
                         verified_owner: tuple[int, float] | None = None,
                         grpc_port_hint: int | None = None):
    """Block the audited vendor fallback paths for this one Desktop constructor.

    PyAEDT 1.9 can set new_desktop=True when its own session discovery misses a
    port. Do not let a health check spawn AEDT. Restore methods on every exit;
    the broker serializes calls, and this process-local lock covers this patch.
    Arbitrary run_python_code calls are outside this narrow protection.
    """
    cls = module.Desktop
    names = ("_validate_port", "_Desktop__initialize", "_Desktop__dispatch_win32", "_Desktop__run_student", "check_starting_mode")
    if not callable(getattr(module, "launch_aedt", None)) or any(not callable(getattr(cls, name, None)) for name in names):
        raise BackendCommandError("PyAEDT Desktop layout differs from the audited attach-only implementation")
    old = {name: getattr(cls, name) for name in names}
    old_launch = module.launch_aedt

    def refuse_launch(*args: Any, **options: Any):
        raise BackendCommandError("PyAEDT attempted a fallback launch; attach-only protection refused it")

    def check_starting_mode(desktop: Any):
        if grpc_port_hint is not None:
            if desktop.new_desktop:
                refuse_launch()
            # Avoid a second vendor process/socket discovery. Its false
            # negatives can incorrectly select COM for an existing -ng server.
            desktop.port = grpc_port_hint
            desktop.is_grpc_api = True
            desktop._Desktop__starting_mode = "grpc"
            return
        return old["check_starting_mode"](desktop)

    def validate_port(desktop: Any):
        if desktop.new_desktop or not desktop.port:
            raise BackendCommandError("PyAEDT attempted to allocate a desktop or change the explicit attach target")
        if kwargs.get("port") and desktop.port != kwargs["port"]:
            raise BackendCommandError("PyAEDT changed the requested gRPC port")
        if grpc_port_hint is not None and desktop.port != grpc_port_hint:
            raise BackendCommandError("PyAEDT changed the verified PID's gRPC port hint")
        # Bypass vendor all_active_sessions(), whose false negatives otherwise
        # switch the constructor into launch mode. Socket ownership was proved.
        if verified_owner is not None:
            actual_owner = _existing_target_owner({"new_desktop": False, "aedt_process_id": verified_owner[0]})
            if actual_owner != verified_owner:
                raise BackendCommandError("AEDT process identity changed before the attach handshake")
        else:
            _existing_target_owner({"new_desktop": False, "port": desktop.port})
        return desktop.port

    def initialize(desktop: Any, new_desktop_required: bool | None = None):
        if desktop.new_desktop or new_desktop_required:
            refuse_launch()
        if not desktop.is_grpc_api:
            # __init_dotnet subsequently binds the ROT moniker for the exact PID.
            # Load COM utilities but skip CreateObject(version), which can create
            # an application if no registered active object remains.
            if not kwargs.get("aedt_process_id"):
                raise BackendCommandError("COM attach requires an explicit verified PID")
            from ansys.aedt.core.internal.clr_module import _clr
            if _clr is None:
                raise BackendCommandError("COM attach requires ansys-pythonnet; install it or use a verified gRPC port")
            _clr.AddReference("Ansys.Ansoft.CoreCOMScripting")
            com = __import__("Ansys.Ansoft.CoreCOMScripting")
            desktop.COMUtil = com.Ansoft.CoreCOMScripting.Util.COMUtil
            return None
        return old["_Desktop__initialize"](desktop, new_desktop_required=False)

    try:
        module.launch_aedt = refuse_launch
        cls._validate_port = validate_port
        cls.check_starting_mode = check_starting_mode
        cls._Desktop__initialize = initialize
        cls._Desktop__dispatch_win32 = refuse_launch
        cls._Desktop__run_student = refuse_launch
        yield
    finally:
        module.launch_aedt = old_launch
        for name, method in old.items():
            setattr(cls, name, method)


def _default_desktop_factory(**kwargs: Any) -> Any:
    # Environment variables silently override explicit targets in PyAEDT.
    for name in ("PYAEDT_PROCESS_ID", "PYAEDT_DESKTOP_PORT"):
        if os.environ.get(name) not in (None, "", "0"):
            raise BackendCommandError(f"unset {name}; this broker requires its explicit PID/port to remain authoritative")
    for name in ("PYAEDT_DOC_GENERATION", "PYAEDT_NON_GRAPHICAL"):
        if os.environ.get(name, "").lower() in ("true", "1", "t"):
            raise BackendCommandError(f"unset {name} before using the attach-only broker")
    configured_version = os.environ.get("PYAEDT_DESKTOP_VERSION")
    if configured_version and configured_version != kwargs.get("version"):
        raise BackendCommandError("PYAEDT_DESKTOP_VERSION conflicts with the explicit AEDT version")
    with _ATTACH_LOCK:
        expected_pid, expected_started = _existing_target_owner(kwargs)
        configured_port, actual_non_graphical = _pid_launch_hints(expected_pid)
        expected_port = kwargs.get("port") or configured_port
        if kwargs.get("port") and configured_port is not None and kwargs["port"] != configured_port:
            raise BackendCommandError("requested gRPC port differs from the verified process's launch argument")
        vendor_kwargs = dict(kwargs)
        if configured_port is not None:
            vendor_kwargs["non_graphical"] = actual_non_graphical
        module = _audited_desktop_module()
        settings = module.settings
        if settings.remote_rpc_session or settings.use_lsf_scheduler:
            raise BackendCommandError("remote/LSF settings are incompatible with this local attach-only broker")
        with _attach_only_desktop(module, kwargs, verified_owner=(expected_pid, expected_started), grpc_port_hint=expected_port):
            desktop = module.Desktop(**vendor_kwargs)
        if getattr(desktop, "aedt_process_id", None) != expected_pid:
            raise BackendCommandError("PyAEDT returned a different AEDT PID; no project operation was performed")
        if expected_port is not None and getattr(desktop, "port", None) != expected_port:
            raise BackendCommandError("PyAEDT returned a different AEDT port; no project operation was performed")
        if kwargs.get("version") and str(getattr(desktop, "aedt_version_id", "")) != kwargs["version"]:
            raise BackendCommandError("PyAEDT returned a different AEDT version; no project operation was performed")
        actual_pid, actual_started = _existing_target_owner({"new_desktop": False, "aedt_process_id": expected_pid})
        if (actual_pid, actual_started) != (expected_pid, expected_started):
            raise BackendCommandError("AEDT process identity changed during attach; no project operation was performed")
        return desktop


def _default_hfss_factory(**kwargs: Any) -> Any:
    from ansys.aedt.core import Hfss

    return Hfss(**kwargs)


def _default_wr90_builder(app: Any, output_dir: str, solve: bool) -> dict[str, Any]:
    from wr90_case import build_wr90_case

    return build_wr90_case(app, output_dir, solve)


def _target_dict(target: AedtTarget) -> dict[str, Any]:
    return {"kind": target.kind, "value": target.value}


def _required_text(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise BackendCommandError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(arguments: Mapping[str, Any], name: str, default: str = "") -> str:
    value = arguments.get(name, default)
    if not isinstance(value, str):
        raise BackendCommandError(f"{name} must be a string")
    return value.strip()


def _read_value(obj: Any, name: str, *args: Any) -> Any:
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _object_name(obj: Any) -> str | None:
    if obj is None:
        return None
    get_name = getattr(obj, "GetName", None)
    if callable(get_name):
        return str(get_name())
    name = getattr(obj, "name", None)
    return str(name) if name is not None else None


def _release(handle: Any) -> bool:
    desktop = getattr(handle, "desktop_class", handle)
    return bool(desktop.release_desktop(close_projects=False, close_on_exit=False))


def _active_design(desktop: Any, project: Any) -> Any:
    if project is None:
        return None
    project_name = _object_name(project)
    try:
        designs = list(_read_value(desktop, "design_list", project_name))
    except AttributeError:
        designs = None
    if designs == []:
        return None
    return desktop.active_design(project)


class PyAedtBackend:
    def __init__(
        self,
        *,
        desktop_factory: Callable[..., Any] | None = None,
        hfss_factory: Callable[..., Any] | None = None,
        wr90_builder: Callable[[Any, str, bool], dict[str, Any]] | None = None,
        official_capabilities: OfficialCapabilities | None = None,
        version: str | None = None,
    ) -> None:
        self._desktop_factory = desktop_factory or _default_desktop_factory
        self._hfss_factory = hfss_factory or _default_hfss_factory
        self._wr90_builder = wr90_builder or _default_wr90_builder
        self._official = official_capabilities or OfficialCapabilities()
        self._maxwell = MaxwellCapabilities(app_resolver=self._official._resolve_app)
        self._version = version or os.environ.get("AEDT_VERSION", "2026.1")
        self._desktop: Any = None
        self._bound_target: AedtTarget | None = None
        self._apps: dict[tuple[str, str, str | None], Any] = {}
        self._lock = threading.RLock()

    def execute(
        self,
        target: AedtTarget,
        command: str,
        arguments: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        with self._lock:
            return self._execute(target, command, arguments)

    def _execute(
        self,
        target: AedtTarget,
        command: str,
        arguments: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if command not in _DESKTOP_COMMANDS | _HFSS_COMMANDS:
            raise BackendCommandError(f"unsupported command: {command}")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, Mapping):
            raise BackendCommandError("arguments must be an object")

        if command in MAXWELL_COMMANDS:
            desktop = self._desktop_for(target)
            try:
                return self._maxwell.execute(
                    command, desktop=desktop, target=target, arguments=arguments,
                )
            except CapabilityError as exc:
                raise BackendCommandError(str(exc)) from exc
        if command in OFFICIAL_BACKEND_COMMANDS:
            desktop = self._desktop_for(target)
            try:
                result = self._official.execute(
                    command,
                    desktop=desktop,
                    target=target,
                    arguments=arguments,
                    connection_kwargs=self._connection_kwargs(
                        self._bound_target or target
                    ),
                )
            except CapabilityError as exc:
                raise BackendCommandError(str(exc)) from exc
            if command == "disconnect_from_aedt":
                self._apps.clear()
                self._desktop = None
                self._bound_target = None
            return result
        if command in _DESKTOP_COMMANDS:
            result = self._execute_desktop(target, command, arguments)
            if command == "close_projects":
                self._official.clear_local_state()
            return result
        return self._execute_hfss(target, command, arguments)

    def release(self) -> bool:
        with self._lock:
            if self._desktop is None:
                return False
            desktop = self._desktop
            self._apps.clear()
            self._official.clear_local_state()
            self._desktop = None
            self._bound_target = None
            return _release(desktop)

    @property
    def session_pid(self) -> int | None:
        with self._lock:
            if self._desktop is None:
                return None
            pid = getattr(self._desktop, "aedt_process_id", None)
            return pid if type(pid) is int and pid > 0 else None

    def close_for_user_request(self) -> bool:
        with self._lock:
            if self._desktop is None:
                return False
            desktop = self._desktop
            self._apps.clear()
            self._official.clear_local_state()
            self._desktop = None
            self._bound_target = None
            desktop.odesktop.QuitApplication()
            return True

    def _desktop_for(self, target: AedtTarget) -> Any:
        if self._desktop is None:
            self._desktop = self._desktop_factory(**self._connection_kwargs(target))
            self._bound_target = target
            return self._desktop

        if not self._target_matches(target):
            raise BackendCommandError(
                f"broker is bound to {self._bound_target.key}; requested {target.key}"
            )
        return self._desktop

    def _target_matches(self, target: AedtTarget) -> bool:
        if target == self._bound_target:
            return True
        if target.kind == "pid":
            return getattr(self._desktop, "aedt_process_id", None) == target.value
        return getattr(self._desktop, "port", None) == target.value

    def _connection_kwargs(self, target: AedtTarget) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "version": self._version,
            "non_graphical": False,
            "new_desktop": False,
            "close_on_exit": False,
        }
        if target.kind == "pid":
            kwargs["aedt_process_id"] = target.value
        else:
            kwargs.update({"machine": "localhost", "port": target.value})
        return kwargs

    def _execute_desktop(
        self,
        target: AedtTarget,
        command: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        desktop = self._desktop_for(target)
        if command == "ping":
            return self._ping(desktop, target)
        if command == "project_info":
            return self._project_info(desktop, target)
        if command == "close_projects":
            return self._close_projects(desktop, target, arguments)
        return self._save_project(desktop, target, arguments)

    def _execute_hfss(
        self,
        target: AedtTarget,
        command: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        if command == "build_wr90_waveguide":
            project_name = _optional_text(
                arguments, "project_name", "Classic_WR90_Waveguide"
            )
            design_name = _optional_text(arguments, "design_name", "WR90_TE10")
            output_dir = _required_text(arguments, "output_dir")
            solve = arguments.get("solve", True)
            if not isinstance(solve, bool):
                raise BackendCommandError("solve must be a boolean")
        else:
            project_name = _required_text(arguments, "project_name")
            design_name = _required_text(arguments, "design_name")
        self._desktop_for(target)
        kwargs = self._connection_kwargs(self._bound_target or target)
        kwargs.update({"project": project_name, "design": design_name})

        if command in {"create_hfss_design", "build_wr90_waveguide"}:
            requested = _optional_text(arguments, "solution_type", "DrivenModal")
            try:
                kwargs["solution_type"] = _SOLUTION_TYPES[requested]
            except KeyError as exc:
                raise BackendCommandError(
                    f"unsupported HFSS solution_type: {requested}"
                ) from exc
        elif command == "start_analysis":
            kwargs["setup"] = _required_text(arguments, "setup_name")

        app_key = (project_name, design_name, kwargs.get("solution_type"))
        app = self._apps.get(app_key)
        if app is None:
            app = self._hfss_factory(**kwargs)
            self._apps[app_key] = app
        if command == "build_wr90_waveguide":
            result = self._wr90_builder(app, output_dir, solve)
            return {"target": _target_dict(target), **result}
        if command == "create_hfss_design":
            return {
                "target": _target_dict(target),
                "project_name": str(getattr(app, "project_name", project_name)),
                "design_name": str(getattr(app, "design_name", design_name)),
                "solution_type": str(
                    getattr(app, "solution_type", kwargs["solution_type"])
                ),
            }
        if command == "start_analysis":
            blocking = arguments.get("blocking", False)
            if not isinstance(blocking, bool):
                raise BackendCommandError("blocking must be a boolean")
            setup_name = kwargs["setup"]
            started = bool(app.analyze_setup(name=setup_name, blocking=blocking))
            return {
                "target": _target_dict(target),
                "project_name": project_name,
                "design_name": design_name,
                "setup_name": setup_name,
                "blocking": blocking,
                "started": started,
                "solver_completion_confirmed": False,
                "convergence_confirmed": False,
                "completion_evidence_required": "Inspect the native profile and convergence for this exact submission; API success is not completion.",
            }

        running = bool(_read_value(app, "are_there_simulations_running"))
        setups = list(app.get_setups())
        return {
            "target": _target_dict(target),
            "project_name": project_name,
            "design_name": design_name,
            "running": running,
            "setups": [str(item) for item in setups],
            "solver_completion_confirmed": False,
            "convergence_confirmed": False,
            "activity_scope": "desktop",
            "completion_evidence_required": "Idle state and existing results do not establish completion of the latest solve.",
        }

    def _ping(self, desktop: Any, target: AedtTarget) -> dict[str, Any]:
        project = desktop.active_project()
        design = _active_design(desktop, project)
        return {
            "connected": True,
            "target": _target_dict(target),
            "aedt_version": str(getattr(desktop, "aedt_version_id", self._version)),
            "pid": getattr(desktop, "aedt_process_id", None),
            "port": getattr(desktop, "port", None),
            "active_project": _object_name(project),
            "active_design": _object_name(design),
        }

    def _project_info(self, desktop: Any, target: AedtTarget) -> dict[str, Any]:
        projects = list(_read_value(desktop, "project_list"))
        project = desktop.active_project()
        design = _active_design(desktop, project)
        project_name = _object_name(project)
        design_name = _object_name(design)
        design_type = None
        if project_name and design_name:
            design_type = desktop.design_type(project_name, design_name)
        return {
            "target": _target_dict(target),
            "projects": [str(item) for item in projects],
            "active_project": project_name,
            "active_design": design_name,
            "design_type": str(design_type) if design_type is not None else None,
        }

    def _save_project(
        self,
        desktop: Any,
        target: AedtTarget,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        project = desktop.active_project()
        project_name = _object_name(project)
        if not project_name:
            raise BackendCommandError("AEDT has no active project to save")
        path = _optional_text(arguments, "path")
        saved = bool(desktop.save_project(project_name, path or None))
        return {
            "target": _target_dict(target),
            "project_name": project_name,
            "path": path or None,
            "saved": saved,
        }

    def _close_projects(
        self,
        desktop: Any,
        target: AedtTarget,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        project_names = arguments.get("project_names")
        if not isinstance(project_names, list) or not project_names:
            raise BackendCommandError("project_names must be a non-empty list")
        if any(not isinstance(name, str) or not name.strip() for name in project_names):
            raise BackendCommandError(
                "project_names must contain only non-empty strings"
            )
        save = arguments.get("save", False)
        if not isinstance(save, bool):
            raise BackendCommandError("save must be a boolean")

        available = [str(item) for item in _read_value(desktop, "project_list")]
        closed = []
        not_found = []
        for raw_name in project_names:
            name = raw_name.strip()
            if name not in available:
                not_found.append(name)
                continue
            if save:
                desktop.save_project(name)
            desktop.odesktop.CloseProject(name)
            available.remove(name)
            closed.append(name)
        self._apps = {
            key: app for key, app in self._apps.items() if key[0] not in closed
        }
        return {
            "target": _target_dict(target),
            "closed": closed,
            "not_found": not_found,
            "remaining": [str(item) for item in _read_value(desktop, "project_list")],
            "saved_before_close": save,
        }
