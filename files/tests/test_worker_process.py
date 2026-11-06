import asyncio
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from aedt_target import AedtTarget
from pyaedt_worker import (
    exit_without_pyaedt_cleanup,
    handle_close_intent,
    run_request_line,
    run_stream,
)
from worker_client import (
    WorkerClient,
    WorkerProcessError,
    WorkerProtocolOutputError,
    WorkerRemoteError,
    WorkerTimeoutError,
    WorkerRecoveredError,
)
from worker_protocol import WorkerRequest, WorkerResponse


class FakeBackend:
    def __init__(self, result=None, error=None):
        self.result = result or {"connected": True}
        self.error = error
        self.calls = []
        self.release_calls = 0
        self.close_calls = 0
        self.session_pid = 4321

    def execute(self, target, command, arguments):
        self.calls.append((target, command, arguments))
        if self.error:
            raise self.error
        return self.result

    def release(self):
        self.release_calls += 1
        return True

    def close_for_user_request(self):
        self.close_calls += 1
        return True


class WorkerEntryPointTests(unittest.TestCase):
    def test_close_intent_gracefully_closes_aedt_before_worker_exit(self):
        events = []

        class OrderedBackend(FakeBackend):
            def close_for_user_request(self):
                events.append("close")
                return True

        handle_close_intent(
            OrderedBackend(),
            "main_window_closed",
            exit_fn=lambda code: events.append(f"exit:{code}"),
        )

        self.assertEqual(events, ["close", "exit:0"])

    def test_stream_reuses_backend_until_explicit_release(self):
        target = AedtTarget("port", 50051)
        first = WorkerRequest.create("ping", target, {}, 5.0)
        second = WorkerRequest.create("project_info", target, {}, 5.0)
        release = WorkerRequest.create("release_connection", target, {}, 5.0)
        backend = FakeBackend()
        output = StringIO()

        exit_code = run_stream(
            StringIO("\n".join((first.to_json(), second.to_json(), release.to_json()))),
            output,
            backend_factory=lambda: backend,
        )

        responses = [WorkerResponse.from_json(line) for line in output.getvalue().splitlines()]
        self.assertEqual(exit_code, 0)
        self.assertEqual([call[1] for call in backend.calls], ["ping", "project_info"])
        self.assertEqual(backend.release_calls, 1)
        self.assertTrue(responses[-1].result["released"])

    def test_stream_releases_backend_on_stdin_eof(self):
        request = WorkerRequest.create("ping", AedtTarget("pid", 1234), {}, 5.0)
        backend = FakeBackend()

        run_stream(StringIO(request.to_json()), StringIO(), backend_factory=lambda: backend)

        self.assertEqual(backend.release_calls, 1)

    def test_process_exit_bypasses_pyaedt_cleanup_handlers(self):
        exit_codes = []

        exit_without_pyaedt_cleanup(7, exit_fn=exit_codes.append)

        self.assertEqual(exit_codes, [7])

    def test_valid_request_returns_success(self):
        request = WorkerRequest.create(
            "ping", AedtTarget("port", 50051), {}, 5.0
        )
        backend = FakeBackend({"connected": True, "label": "测试"})

        response, exit_code = run_request_line(
            request.to_json(), backend_factory=lambda: backend
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.result["label"], "测试")
        self.assertEqual(backend.calls[0][1], "ping")

    def test_invalid_request_returns_protocol_error(self):
        response, exit_code = run_request_line("not-json", backend_factory=FakeBackend)

        self.assertEqual(exit_code, 2)
        self.assertFalse(response.ok)
        self.assertEqual(response.error["code"], "invalid_request")

    def test_backend_failure_returns_stable_error(self):
        request = WorkerRequest.create(
            "ping", AedtTarget("pid", 1234), {}, 5.0
        )
        backend = FakeBackend(error=RuntimeError("AEDT unavailable"))

        response, exit_code = run_request_line(
            request.to_json(), backend_factory=lambda: backend
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.error["code"], "backend_error")
        self.assertIn("AEDT unavailable", response.error["message"])


class WorkerClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            close_all = getattr(client, "close_all", None)
            if close_all:
                close_all()
            # Only these test-created fake workers may be terminated. The
            # production timeout path must leave an unknown operation alone.
            for broker in list({id(b): b for b in client._brokers.values()}.values()):
                self.assertEqual(client.worker_script.parent,self.root)
                client._stop_broker(broker,graceful_timeout=0.2)
        self.temp.cleanup()

    def _script(self, name, source):
        path = self.root / name
        path.write_text(source, encoding="utf-8")
        return path

    def _client(self, script, timeout=2.0):
        client = WorkerClient(
            worker_script=script,
            python_executable=sys.executable,
            log_dir=self.root / "logs",
            default_timeout=timeout,
        )
        self.clients.append(client)
        return client

    def test_same_target_reuses_broker_until_release(self):
        script = self._script(
            "persistent_worker.py",
            """import json, sys, uuid
instance = str(uuid.uuid4())
for line in sys.stdin:
    request = json.loads(line)
    released = request["command"] == "release_connection"
    result = {"instance": instance, "released": released}
    print(json.dumps({"request_id": request["request_id"], "ok": True, "result": result, "error": None}), flush=True)
    if released:
        break
""",
        )
        client = self._client(script)
        target = AedtTarget("port", 50051)

        first = client.execute(target, "ping", {})
        second = client.execute(target, "ping", {})
        released = client.release(target)
        third = client.execute(target, "ping", {})

        self.assertEqual(first["instance"], second["instance"])
        self.assertTrue(released["released"])
        self.assertNotEqual(first["instance"], third["instance"])

    def test_ping_registers_pid_and_port_aliases_for_one_broker(self):
        script = self._script(
            "alias_worker.py",
            """import json, sys, uuid
instance = str(uuid.uuid4())
for line in sys.stdin:
    request = json.loads(line)
    released = request["command"] == "release_connection"
    result = {"instance": instance, "pid": 4321, "port": 50051, "released": released}
    print(json.dumps({"request_id": request["request_id"], "ok": True, "result": result, "error": None}), flush=True)
    if released:
        break
""",
        )
        client = self._client(script)

        by_port = client.execute(AedtTarget("port", 50051), "ping", {})
        by_pid = client.execute(AedtTarget("pid", 4321), "ping", {})

        self.assertEqual(by_port["instance"], by_pid["instance"])

    def test_valid_subprocess_response_and_stderr_log(self):
        script = self._script(
            "valid_worker.py",
            """import json, sys
for line in sys.stdin:
    request = json.loads(line)
    sys.stderr.write("worker diagnostic\\n")
    print(json.dumps({"request_id": request["request_id"], "ok": True, "result": {"pid": 7}, "error": None}), flush=True)
    if request["command"] == "release_connection":
        break
""",
        )

        result = self._client(script).execute(
            AedtTarget("pid", 7), "ping", {}, timeout=1.0
        )

        self.assertEqual(result, {"pid": 7})
        logs = list((self.root / "logs").glob("*.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("worker diagnostic", logs[0].read_text(encoding="utf-8"))

    def test_timeout_retains_worker_without_replaying_request(self):
        script = self._script(
            "sleep_worker.py",
            "import time, sys, json\nr=json.loads(sys.stdin.readline())\ntime.sleep(0.4)\n"
            "print(json.dumps(dict(request_id=r['request_id'],ok=True,result={'late':True},error=None)),flush=True)\n",
        )
        client = self._client(script, timeout=0.1)

        started = time.monotonic()
        with self.assertRaises(WorkerTimeoutError):
            client.execute(AedtTarget("pid", 7), "ping", {}, timeout=0.1)

        self.assertLess(time.monotonic() - started, 5.0)
        broker = client._brokers['pid:7']
        self.assertIsNotNone(broker.pending_request)
        time.sleep(0.5)
        with self.assertRaises(WorkerRecoveredError):
            client.execute(AedtTarget('pid',7),'ping',{})

    def test_invalid_stdout_is_rejected(self):
        script = self._script(
            "invalid_worker.py",
            "import sys\nsys.stdin.readline()\nprint('not-json', flush=True)\n",
        )

        with self.assertRaises(WorkerProtocolOutputError):
            self._client(script).execute(AedtTarget("pid", 7), "ping", {})

    def test_multiple_stdout_lines_are_rejected(self):
        script = self._script(
            "two_lines.py",
            "import sys\nsys.stdin.readline()\nprint('{}', flush=True)\nprint('{}', flush=True)\n",
        )

        with self.assertRaisesRegex(WorkerProtocolOutputError, "exactly one"):
            self._client(script).execute(AedtTarget("pid", 7), "ping", {})

    def test_nonzero_without_valid_response_is_process_error(self):
        script = self._script(
            "failed_worker.py",
            "import sys\nsys.stdin.readline()\nsys.stderr.write('failed')\nraise SystemExit(3)\n",
        )

        with self.assertRaises(WorkerProcessError):
            self._client(script).execute(AedtTarget("pid", 7), "ping", {})

    def test_remote_error_preserves_code_and_detail(self):
        script = self._script(
            "remote_error.py",
            """import json, sys
request = json.loads(sys.stdin.readline())
print(json.dumps({"request_id": request["request_id"], "ok": False, "result": None, "error": {"code": "session_not_found", "message": "missing", "detail": {"pid": 7}}}))
raise SystemExit(1)
""",
        )

        with self.assertRaises(WorkerRemoteError) as caught:
            self._client(script).execute(AedtTarget("pid", 7), "ping", {})

        self.assertEqual(caught.exception.code, "session_not_found")
        self.assertEqual(caught.exception.detail, {"pid": 7})

    def test_mismatched_request_id_is_rejected(self):
        script = self._script(
            "wrong_id.py",
            "import sys\nsys.stdin.readline()\nprint('{\"request_id\":\"wrong\",\"ok\":true,\"result\":{},\"error\":null}', flush=True)\n",
        )

        with self.assertRaisesRegex(WorkerProtocolOutputError, "request_id"):
            self._client(script).execute(AedtTarget("pid", 7), "ping", {})


class WorkerLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_target_is_serialized_and_distinct_targets_overlap(self):
        client = WorkerClient(worker_script=Path("unused.py"))
        active = 0
        max_by_pair = {"same": 0, "different": 0}

        def slow_execute(target, command, arguments, timeout=None):
            nonlocal active
            active += 1
            bucket = arguments["bucket"]
            max_by_pair[bucket] = max(max_by_pair[bucket], active)
            time.sleep(0.05)
            active -= 1
            return {"target": target.key}

        client.execute = slow_execute

        same = AedtTarget("pid", 1)
        await asyncio.gather(
            client.execute_async(same, "ping", {"bucket": "same"}),
            client.execute_async(same, "ping", {"bucket": "same"}),
        )
        self.assertEqual(max_by_pair["same"], 1)

        await asyncio.gather(
            client.execute_async(AedtTarget("pid", 2), "ping", {"bucket": "different"}),
            client.execute_async(AedtTarget("pid", 3), "ping", {"bucket": "different"}),
        )
        self.assertGreaterEqual(max_by_pair["different"], 2)


if __name__ == "__main__":
    unittest.main()
