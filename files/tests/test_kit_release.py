"""Regression tests run only in temporary mock repositories, never AEDT."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('kit_release_installer',ROOT/'install.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class ReleaseInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.payload = self.root/'kit'
        self.repo = self.root/'repo'
        self.payload.mkdir()
        self.repo.mkdir()
        self.patch = mock.patch.object(kit,'HERE',str(self.payload))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def manifest(self,paths=('a.py','b.py'),new=False):
        entries = {}
        for name in paths:
            src = self.payload/'files'/name
            src.parent.mkdir(parents=True,exist_ok=True)
            src.write_bytes(b'new\n')
            dst = self.repo/name
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not new:
                dst.write_bytes(b'old\n')
            entries[name] = {'kit_file':'files/'+name,'installed_sha256':kit.sha256(src),
                             'base_sha256':hashlib.sha256(b'old\n').hexdigest(),
                             'new_file':new,'text_lf':True}
        return {'version':'test','files':entries,'tests':[]}

    def test_crlf_only_target_is_accepted(self):
        mf = self.manifest(('a.py',))
        (self.repo/'a.py').write_bytes(b'old\r\n')
        entry = dict(mf['files']['a.py'],installed_path='a.py')
        self.assertEqual(kit.classify(self.repo,entry)[0],'base')
        self.assertTrue(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'new\n')
        backup = Path(kit.LAST_BATCH)/'before/a.py'
        self.assertEqual(backup.read_bytes(),b'old\r\n')

    def test_payload_crlf_change_is_still_rejected(self):
        mf = self.manifest(('a.py',))
        (self.payload/'files/a.py').write_bytes(b'new\r\n')
        self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')

    def test_trailing_whitespace_is_real_edit(self):
        mf = self.manifest(('a.py',))
        (self.repo/'a.py').write_bytes(b'old \r\n')
        self.assertFalse(kit.do_install(mf,self.repo))

    def test_missing_original_aborts_before_any_write(self):
        mf = self.manifest()
        (self.repo/'b.py').unlink()
        self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')
        self.assertEqual(kit.do_check(mf,self.repo)['missing_required'],1)
        self.assertFalse((self.repo/'.aedt-hardening-backups').exists())

    def test_new_file_allowed_and_idempotent(self):
        mf = self.manifest(('new.py',),new=True)
        self.assertTrue(kit.do_install(mf,self.repo))
        batches = list((self.repo/'.aedt-hardening-backups').iterdir())
        self.assertTrue(kit.do_install(mf,self.repo))
        self.assertEqual(list((self.repo/'.aedt-hardening-backups').iterdir()),batches)

    def test_target_paths_are_checked_even_when_payload_exists(self):
        for target in ('../escape.py','C:/escape.py','/escape.py','a/../escape.py','a.py:stream','a\\b.py'):
            mf = self.manifest(('a.py',))
            mf['files'][target] = mf['files'].pop('a.py')
            with self.subTest(target=target):
                self.assertFalse(kit.verify_payload(mf))

    def test_case_collisions_rejected(self):
        mf = self.manifest(('a.py',))
        mf['files']['A.py'] = dict(mf['files']['a.py'])
        self.assertFalse(kit.verify_payload(mf))

    def test_modified_second_target_leaves_first_intact(self):
        mf = self.manifest()
        (self.repo/'b.py').write_bytes(b'USER')
        self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')

    def test_write_failure_rolls_back_as_a_batch(self):
        mf = self.manifest()
        real = kit._atomic_write
        def fail_second(path,data):
            if Path(path) == self.repo/'b.py' and data == b'new\n':
                raise OSError('injected write failure')
            return real(path,data)
        with mock.patch.object(kit,'_atomic_write',side_effect=fail_second):
            self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')
        self.assertEqual((self.repo/'b.py').read_bytes(),b'old\n')
        journal = json.loads((Path(kit.LAST_BATCH)/'journal.json').read_text())
        self.assertEqual(journal['status'],'rolled_back')

    def test_rollback_does_not_overwrite_external_edit(self):
        mf = self.manifest()
        real = kit._atomic_write
        def fail_after_external_write(path,data):
            if Path(path) == self.repo/'b.py' and data == b'new\n':
                (self.repo/'a.py').write_bytes(b'EXTERNAL')
                raise OSError('external editor')
            return real(path,data)
        with mock.patch.object(kit,'_atomic_write',side_effect=fail_after_external_write):
            self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'EXTERNAL')
        journal = json.loads((Path(kit.LAST_BATCH)/'journal.json').read_text())
        self.assertEqual(journal['status'],'rollback_incomplete')
        self.assertEqual(journal['rollback_conflicts'],['a.py'])

    def test_install_lock_is_not_deleted_or_overwritten(self):
        mf = self.manifest(('a.py',))
        lock = self.repo/'.aedt-hardening-install.lock'
        lock.write_bytes(b'OTHER INSTALLER')
        self.assertFalse(kit.do_install(mf,self.repo))
        self.assertEqual(lock.read_bytes(),b'OTHER INSTALLER')
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')

    def test_dependencies_are_validated_before_writes(self):
        mf = self.manifest(('a.py',))
        (self.repo/'pyproject.toml').write_text('[project]\ndependencies = ["unknown"]\n')
        self.assertFalse(kit.do_install(mf,self.repo,pyproject=True))
        self.assertEqual((self.repo/'a.py').read_bytes(),b'old\n')

    def test_pyproject_edits_only_project_dependencies(self):
        text = '# "mcp>=1.0"\n[project]\ndependencies = [\n  "mcp>=1.0",\n  "pyaedt==1.5.0",\n]\n[tool.example]\nname = "mcp>=1.0"\n[tool.setuptools]\npy-modules = [\n "mcp_server",\n]\n'
        (self.repo/'pyproject.toml').write_bytes(text.encode())
        before,after = kit._pyproject_bytes(self.repo,True)
        self.assertIn(b'"mcp>=1.0,<2"',after)
        self.assertIn(b'"pyaedt==1.9.0"',after)
        self.assertIn(b'name = "mcp>=1.0"',after)
        self.assertIn(b'"aedt_project_guard"',after)
        self.assertIn(b'"solve_evidence"',after)
        self.assertEqual(before.decode(),text)

    def test_test_failure_propagates(self):
        with mock.patch.object(kit,'run_test_suite',return_value=False):
            self.assertFalse(kit.do_check({'files':{},'tests':['fake']},self.repo,True)['tests_ok'])


if __name__ == '__main__':
    unittest.main()
