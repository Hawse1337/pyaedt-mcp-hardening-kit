"""Installer safety tests; isolated temporary files only, no AEDT required."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('kit_installer',ROOT/'install.py')
kit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

class PayloadSafetyTests(unittest.TestCase):
    def test_real_payload_matches_manifest(self):
        self.assertTrue(kit.verify_payload(kit.load_manifest()))
    def test_modified_payload_rejected(self):
        manifest=kit.load_manifest()
        manifest['files']['aedt_project_guard.py']['installed_sha256']='0'*64
        self.assertFalse(kit.verify_payload(manifest))
    def test_missing_payload_rejected(self):
        manifest=kit.load_manifest()
        manifest['files']['aedt_project_guard.py']['kit_file']='files/missing.py'
        self.assertFalse(kit.verify_payload(manifest))
    def test_path_escape_rejected(self):
        manifest=kit.load_manifest()
        manifest['files']['aedt_project_guard.py']['kit_file']='../outside.py'
        self.assertFalse(kit.verify_payload(manifest))
    def test_force_and_revert_are_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            for name in ('mcp_server.py','pyaedt_worker.py','pyaedt_capabilities.py'):
                (root/name).write_text('user work',encoding='utf-8')
            for flag in ('--force','--revert'):
                args=['install.py','--repo',d,flag]
                if flag=='--force': args.append('--install')
                with mock.patch('sys.argv',args):
                    self.assertEqual(kit.main(),1)
            self.assertEqual((root/'mcp_server.py').read_text(encoding='utf-8'),'user work')

    def test_modified_target_not_overwritten_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'x.py';target.write_text('user work',encoding='utf-8')
            manifest={'files':{'x.py':{'installed_sha256':'a'*64,'base_sha256':'b'*64,'kit_file':'files/aedt_project_guard.py'}}}
            self.assertFalse(kit.do_install(manifest,d,False))
            self.assertEqual(target.read_text(encoding='utf-8'),'user work')

if __name__=='__main__':unittest.main()
