"""Smoke-test installer against a disposable mock upstream repository."""
import importlib.util,pathlib,tempfile,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('kit_installer2',ROOT/'install.py');kit=importlib.util.module_from_spec(spec);spec.loader.exec_module(kit)
class InstallerFlowTests(unittest.TestCase):
 def test_success_install_and_modified_target_refusal(self):
  with tempfile.TemporaryDirectory() as tmp:
   repo=pathlib.Path(tmp)
   for name in ('mcp_server.py','pyaedt_worker.py','pyaedt_capabilities.py'):(repo/name).write_text('baseline',encoding='utf-8')
   mf={'files':{'mcp_server.py':{'kit_file':'files/mcp_server.py','base_sha256':kit.sha256(repo/'mcp_server.py'),'installed_sha256':kit.sha256(ROOT/'files/mcp_server.py')}},'tests':[]}
   self.assertTrue(kit.verify_payload(mf));self.assertTrue(kit.do_install(mf,str(repo),False))
   self.assertEqual(kit.classify(str(repo),dict(mf['files']['mcp_server.py'],installed_path='mcp_server.py'))[0],'installed')
   (repo/'mcp_server.py').write_text('user change',encoding='utf-8')
   self.assertFalse(kit.do_install(mf,str(repo),False));self.assertEqual((repo/'mcp_server.py').read_text(),'user change')
 def test_test_failures_propagated_from_check(self):
  with tempfile.TemporaryDirectory() as tmp:
   with mock.patch.object(kit,'run_test_suite',return_value=False):
    result=kit.do_check({'files':{},'tests':['mock.failure']},tmp,run_tests=True)
   self.assertFalse(result['tests_ok'])
if __name__=='__main__':unittest.main()
