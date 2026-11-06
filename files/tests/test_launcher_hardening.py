"""Offline regression tests: no AEDT, COM, gRPC or real processes are started."""
import os
import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from aedt_launcher import AedtLaunchError, AedtLauncher
import pyaedt_backend as backend
from session_discovery import SessionDiscovery


class LauncherRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.install = Path(self.temp.name)
        (self.install / 'ansysedt.exe').write_bytes(b'not executable')
        self.process = Mock(pid=12345)
        self.process.poll.return_value = None
        self.factory = Mock(return_value=self.process)
        self.worker = Mock()
        self.worker.execute.return_value = {'connected': True, 'pid': 12345, 'port':50051, 'aedt_version': '2026.1'}
        self.now = 0.0

    def tearDown(self):
        self.temp.cleanup()

    def sleep(self, seconds):
        self.now += seconds

    def launcher(self, **options):
        values = dict(worker_client=self.worker, process_factory=self.factory,
                      choose_free_port=lambda: 50051, port_is_free=lambda port: True,
                      port_is_open=lambda port: False, monotonic=lambda: self.now, sleep=self.sleep)
        values.update(options)
        return AedtLauncher(**values)

    def test_no_broker_is_created_during_passive_timeout(self):
        with self.assertRaisesRegex(AedtLaunchError, 'no broker probe was started'):
            self.launcher().launch(install_dir=self.install, timeout=2)
        self.factory.assert_called_once()
        self.worker.execute.assert_not_called()
        self.worker.release.assert_not_called()
        self.process.terminate.assert_not_called()
        self.process.kill.assert_not_called()

    def test_repeated_call_after_timeout_does_not_spawn_another_process(self):
        launcher = self.launcher()
        for message in ('timed out', 'still running'):
            with self.assertRaisesRegex(AedtLaunchError, message):
                launcher.launch(install_dir=self.install, timeout=1)
        self.factory.assert_called_once()

    def test_one_handshake_receives_remaining_budget_not_five_second_probes(self):
        result = self.launcher(port_is_open=lambda port: True).launch(install_dir=self.install, timeout=240)
        self.worker.execute.assert_called_once()
        self.assertEqual(self.worker.execute.call_args.kwargs['timeout'], 240)
        self.assertEqual(self.worker.execute.call_args.args[0].key, 'pid:12345')
        self.assertEqual(result['pid'], 12345)

    def test_handshake_error_does_not_retry_or_terminate(self):
        self.worker.execute.side_effect = TimeoutError('connection pending')
        launcher = self.launcher(port_is_open=lambda port: True)
        with self.assertRaisesRegex(AedtLaunchError, 'no retry or termination'):
            launcher.launch(install_dir=self.install, timeout=240)
        self.worker.execute.assert_called_once()
        self.worker.release.assert_not_called()
        self.process.terminate.assert_not_called()
        with self.assertRaisesRegex(AedtLaunchError, 'still running'):
            launcher.launch(install_dir=self.install, timeout=240)
        self.factory.assert_called_once()

    def test_identity_version_or_connection_mismatch_never_returns_success(self):
        invalid = [None, {}, {'connected':False, 'pid':12345, 'port':50051, 'aedt_version':'2026.1'},
                   {'connected':True, 'pid':999, 'port':50051, 'aedt_version':'2026.1'},
                   {'connected':True, 'pid':True, 'port':50051, 'aedt_version':'2026.1'},
                   {'connected':True, 'pid':12345, 'port':50051, 'aedt_version':'2023.1'},
                   {'connected':True, 'pid':12345, 'port':0, 'aedt_version':'2026.1'},
                   {'connected':True, 'pid':12345, 'port':59999, 'aedt_version':'2026.1'}]
        for value in invalid:
            with self.subTest(value=value):
                self.worker.execute.return_value = value
                with self.assertRaises(AedtLaunchError):
                    self.launcher(port_is_open=lambda port: True).launch(install_dir=self.install, timeout=1)

    def test_nonfinite_or_invalid_timeout_never_starts_process(self):
        for value in (float('nan'), float('inf'), -1, 0, True, 'nan', 'inf', 'x'):
            with self.subTest(value=value):
                with self.assertRaises(AedtLaunchError):
                    self.launcher().launch(install_dir=self.install, timeout=value)
        self.factory.assert_not_called()

    def test_invalid_selected_port_never_starts_process(self):
        with self.assertRaises(AedtLaunchError):
            self.launcher(choose_free_port=lambda: 0).launch(install_dir=self.install)
        self.factory.assert_not_called()

    def test_concurrent_launch_is_refused_before_process_creation(self):
        launcher = self.launcher()
        launcher._launch_lock.acquire()
        try:
            with self.assertRaisesRegex(AedtLaunchError, 'already in progress'):
                launcher.launch(install_dir=self.install)
        finally:
            launcher._launch_lock.release()
        self.factory.assert_not_called()

    def test_failed_process_may_exit_before_a_later_explicit_launch(self):
        launcher = self.launcher()
        with self.assertRaises(AedtLaunchError):
            launcher.launch(install_dir=self.install, timeout=1)
        self.process.poll.return_value = 1
        with self.assertRaisesRegex(AedtLaunchError, 'exited with code 1'):
            launcher.launch(install_dir=self.install, timeout=1)
        self.assertEqual(self.factory.call_count, 2)


class DiscoveryRegressionTests(unittest.TestCase):
    def test_lan_listener_is_reported_and_command_line_port_is_only_a_hint(self):
        process = SimpleNamespace(info={'pid': 12345, 'name':'ansysedt.exe', 'exe':None,
                                       'create_time':None, 'cmdline':['ansysedt.exe','-grpcsrv','2004']})
        connection = SimpleNamespace(pid=12345,status='LISTEN',laddr=('192.168.0.10',2004))
        worker = Mock()
        discovery = SessionDiscovery(process_iter=lambda attrs:[process],net_connections=lambda kind:[connection],worker_client=worker)
        result = discovery.list_sessions()[0]
        self.assertEqual(result['listening_ports'], [2004])
        self.assertEqual(result['configured_grpc_port'], 2004)
        worker.execute.assert_not_called()
        discovery._net_connections = Mock(side_effect=PermissionError())
        result = discovery.list_sessions()[0]
        self.assertEqual(result['listening_ports'], [])
        self.assertEqual(result['configured_grpc_port'], 2004)

    def test_invalid_process_identifiers_and_command_lines_are_ignored(self):
        records = [SimpleNamespace(info={'pid': True,'name':'ansysedt.exe'}),
                   SimpleNamespace(info={'pid':-1,'name':'ansysedt.exe'}),
                   SimpleNamespace(info={'pid':12345,'name':'ansysedt.exe','cmdline':['x','-grpcsrv','65536']})]
        discovery = SessionDiscovery(process_iter=lambda attrs:records,net_connections=lambda kind:[],worker_client=Mock())
        result = discovery.list_sessions()
        self.assertEqual(len(result),1)
        self.assertNotIn('configured_grpc_port',result[0])


def fake_vendor_module():
    module = SimpleNamespace(launches=0, settings=SimpleNamespace(remote_rpc_session=None, use_lsf_scheduler=False))
    def launch(*args, **kwargs):
        module.launches += 1
        raise AssertionError('a fallback would have launched AEDT')
    module.launch_aedt = launch
    class Desktop:
        def __init__(self, **kwargs):
            self.new_desktop = kwargs['new_desktop']
            self.port = kwargs.get('port', 50051)
            self.is_grpc_api = True
            self.aedt_process_id = 12345
            self.aedt_version_id = kwargs['version']
            self.check_starting_mode()
            self._validate_port()
            self._Desktop__initialize(False)
        def check_starting_mode(self):
            self.is_grpc_api = False
        def _validate_port(self):
            # Simulates the exact bug: vendor discovery misses the target.
            self.new_desktop = True
            self.port = 59999
        def _Desktop__initialize(self,new_desktop_required=None):
            if self.new_desktop or new_desktop_required:
                module.launch_aedt()
            return True
        def _Desktop__dispatch_win32(self,*args):
            module.launch_aedt()
        def _Desktop__run_student(self):
            module.launch_aedt()
    module.Desktop = Desktop
    return module


class AttachOnlyRegressionTests(unittest.TestCase):
    def test_unverified_pid_or_non_aedt_port_never_invokes_vendor(self):
        with patch.object(backend,'_audited_desktop_module') as factory, patch('psutil.Process',side_effect=ProcessLookupError()):
            with self.assertRaises(backend.BackendCommandError):
                backend._default_desktop_factory(aedt_process_id=12345,new_desktop=False)
            factory.assert_not_called()

    def test_listener_owner_must_exist_and_be_aedt(self):
        connection = SimpleNamespace(pid=12345,status='LISTEN',laddr=('192.168.0.10',50051))
        process = Mock()
        process.name.return_value = 'python.exe'
        with patch('psutil.net_connections',return_value=[connection]),patch('psutil.Process',return_value=process):
            with self.assertRaisesRegex(backend.BackendCommandError,'does not belong'):
                backend._existing_target_owner({'new_desktop':False,'port':50051})

    def test_unknown_listener_owner_is_not_treated_as_aedt(self):
        connection = SimpleNamespace(pid=None,status='LISTEN',laddr=('127.0.0.1',50051))
        with patch('psutil.net_connections',return_value=[connection]):
            with self.assertRaisesRegex(backend.BackendCommandError,'owner is unknown'):
                backend._existing_target_owner({'new_desktop':False,'port':50051})

    def test_constructor_bypasses_false_negative_port_discovery_without_launch(self):
        module = fake_vendor_module()
        original = module.Desktop._validate_port
        with patch.dict(os.environ,{},clear=True), patch.object(backend,'_existing_target_owner',return_value=(12345,1000.0)), patch.object(backend,'_audited_desktop_module',return_value=module):
            result = backend._default_desktop_factory(version='2026.1',new_desktop=False,port=50051,machine='localhost')
        self.assertEqual(result.aedt_process_id,12345)
        self.assertEqual(result.port,50051)
        self.assertEqual(module.launches,0)
        self.assertIs(module.Desktop._validate_port,original)

    def test_all_audited_fallback_entries_refuse_and_restore_after_exception(self):
        module = fake_vendor_module()
        original = module.launch_aedt
        with self.assertRaisesRegex(backend.BackendCommandError,'fallback launch'):
            with backend._attach_only_desktop(module,{'port':50051}):
                module.launch_aedt()
        self.assertIs(module.launch_aedt,original)
        for name in ('_Desktop__dispatch_win32','_Desktop__run_student'):
            with backend._attach_only_desktop(module,{'port':50051}):
                with self.assertRaises(backend.BackendCommandError):
                    getattr(module.Desktop,name)(None)
        self.assertEqual(module.launches,0)

    def test_initializer_refuses_new_desktop_and_com_without_pid(self):
        module = fake_vendor_module()
        with backend._attach_only_desktop(module,{'port':50051}):
            for obj,required in [(SimpleNamespace(new_desktop=True),False),
                                 (SimpleNamespace(new_desktop=False),True),
                                 (SimpleNamespace(new_desktop=False,is_grpc_api=False),False)]:
                with self.assertRaises(backend.BackendCommandError):
                    module.Desktop._Desktop__initialize(obj,required)

    def test_unreviewed_pyaedt_version_is_refused(self):
        with patch('importlib.metadata.version',return_value='2.0.0'):
            with self.assertRaisesRegex(backend.BackendCommandError,'audited for PyAEDT 1.9.0'):
                backend._audited_desktop_module()

    def test_com_initializer_loads_utilities_without_creating_an_application(self):
        module = fake_vendor_module()
        clr = Mock()
        wrapper = Mock()
        comutil = object()
        com = SimpleNamespace(Ansoft=SimpleNamespace(CoreCOMScripting=SimpleNamespace(
            Util=SimpleNamespace(COMUtil=comutil), COM=SimpleNamespace(StandalonePyScriptWrapper=wrapper))))
        fake_modules = {'ansys.aedt.core.internal.clr_module':SimpleNamespace(_clr=clr), 'Ansys':com,
                        'Ansys.Ansoft':com.Ansoft, 'Ansys.Ansoft.CoreCOMScripting':com.Ansoft.CoreCOMScripting}
        desktop = SimpleNamespace(new_desktop=False,is_grpc_api=False)
        with patch.dict(sys.modules,fake_modules), backend._attach_only_desktop(module,{'aedt_process_id':12345}):
            self.assertIsNone(module.Desktop._Desktop__initialize(desktop,False))
        self.assertIs(desktop.COMUtil,comutil)
        clr.AddReference.assert_called_once_with('Ansys.Ansoft.CoreCOMScripting')
        wrapper.CreateObject.assert_not_called()
        wrapper.CreateObjectNew.assert_not_called()

    def test_com_initializer_reports_missing_pythonnet_without_fallback(self):
        module = fake_vendor_module()
        desktop = SimpleNamespace(new_desktop=False,is_grpc_api=False)
        with patch.dict(sys.modules,{'ansys.aedt.core.internal.clr_module':SimpleNamespace(_clr=None)}), backend._attach_only_desktop(module,{'aedt_process_id':12345}):
            with self.assertRaisesRegex(backend.BackendCommandError,'ansys-pythonnet'):
                module.Desktop._Desktop__initialize(desktop,False)

    def test_environment_target_override_is_refused(self):
        for name,value in [('PYAEDT_PROCESS_ID','999'),('PYAEDT_DESKTOP_PORT','999'),
                           ('PYAEDT_DOC_GENERATION','true'),('PYAEDT_NON_GRAPHICAL','1')]:
            with self.subTest(name=name), patch.dict(os.environ,{name:value},clear=True):
                with self.assertRaises(backend.BackendCommandError):
                    backend._default_desktop_factory(aedt_process_id=12345,new_desktop=False)

    def test_unreviewed_vendor_layout_and_remote_settings_fail_closed(self):
        module = fake_vendor_module()
        module.Desktop._Desktop__initialize = None
        with self.assertRaisesRegex(backend.BackendCommandError,'layout differs'):
            with backend._attach_only_desktop(module,{}):
                self.fail('must never enter')
        module = fake_vendor_module()
        module.settings.remote_rpc_session = object()
        with patch.dict(os.environ,{},clear=True), patch.object(backend,'_existing_target_owner',return_value=(12345,1000.0)), patch.object(backend,'_audited_desktop_module',return_value=module):
            with self.assertRaisesRegex(backend.BackendCommandError,'remote/LSF'):
                backend._default_desktop_factory(version='2026.1',new_desktop=False,port=50051)

    def test_process_creation_time_change_aborts_without_closing_any_desktop(self):
        module = fake_vendor_module()
        owners = [(12345,1000.0),(12345,1000.0),(12345,2000.0)]
        with patch.dict(os.environ,{},clear=True), patch.object(backend,'_existing_target_owner',side_effect=owners), patch.object(backend,'_audited_desktop_module',return_value=module):
            with self.assertRaisesRegex(backend.BackendCommandError,'identity changed'):
                backend._default_desktop_factory(version='2026.1',new_desktop=False,port=50051)

    def test_pid_handshake_uses_command_line_hint_without_socket_owner_enumeration(self):
        module = fake_vendor_module()
        process = Mock()
        process.name.return_value = 'ansysedt.exe'
        process.create_time.return_value = 1000.0
        process.cmdline.return_value = ['ansysedt.exe','-grpcsrv','51568','-ng']
        with patch.dict(os.environ,{},clear=True), patch('psutil.Process',return_value=process), patch('psutil.net_connections',side_effect=AssertionError('must not enumerate sockets')), patch.object(backend,'_audited_desktop_module',return_value=module):
            result = backend._default_desktop_factory(version='2026.1',new_desktop=False,aedt_process_id=12345)
        self.assertEqual(result.aedt_process_id,12345)
        self.assertEqual(result.port,51568)
        self.assertTrue(result.is_grpc_api)
        self.assertEqual(module.launches,0)

    def test_invalid_command_line_port_remains_a_com_candidate_not_a_guessed_grpc_target(self):
        process = Mock()
        for command_line in ([], ['ansysedt.exe','-grpcsrv','65536'], ['ansysedt.exe','-grpcsrv','not-a-port']):
            process.cmdline.return_value = command_line
            with patch('psutil.Process',return_value=process):
                self.assertEqual(backend._pid_launch_hints(12345)[0],None)


if __name__ == '__main__':
    unittest.main()
