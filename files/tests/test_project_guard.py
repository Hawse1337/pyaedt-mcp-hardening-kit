# -*- coding: utf-8 -*-
"""Tests for aedt_project_guard (no AEDT session required)."""
import os
import builtins
import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import aedt_project_guard as guard


class ResolveProjectArgumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name).resolve()
        self.existing = self.dir / "LensFinal.aedt"
        self.existing.write_text("$begin 'AnsoftProject'\n", encoding="utf-8")
        self.dirs = [str(self.dir)]
        patcher = mock.patch.dict(os.environ, {"AEDT_GUARD_ALLOW_CREATE":"0", "AEDT_GUARD_ATTACH_OPEN":"0", "AEDT_GUARD_SEARCH_DIRS":""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_none_and_empty_are_untouched(self):
        self.assertIsNone(guard.resolve_project_argument(None, self.dirs))
        self.assertEqual(guard.resolve_project_argument("", self.dirs), "")

    def test_bare_name_matching_a_file_becomes_absolute_path(self):
        resolved = guard.resolve_project_argument("LensFinal", self.dirs)
        self.assertEqual(resolved, str(self.existing))
        self.assertTrue(os.path.isabs(resolved))

    def test_bare_name_with_extension_is_also_resolved(self):
        resolved = guard.resolve_project_argument("LensFinal.aedt", self.dirs)
        self.assertEqual(resolved, str(self.existing))

    def test_absolute_path_is_left_alone(self):
        value = str(self.existing)
        self.assertEqual(guard.resolve_project_argument(value, self.dirs), value)

    def test_missing_absolute_path_is_refused_before_implicit_creation(self):
        value = str(self.dir / "BrandNew.aedt")
        with self.assertRaisesRegex(RuntimeError, "missing project path"):
            guard.resolve_project_argument(value, self.dirs)

    def test_existing_relative_path_is_made_absolute(self):
        value = os.path.relpath(self.existing)
        self.assertEqual(guard.resolve_project_argument(value, self.dirs), str(self.existing))

    def test_missing_relative_path_with_separator_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "missing project path"):
            guard.resolve_project_argument("sub/Thing.aedt", self.dirs)

    def test_unknown_bare_name_is_refused(self):
        with self.assertRaises(RuntimeError) as ctx:
            guard.resolve_project_argument("NoSuchProject", self.dirs)
        self.assertIn("refused", str(ctx.exception))
        self.assertIn("OVERWRITE", str(ctx.exception))

    def test_escape_hatch_creates_inside_the_first_search_dir(self):
        # Creation is allowed, but the location must be deterministic: a bare name
        # becomes <first search dir>/<name>.aedt, never PyAEDT's default directory.
        with mock.patch.dict(os.environ, {"AEDT_GUARD_ALLOW_CREATE": "1"}):
            resolved = guard.resolve_project_argument("NoSuchProject", self.dirs)
        self.assertEqual(resolved, os.path.join(str(self.dir), "NoSuchProject.aedt"))
        self.assertTrue(os.path.isabs(resolved))

    def test_attach_open_flag_cannot_bypass_unverified_name(self):
        with mock.patch.dict(os.environ, {"AEDT_GUARD_ATTACH_OPEN": "1", "AEDT_GUARD_ALLOW_CREATE": "1"}):
            with self.assertRaisesRegex(RuntimeError, "unverified"):
                guard.resolve_project_argument("NoSuchProject", self.dirs)

    def test_search_dirs_can_come_from_environment(self):
        other = self.dir / "other"
        other.mkdir()
        target = other / "EnvProj.aedt"
        target.write_text("x", encoding="utf-8")
        with mock.patch.dict(os.environ, {"AEDT_GUARD_SEARCH_DIRS": str(other)}):
            resolved = guard.resolve_project_argument("EnvProj", [str(self.dir)])
        self.assertEqual(resolved, str(target))

    def test_duplicate_names_across_search_roots_are_refused(self):
        other = self.dir / 'other'
        other.mkdir()
        (other / self.existing.name).write_text('different project', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            guard.resolve_project_argument('LensFinal', [self.dir, other])

    def test_repeated_search_directory_is_one_match(self):
        self.assertEqual(guard.resolve_project_argument('LensFinal', [self.dir, self.dir / '.']), str(self.existing))

    def test_single_pathlike_search_root(self):
        self.assertEqual(guard.resolve_project_argument('LensFinal', self.dir), str(self.existing))

    def test_no_machine_specific_default_directories(self):
        with mock.patch('os.getcwd', return_value=str(self.dir)):
            self.assertEqual(guard._search_dirs(), [str(self.dir)])

    def test_pathlike_existing_project_is_checked(self):
        self.assertEqual(guard.resolve_project_argument(self.existing), str(self.existing))

    def test_pathlike_missing_project_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'missing project path'):
            guard.resolve_project_argument(self.dir / 'Missing.aedt')

    def test_nonpath_argument_cannot_bypass_guard(self):
        for value in (42, b'Example.aedt', object()):
            with self.assertRaises(TypeError):
                guard.resolve_project_argument(value)

    def test_nul_is_refused(self):
        with self.assertRaises(ValueError):
            guard.resolve_project_argument('Example\x00.aedt')

    @unittest.skipUnless(os.name == 'nt', 'Windows drive-relative path')
    def test_drive_relative_path_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'drive-relative'):
            guard.resolve_project_argument('C:Example.aedt')

    def test_aedb_existing_directory_is_supported(self):
        database = self.dir / 'Layout.aedb'
        database.mkdir()
        self.assertEqual(guard.resolve_project_argument(database), str(database))
        self.assertEqual(guard.resolve_project_argument('Layout.aedb', self.dirs), str(database))

    def test_ordinary_directory_is_not_a_project(self):
        with self.assertRaisesRegex(RuntimeError, 'invalid project path'):
            guard.resolve_project_argument(self.dir)

    def test_explicit_missing_path_legacy_creation_option(self):
        target = self.dir / 'LegacyNew.aedt'
        with mock.patch.dict(os.environ, {'AEDT_GUARD_ALLOW_CREATE':'1'}):
            self.assertEqual(guard.resolve_project_argument(target), str(target))

    def test_duplicate_roots_with_same_real_path_are_not_ambiguous(self):
        with mock.patch.dict(os.environ, {'AEDT_GUARD_SEARCH_DIRS': str(self.dir)}):
            self.assertEqual(guard.resolve_project_argument('LensFinal', [self.dir]), str(self.existing))

    def test_broken_symlink_is_not_followed_for_creation(self):
        link = self.dir / 'Broken.aedt'
        try:
            link.symlink_to(self.dir / 'Missing.aedt')
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation not supported by this environment')
        with mock.patch.dict(os.environ, {'AEDT_GUARD_ALLOW_CREATE':'1'}):
            with self.assertRaisesRegex(RuntimeError, 'invalid project path'):
                guard.resolve_project_argument(link)
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                guard.resolve_project_argument('Broken', self.dirs)
        self.assertTrue(os.path.lexists(link))


class CreateProjectTests(unittest.TestCase):
    """create_project() is the sanctioned way to create a new project."""

    class FakeApp:
        def __init__(self, project=None, **kwargs):
            self.project = project
            self.kwargs = kwargs

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name).resolve()
        patcher = mock.patch.dict(os.environ, {"AEDT_GUARD_ALLOW_CREATE":"0", "AEDT_GUARD_ATTACH_OPEN":"0", "AEDT_GUARD_SEARCH_DIRS":""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_creates_at_the_requested_absolute_path(self):
        target = self.dir / "BrandNew.aedt"
        app = guard.create_project(self.FakeApp, str(target), design="D1")
        self.assertEqual(app.project, str(target))
        self.assertFalse(target.exists())  # FakeApp must not create the file
        self.assertEqual(app.kwargs["design"], "D1")

    def test_appends_aedt_extension(self):
        app = guard.create_project(self.FakeApp, str(self.dir / "NoExt"))
        self.assertTrue(app.project.endswith("NoExt.aedt"))

    def test_refuses_when_the_file_already_exists(self):
        existing = self.dir / "LensFinal.aedt"
        existing.write_text("x", encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            guard.create_project(self.FakeApp, str(existing))
        self.assertIn("already exists", str(ctx.exception))
        # the file must be untouched
        self.assertEqual(existing.read_text(encoding="utf-8"), "x")

    def test_rejects_a_bare_name(self):
        # A bare name would let PyAEDT pick the directory; refuse it.
        old = os.getcwd()
        os.chdir(self.dir)
        try:
            with self.assertRaises((ValueError, RuntimeError)):
                guard.create_project(self.FakeApp, "BareName.aedt")
        finally:
            os.chdir(old)

    def test_creates_missing_parent_directories(self):
        target = self.dir / "sub" / "deeper" / "New.aedt"
        app = guard.create_project(self.FakeApp, str(target))
        self.assertEqual(app.project, str(target))
        self.assertTrue((self.dir / "sub" / "deeper").is_dir())

    def test_project_keyword_cannot_silently_override_path(self):
        target = self.dir / "Dup.aedt"
        with self.assertRaisesRegex(TypeError, 'project keyword'):
            guard.create_project(self.FakeApp, str(target), project="ignored")

    def test_pathlike_new_project_is_supported(self):
        target = self.dir / 'New.aedt'
        self.assertEqual(guard.create_project(self.FakeApp, target).project, str(target))

    def test_existing_results_are_not_reused_or_deleted(self):
        target = self.dir / 'New.aedt'
        results = self.dir / 'New.aedtresults'
        results.mkdir()
        evidence = results / 'evidence.txt'
        evidence.write_text('previous simulation', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            guard.create_project(self.FakeApp, target)
        self.assertEqual(evidence.read_text(encoding='utf-8'), 'previous simulation')

    def test_existing_lock_is_not_removed(self):
        target = self.dir / 'New.aedt'
        lock = self.dir / 'New.aedt.lock'
        lock.write_text('another session', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            guard.create_project(self.FakeApp, target)
        self.assertEqual(lock.read_text(encoding='utf-8'), 'another session')

    def test_create_helper_works_with_wrapped_constructor_and_permission_expires(self):
        target = self.dir / 'New.aedt'
        guarded = guard._wrap(self.FakeApp, 'FakeApp')
        self.assertEqual(guard.create_project(guarded, target).project, str(target))
        with self.assertRaisesRegex(RuntimeError, 'missing project path'):
            guarded(project=target)

    def test_create_permission_is_not_given_to_a_different_path(self):
        other = self.dir / 'Unrelated.aedt'
        class NestedApp:
            def __init__(self, project=None):
                guard.resolve_project_argument(other)
        with self.assertRaisesRegex(RuntimeError, 'missing project path'):
            guard.create_project(NestedApp, self.dir / 'New.aedt')
        self.assertIsNone(guard._creation_target.get())

    def test_constructor_exception_does_not_leak_creation_permission(self):
        class FailingApp:
            def __init__(self, project=None):
                raise ValueError('constructor failed')
        target = self.dir / 'New.aedt'
        with self.assertRaisesRegex(ValueError, 'constructor failed'):
            guard.create_project(FailingApp, target)
        with self.assertRaisesRegex(RuntimeError, 'missing project path'):
            guard.resolve_project_argument(target)

    def test_open_helper_never_creates_even_with_legacy_env_option(self):
        with mock.patch.dict(os.environ, {'AEDT_GUARD_ALLOW_CREATE':'1'}):
            with self.assertRaisesRegex(RuntimeError, 'missing or invalid'):
                guard.open_project(self.FakeApp, self.dir / 'Missing.aedt')

    def test_open_helper_uses_existing_absolute_path(self):
        target = self.dir / 'Existing.aedt'
        target.write_text('existing project', encoding='utf-8')
        app = guard.open_project(self.FakeApp, target)
        self.assertEqual(app.project, str(target))
        self.assertEqual(target.read_text(encoding='utf-8'), 'existing project')

    def test_open_intent_does_not_become_create_intent_when_file_disappears(self):
        target = self.dir / 'Existing.aedt'
        target.write_text('existing project', encoding='utf-8')
        class DeletedDuringOpen:
            def __init__(self, project=None):
                target.unlink()
                guard.resolve_project_argument(project)
        with mock.patch.dict(os.environ, {'AEDT_GUARD_ALLOW_CREATE':'1'}):
            with self.assertRaisesRegex(RuntimeError, 'missing project path'):
                guard.open_project(DeletedDuringOpen, target)
        self.assertIsNone(guard._open_target.get())

    def test_broken_symlink_is_not_a_new_project_target(self):
        target = self.dir / 'Broken.aedt'
        try:
            target.symlink_to(self.dir / 'Missing.aedt')
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation not supported by this environment')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            guard.create_project(self.FakeApp, target)


class WrapperTests(unittest.TestCase):
    def test_wrapper_preserves_type_and_rewrites_project(self):
        class Fake:
            def __init__(self, project=None, design=None):
                self.project = project
                self.design = design

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name).resolve()
        existing = directory / "Proj.aedt"
        existing.write_text("x", encoding="utf-8")

        guarded = guard._wrap(Fake, "Fake")
        with mock.patch.dict(os.environ, {"AEDT_GUARD_SEARCH_DIRS": str(directory)}):
            instance = guarded(project="Proj", design="D1")

        self.assertIsInstance(instance, Fake)
        self.assertEqual(instance.project, str(existing))
        self.assertEqual(instance.design, "D1")
        self.assertEqual(guarded.__name__, "Fake")

    def test_wrapper_handles_positional_project(self):
        class Fake:
            def __init__(self, project=None):
                self.project = project

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name).resolve()
        existing = directory / "Proj.aedt"
        existing.write_text("x", encoding="utf-8")

        guarded = guard._wrap(Fake, "Fake")
        with mock.patch.dict(os.environ, {"AEDT_GUARD_SEARCH_DIRS": str(directory)}):
            instance = guarded("Proj")

        self.assertEqual(instance.project, str(existing))


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.core = types.ModuleType('ansys.aedt.core')
        self.aedt = types.ModuleType('ansys.aedt')
        self.ansys = types.ModuleType('ansys')
        self.submodule = types.ModuleType('fake_guard_app')
        class Fake:
            def __init__(self, project=None):
                self.project = project
        Fake.__module__ = self.submodule.__name__
        self.original = Fake
        self.core.Hfss = self.submodule.Hfss = Fake
        self.aedt.core = self.core
        self.ansys.aedt = self.aedt
        patcher = mock.patch.dict(sys.modules, {'ansys':self.ansys, 'ansys.aedt':self.aedt,
                                               'ansys.aedt.core':self.core,
                                               self.submodule.__name__:self.submodule})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repeated_install_is_idempotent_and_populates_new_namespace(self):
        first = {}
        self.assertEqual(guard.install(first), ['Hfss'])
        guarded = self.core.Hfss
        second = {}
        self.assertEqual(guard.install(second), [])
        self.assertIs(self.core.Hfss, guarded)
        self.assertIs(first['Hfss'], second['Hfss'])
        self.assertIs(self.submodule.Hfss, guarded)
        self.assertTrue(issubclass(guarded, self.original))

    def test_import_banner_and_guard_messages_never_reach_stdout(self):
        original_import = builtins.__import__
        def noisy_import(name, *args, **kwargs):
            if name == 'ansys.aedt.core':
                print('fake PyAEDT import banner')
                print('fake import diagnostic', file=sys.stderr)
            return original_import(name, *args, **kwargs)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with mock.patch('builtins.__import__', side_effect=noisy_import):
                guard.install()
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('fake PyAEDT import banner', stderr.getvalue())
        self.assertIn('fake import diagnostic', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
