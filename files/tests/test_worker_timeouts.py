"""No subprocesses or AEDT: test lost-response recovery and non-replay."""
from io import StringIO
from pathlib import Path
import queue
import threading
import unittest
from unittest import mock

from aedt_target import AedtTarget
from worker_client import (WorkerClient,_Broker,WorkerTimeoutError,WorkerPendingError,
                           WorkerRecoveredError,WorkerProcessError)
from worker_protocol import WorkerResponse


class WorkerTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.target = AedtTarget('pid',42)
        self.process = mock.Mock()
        self.process.poll.return_value = None
        self.process.stdin = StringIO()
        self.broker = _Broker(self.process,self.target,queue.Queue(),mock.Mock(),StringIO(),Path('mock.log'))
        self.client = WorkerClient(default_timeout=1)
        self.client._brokers[self.target.key] = self.broker
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.client._brokers.clear()
        self.broker.log_handle.close()

    def timeout(self):
        with self.assertRaises(WorkerTimeoutError):
            self.client.execute(self.target,'mutating',{},timeout=0.001)
        self.assertIsNotNone(self.broker.pending_request)

    def test_timeout_does_not_terminate_or_restart(self):
        self.timeout()
        first = self.process.stdin.getvalue()
        with self.assertRaises(WorkerPendingError):
            self.client.execute(self.target,'mutating',{})
        self.assertEqual(self.process.stdin.getvalue(),first)
        self.process.terminate.assert_not_called()
        self.process.kill.assert_not_called()

    def test_late_success_is_recovered_without_new_command(self):
        self.timeout()
        first = self.process.stdin.getvalue()
        response = WorkerResponse.success(self.broker.pending_request.request_id,{'done':True,'pid':42})
        self.broker.responses.put(response.to_json())
        with self.assertRaises(WorkerRecoveredError) as context:
            self.client.execute(self.target,'mutating',{})
        self.assertEqual(context.exception.result,{'done':True,'pid':42})
        self.assertEqual(self.process.stdin.getvalue(),first)
        self.assertIsNone(self.broker.pending_request)

    def test_late_failure_is_recovered_without_new_command(self):
        self.timeout()
        response = WorkerResponse.failure(self.broker.pending_request.request_id,'error','failed')
        self.broker.responses.put(response.to_json())
        with self.assertRaises(WorkerRecoveredError) as context:
            self.client.execute(self.target,'mutating',{})
        self.assertEqual(context.exception.error['code'],'error')

    def test_release_does_not_kill_pending_broker(self):
        self.timeout()
        with self.assertRaises(WorkerPendingError):
            self.client.release(self.target)
        self.process.terminate.assert_not_called()

    def test_release_timeout_itself_does_not_kill_broker(self):
        with self.assertRaises(WorkerTimeoutError):
            self.client.release(self.target,timeout=0.001)
        self.assertIsNotNone(self.broker.pending_request)
        self.process.terminate.assert_not_called()

    def test_close_all_release_timeout_does_not_kill_broker(self):
        self.client.default_timeout = 0.001
        self.client.close_all()
        self.assertIsNotNone(self.broker.pending_request)
        self.process.terminate.assert_not_called()

    def test_sent_request_eof_preserves_unknown_outcome(self):
        self.broker.responses.put(None)
        self.process.poll.side_effect = [None,None,1]
        self.process.returncode = 1
        with self.assertRaises(WorkerProcessError):
            self.client.execute(self.target,'mutating',{})
        self.assertIsNotNone(self.broker.pending_request)
        self.process.poll.side_effect = None
        self.process.poll.return_value = 1
        with mock.patch.object(self.client,'_start_broker') as start:
            with self.assertRaises(WorkerProcessError):
                self.client.execute(self.target,'mutating',{})
        start.assert_not_called()
        self.client.close_all()
        self.process.terminate.assert_not_called()

    def test_dead_timed_out_broker_is_not_automatically_restarted(self):
        self.timeout()
        self.process.poll.return_value = 1
        with mock.patch.object(self.client,'_start_broker') as start:
            with self.assertRaises(WorkerProcessError):
                self.client.execute(self.target,'mutating',{})
        start.assert_not_called()

    def test_invalid_timeout_rejected_before_sending(self):
        for timeout in (0,-1,float('nan'),float('inf'),True):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    self.client.execute(self.target,'mutating',{},timeout=timeout)
        self.assertEqual(self.process.stdin.getvalue(),'')


if __name__ == '__main__':
    unittest.main()
