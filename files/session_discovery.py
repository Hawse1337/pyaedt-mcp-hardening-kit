from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
import re
from typing import Any

from aedt_target import AedtTarget
from worker_client import WorkerClient


_AEDT_PROCESS_NAME = "ansysedt.exe"
_VERSION_PATTERN = re.compile(r"[\\/]v(?P<code>\d{3})[\\/]", re.IGNORECASE)


def _default_process_iter(attrs: list[str]) -> Iterable[Any]:
    import psutil

    return psutil.process_iter(attrs=attrs, ad_value=None)


def _default_net_connections(kind: str) -> list[Any]:
    import psutil

    return psutil.net_connections(kind=kind)


def _version_from_path(executable: str | None) -> str | None:
    if not executable:
        return None
    match = _VERSION_PATTERN.search(executable)
    if not match:
        return None
    code = match.group("code")
    return f"20{code[:2]}.{int(code[2])}"


def _started_at(timestamp: Any) -> str | None:
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        return None
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _connection_address(connection: Any) -> tuple[str | None, int | None]:
    address = getattr(connection, "laddr", None)
    if not address:
        return None, None
    ip = getattr(address, "ip", None)
    port = getattr(address, "port", None)
    if ip is None and isinstance(address, tuple) and len(address) >= 2:
        ip, port = address[0], address[1]
    return str(ip) if ip is not None else None, port if isinstance(port, int) else None


def _configured_grpc_port(command_line: Any) -> int | None:
    """Read a launch argument as a hint, never as proof that a server is ready."""
    if not isinstance(command_line, (tuple, list)):
        return None
    for index, argument in enumerate(command_line[:-1]):
        if isinstance(argument, str) and argument.lower() == "-grpcsrv":
            value = command_line[index + 1]
            if isinstance(value, str) and value.isascii() and value.isdecimal():
                port = int(value)
                if 0 < port <= 65535:
                    return port
    return None


class SessionDiscovery:
    def __init__(
        self,
        *,
        process_iter: Callable[[list[str]], Iterable[Any]] | None = None,
        net_connections: Callable[[str], list[Any]] | None = None,
        worker_client: WorkerClient | None = None,
    ) -> None:
        self._process_iter = process_iter or _default_process_iter
        self._net_connections = net_connections or _default_net_connections
        self._worker_client = worker_client or WorkerClient()

    def list_sessions(self) -> list[dict[str, Any]]:
        process_records: dict[int, dict[str, Any]] = {}
        attrs = ["pid", "name", "exe", "create_time", "cmdline"]
        try:
            processes = self._process_iter(attrs)
            for process in processes:
                try:
                    info = process.info
                except Exception:
                    continue
                pid = info.get("pid") if isinstance(info, dict) else None
                name = info.get("name") if isinstance(info, dict) else None
                if type(pid) is not int or pid <= 0 or not isinstance(name, str):
                    continue
                if name.lower() != _AEDT_PROCESS_NAME:
                    continue
                executable = info.get("exe")
                process_records[pid] = {
                    "pid": pid,
                    "version": _version_from_path(executable),
                    "executable": executable if isinstance(executable, str) else None,
                    "started_at": _started_at(info.get("create_time")),
                    "listening_ports": [],
                }
                configured_port = _configured_grpc_port(info.get("cmdline"))
                if configured_port is not None:
                    process_records[pid]["configured_grpc_port"] = configured_port
        except Exception:
            return []

        if not process_records:
            return []

        try:
            connections = self._net_connections("tcp")
        except Exception:
            connections = []
        for connection in connections:
            pid = getattr(connection, "pid", None)
            if pid not in process_records or str(getattr(connection, "status", "")).upper() != "LISTEN":
                continue
            _, port = _connection_address(connection)
            # A listener owned by this PID may bind to a local LAN address,
            # not only loopback/wildcard. An empty list is not proof of absence
            # when psutil cannot enumerate sockets on a particular machine.
            if type(port) is not int or not 0 < port <= 65535:
                continue
            process_records[pid]["listening_ports"].append(port)

        for record in process_records.values():
            record["listening_ports"] = sorted(set(record["listening_ports"]))
        return [process_records[pid] for pid in sorted(process_records)]

    def probe_session(
        self,
        *,
        pid: int | None = None,
        port: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        target = AedtTarget.from_values(pid=pid, port=port)
        result = self._worker_client.execute(
            target,
            "ping",
            {},
            timeout=timeout,
        )
        if not isinstance(result, dict):
            raise RuntimeError("AEDT ping worker returned a non-object result")
        return result
