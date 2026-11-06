import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aedt_launcher import AedtLaunchError, AedtLauncher, resolve_aedt_executable


class FakeProcess:
    def __init__(self, pid=4321, returncode=None):
        self.pid = pid
        self.returncode = returncode
        self.terminate_called = False
        self.kill_called = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_called = True

    def kill(self):
        self.kill_called = True


class FakeWorkerClient:
    def __init__(self, failures=0, reported_pid=4321, reported_port=50051):
        self.failures = failures
        self.reported_pid = reported_pid
        self.reported_port = reported_port
        self.calls = []
        self.releases = []

    def execute(self, target, command, arguments, timeout=None):
        self.calls.append((target, command, arguments, timeout))
        if len(self.calls) <= self.failures:
            raise RuntimeError("not ready")
        return {
            "connected": True,
            "aedt_version": "2026.1",
            "pid": self.reported_pid,
            "port": self.reported_port,
        }

    def release(self, target, timeout=None):
        self.releases.append((target, timeout))
        return {"released": True}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class AedtLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.install = Path(self.temp.name).resolve()
        self.executable = self.install / "ansysedt.exe"
        self.executable.write_bytes(b"fake")
        self.process = FakeProcess()
        self.commands = []
        self.clock = FakeClock()
        self.worker = FakeWorkerClient()

    def tearDown(self):
        self.temp.cleanup()

    def _launcher(self, **overrides):
        def process_factory(command, **kwargs):
            self.commands.append((command, kwargs))
            return self.process

        defaults = {
            "worker_client": self.worker,
            "process_factory": process_factory,
            "choose_free_port": lambda: 55000,
            "port_is_free": lambda port: True,
            "port_is_open": lambda port: True,
            "monotonic": self.clock.monotonic,
            "sleep": self.clock.sleep,
        }
        defaults.update(overrides)
        return AedtLauncher(**defaults)

    def test_launch_uses_visible_grpc_command_and_exact_port(self):
        result = self._launcher().launch(
            version="2026.1", port=50051, install_dir=self.install, timeout=5.0
        )

        self.assertEqual(self.commands[0][0], [str(self.executable), "-grpcsrv", "50051"])
        self.assertNotIn("-ng", self.commands[0][0])
        self.assertEqual(self.worker.calls[0][0].key, "pid:4321")
        self.assertEqual(result, {
            "pid": 4321,
            "port": 50051,
            "version": "2026.1",
            "connection_mode": "grpc",
        })

    def test_launch_refuses_unconfirmed_process_identity(self):
        self.worker = FakeWorkerClient(reported_pid=None)

        with self.assertRaisesRegex(AedtLaunchError, "does not match launched PID"):
            self._launcher().launch(version="2026.1", port=50051, install_dir=self.install, timeout=5.0)

    def test_zero_port_selects_free_port(self):
        self.worker.reported_port = 55000
        result = self._launcher().launch(port=0, install_dir=self.install)

        self.assertEqual(result["port"], 55000)
        self.assertEqual(self.commands[0][0][-1], "55000")

    def test_explicit_occupied_port_is_rejected_before_launch(self):
        launcher = self._launcher(port_is_free=lambda port: False)

        with self.assertRaisesRegex(AedtLaunchError, "already in use"):
            launcher.launch(port=50051, install_dir=self.install)

        self.assertEqual(self.commands, [])

    def test_invalid_timeout_is_rejected_before_launch(self):
        with self.assertRaisesRegex(AedtLaunchError, "timeout"):
            self._launcher().launch(port=50051, install_dir=self.install, timeout=0)

        self.assertEqual(self.commands, [])

    def test_readiness_waits_for_port_and_worker_ping(self):
        states = iter([False, False, True])
        launcher = self._launcher(port_is_open=lambda port: next(states, True))

        result = launcher.launch(port=50051, install_dir=self.install, timeout=5.0)

        self.assertEqual(result["pid"], 4321)
        self.assertEqual(len(self.worker.calls), 1)
        self.assertGreater(self.clock.now, 0)

    def test_timeout_never_terminates_aedt(self):
        launcher = self._launcher(port_is_open=lambda port: False)

        with self.assertRaisesRegex(AedtLaunchError, "timed out"):
            launcher.launch(port=50051, install_dir=self.install, timeout=1.0)

        self.assertFalse(self.process.terminate_called)
        self.assertFalse(self.process.kill_called)

    def test_failed_handshake_is_not_retried_or_released(self):
        self.worker = FakeWorkerClient(failures=100)
        launcher = self._launcher(port_is_open=lambda port: True)

        with self.assertRaisesRegex(AedtLaunchError, "single readiness handshake failed"):
            launcher.launch(
                version="2026.1",
                port=50051,
                install_dir=self.install,
                timeout=0.5,
            )

        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(self.worker.releases, [])
        self.assertFalse(self.process.terminate_called)

    def test_early_process_exit_is_reported_without_kill(self):
        self.process.returncode = 5

        with self.assertRaisesRegex(AedtLaunchError, "exited with code 5"):
            self._launcher().launch(port=50051, install_dir=self.install)

        self.assertFalse(self.process.kill_called)

    def test_resolve_executable_from_install_dir_or_environment(self):
        self.assertEqual(resolve_aedt_executable(self.install), self.executable)
        with patch.dict(os.environ, {"ANSYSEM_ROOT261": str(self.install)}, clear=False):
            self.assertEqual(resolve_aedt_executable(None), self.executable)

    def test_missing_executable_is_actionable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(AedtLaunchError, "AEDT_INSTALL_DIR"):
                resolve_aedt_executable(self.install / "missing")


if __name__ == "__main__":
    unittest.main()
