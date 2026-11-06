#!/usr/bin/env python
"""Offline, hash-gated installer. Payload hashes are strict byte hashes.

Declared UTF-8 targets may differ in CRLF/LF only. Every write is staged in a
named backup batch. Caught write failures roll back unchanged destinations;
process death/power loss is not a multi-file atomic transaction.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

for _stream in (sys.stdout,sys.stderr):
    if hasattr(_stream,'reconfigure'):
        _stream.reconfigure(encoding='utf-8',errors='replace')

HERE = str(Path(__file__).resolve().parent)
MANIFEST = os.path.join(HERE, 'manifest.json')
LAST_BATCH = None


def sha256(path):
    return _digest(Path(path).read_bytes())


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _lf_digest(data):
    data.decode('utf-8')
    return _digest(data.replace(b'\r\n', b'\n'))


def load_manifest():
    return json.loads(Path(MANIFEST).read_text(encoding='utf-8'))


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('expected a portable relative path')
    parts = relative.split('/')
    if (ntpath.isabs(relative) or ntpath.splitdrive(relative)[0]
            or any(p in ('', '.', '..') or ':' in p for p in parts)):
        raise ValueError('unsafe relative path: ' + relative)
    root = Path(root).resolve()
    target = root.joinpath(*parts)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):
            raise ValueError('link or junction in target: ' + relative)
    if not target.resolve().is_relative_to(root):
        raise ValueError('path escapes root: ' + relative)
    return target


def verify_payload(manifest):
    errors, seen = [], set()
    try:
        if not isinstance(manifest['files'], dict):
            raise ValueError('files must be an object')
        for target, entry in manifest['files'].items():
            try:
                safe_path(HERE,target)
                if target.casefold() in seen:
                    raise ValueError('duplicate target ignoring case')
                seen.add(target.casefold())
                src = safe_path(HERE,entry['kit_file'])
                expected = entry['installed_sha256']
                if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
                    raise ValueError('invalid SHA256')
                if not src.is_file() or sha256(src) != expected:
                    raise ValueError('payload missing or SHA256 mismatch')
                for value in [entry.get('base_sha256')] + entry.get('compatible_sha256',[]):
                    if value is not None and not re.fullmatch('[0-9a-f]{64}',value):
                        raise ValueError('invalid baseline SHA256')
            except (ValueError,OSError,KeyError,TypeError) as exc:
                errors.append('%s: %s' % (target,exc))
    except (ValueError,KeyError,TypeError) as exc:
        errors.append(str(exc))
    for error in errors:
        print('ERROR: ' + error)
    return not errors


def looks_like_repo(repo):
    return all((Path(repo)/name).is_file() for name in
               ('mcp_server.py','pyaedt_worker.py','pyaedt_capabilities.py'))


def verify_dependencies(manifest,repo):
    for name,allowed in manifest.get('required_files',{}).items():
        try:
            data = safe_path(repo,name).read_bytes()
            if _digest(data) not in allowed and _lf_digest(data) not in allowed:
                raise ValueError('unsupported dependency hash: '+name)
        except (ValueError,OSError,UnicodeError) as exc:
            print('ERROR: %s' % exc)
            return False
    return True


def classify(repo,entry):
    target = safe_path(repo,entry['installed_path'])
    if not target.exists():
        return 'missing',None
    if not target.is_file():
        return 'modified',None
    data = target.read_bytes()
    current = _digest(data)
    installed = entry['installed_sha256']
    bases = {entry.get('base_sha256'),*entry.get('compatible_sha256',[])} - {None}
    if current == installed:
        return 'installed',current
    if current in bases:
        return 'base',current
    if entry.get('text_lf',False):
        try:
            normal = _lf_digest(data)
        except UnicodeError:
            normal = None
        if normal == entry.get('installed_lf_sha256',installed):
            return 'installed',current
        if normal in bases | set(entry.get('compatible_lf_sha256',[])):
            return 'base',current
    return 'modified',current


def do_check(manifest,repo,run_tests=False):
    counts = dict(installed=0,base=0,modified=0,missing=0,missing_required=0)
    for target,entry in manifest['files'].items():
        state,_ = classify(repo,dict(entry,installed_path=target))
        counts[state] += 1
        if state == 'missing' and not entry.get('new_file',False):
            counts['missing_required'] += 1
        print('  %-46s %s' % (target,state))
    counts['tests_ok'] = run_test_suite(repo,manifest) if run_tests else True
    return counts


def run_test_suite(repo,manifest):
    modules = manifest.get('tests',[])
    if not modules:
        return True
    try:
        result = subprocess.run([sys.executable,'-B','-m','unittest',*modules],cwd=repo,
                                capture_output=True,text=True,encoding='utf-8',errors='replace',
                                timeout=180,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    except (OSError,subprocess.TimeoutExpired) as exc:
        print('Tests failed: %s' % exc)
        return False
    print((result.stdout+result.stderr).strip())
    return result.returncode == 0


def _atomic_write(path,data):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp = tempfile.mkstemp(prefix='.hardening-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def install_lock(repo):
    lock = safe_path(repo,'.aedt-hardening-install.lock')
    fd = os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(json.dumps({'pid':os.getpid(),'created_utc':datetime.now(timezone.utc).isoformat()}))
        yield
    finally:
        lock.unlink()


def _snapshot(path):
    if path.exists() and not path.is_file():
        raise ValueError('target is not a regular file: %s' % path)
    return path.read_bytes() if path.exists() else None


def _pyproject_bytes(repo,pin_pyaedt):
    path = safe_path(repo,'pyproject.toml')
    original = path.read_bytes()
    text = original.decode('utf-8')
    match = re.search(r'(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)',text)
    if not match:
        raise ValueError('pyproject.toml: missing [project]')
    block = match.group(1)
    deps = re.search(r'(?ms)^dependencies\s*=\s*\[(.*?)\]',block)
    if not deps:
        raise ValueError('pyproject.toml: no recognised dependency list')
    dep_text = deps.group(1)
    mcp = re.compile(r'(?m)^(\s*)([\'\"])mcp>=1\.0(?:,<2)?\2(\s*,?\s*(?:#.*)?)$')
    dep_text,count = mcp.subn(lambda m:m.group(1)+m.group(2)+'mcp>=1.0,<2'+m.group(2)+m.group(3),dep_text)
    if count != 1:
        raise ValueError('unrecognised/ambiguous mcp requirement; merge manually')
    if pin_pyaedt:
        pat = re.compile(r'(?m)^(\s*)([\'\"])pyaedt==[0-9][^\'\"\r\n]*\2(\s*,?\s*(?:#.*)?)$')
        dep_text,count = pat.subn(lambda m:m.group(1)+m.group(2)+'pyaedt==1.9.0'+m.group(2)+m.group(3),dep_text)
        if count != 1:
            raise ValueError('unrecognised/ambiguous pyaedt pin; merge manually')
    new_block = block[:deps.start(1)]+dep_text+block[deps.end(1):]
    updated = text[:match.start(1)]+new_block+text[match.end(1):]
    module_list = re.search(r'(?ms)^\[tool\.setuptools\]\s*\n.*?^py-modules\s*=\s*\[(.*?)\]',updated)
    if not module_list:
        raise ValueError('missing or unrecognised setuptools py-modules list; merge manually')
    modules = module_list.group(1)
    for module in ('aedt_project_guard','solve_evidence'):
        if not re.search(r'[\'\"]'+module+r'[\'\"]',modules):
            modules += '\n    "'+module+'",\n'
    updated = updated[:module_list.start(1)]+modules+updated[module_list.end(1):]
    return original,updated.encode('utf-8')


def do_pyproject(repo,pin_pyaedt=False,dry=False):
    try:
        before,after = _pyproject_bytes(repo,pin_pyaedt)
        if not dry and before != after:
            raise ValueError('use --install --pyproject to share the install batch')
        print('pyproject.toml: '+('would change' if before != after else 'already configured'))
        return True
    except (ValueError,OSError,UnicodeError) as exc:
        print('ERROR: %s' % exc)
        return False


def do_install(manifest,repo,force=False,*,pyproject=False,pin_pyaedt=False):
    global LAST_BATCH
    LAST_BATCH = None
    if force or not verify_payload(manifest):
        print('ERROR: force disabled or invalid payload')
        return False
    repo = Path(repo).resolve()
    plans,written = [],[]
    batch_dir = None
    try:
        with install_lock(repo):
            if not verify_dependencies(manifest,repo):
                return False
            if not pyproject and manifest.get('required_py_modules'):
                config = safe_path(repo,'pyproject.toml').read_text(encoding='utf-8')
                modules = re.search(r'(?ms)^\[tool\.setuptools\]\s*\n.*?^py-modules\s*=\s*\[(.*?)\]',config)
                if modules is None or any(not re.search(r'[\'\"]'+re.escape(name)+r'[\'\"]',modules.group(1))
                                          for name in manifest['required_py_modules']):
                    raise ValueError('new modules must be packaged; rerun with --pyproject after review')
            for target,entry in manifest['files'].items():
                dst = safe_path(repo,target)
                state,_ = classify(repo,dict(entry,installed_path=target))
                if state == 'modified' or (state == 'missing' and not entry.get('new_file',False)):
                    raise ValueError('incompatible or missing required target: '+target)
                if state != 'installed':
                    payload = safe_path(HERE,entry['kit_file']).read_bytes()
                    if _digest(payload) != entry['installed_sha256']:
                        raise ValueError('payload changed during preflight: '+target)
                    plans.append((target,_snapshot(dst),payload))
            if pyproject:
                before,after = _pyproject_bytes(repo,pin_pyaedt)
                if before != after:
                    plans.append(('pyproject.toml',before,after))
            if not plans:
                print('Already installed; nothing written')
                return True
            batch = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:12]
            batch_dir = safe_path(repo,'.aedt-hardening-backups/'+batch)
            batch_dir.mkdir(parents=True,exist_ok=False)
            journal = {'version':manifest.get('version'),'repo':str(repo),'batch':batch,'status':'prepared','files':[]}
            for target,before,after in plans:
                journal['files'].append({'path':target,'before_sha256':_digest(before) if before is not None else None,'after_sha256':_digest(after)})
                if before is not None:
                    backup_path = safe_path(batch_dir,'before/'+target)
                    backup_path.parent.mkdir(parents=True,exist_ok=True)
                    backup_path.write_bytes(before)
            _atomic_write(batch_dir/'journal.json',(json.dumps(journal,indent=2)+'\n').encode('utf-8'))
            try:
                for target,before,after in plans:
                    dst = safe_path(repo,target)
                    if _snapshot(dst) != before:
                        raise ValueError('target changed after preflight: '+target)
                    _atomic_write(dst,after)
                    written.append((target,before,after))
                journal['status'] = 'installed'
            except Exception:
                conflicts = []
                for target,before,after in reversed(written):
                    try:
                        dst = safe_path(repo,target)
                        if _snapshot(dst) != after:
                            conflicts.append(target)
                        elif before is None:
                            dst.unlink()
                        else:
                            _atomic_write(dst,before)
                    except (OSError,ValueError):
                        conflicts.append(target)
                journal['status'] = 'rollback_incomplete' if conflicts else 'rolled_back'
                journal['rollback_conflicts'] = conflicts
                raise
            finally:
                _atomic_write(batch_dir/'journal.json',(json.dumps(journal,indent=2)+'\n').encode('utf-8'))
                LAST_BATCH = str(batch_dir)
        print('Installed %d files; batch: %s' % (len(plans),batch_dir))
        return True
    except (ValueError,OSError,UnicodeError) as exc:
        print('ERROR: %s' % exc)
        if batch_dir:
            print('Inspect batch journal: %s' % (batch_dir/'journal.json'))
        return False


def main():
    parser = argparse.ArgumentParser(description='PyAEDT-MCP reviewed hardening kit installer')
    parser.add_argument('--repo',default=os.environ.get('PYAEDT_MCP_REPO',''))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check',action='store_true')
    group.add_argument('--install',action='store_true')
    group.add_argument('--revert',action='store_true',help='disabled; review a named backup batch')
    parser.add_argument('--force',action='store_true',help='disabled')
    parser.add_argument('--tests',action='store_true')
    parser.add_argument('--pyproject',action='store_true')
    parser.add_argument('--pyaedt',action='store_true')
    args = parser.parse_args()
    if args.force or args.revert:
        print('ERROR: --force/--revert disabled; review differences and batch backups')
        return 1
    if args.pyaedt and not args.pyproject:
        parser.error('--pyaedt requires --pyproject')
    try:
        manifest = load_manifest()
        repo = str(Path(args.repo or os.getcwd()).resolve())
        print('PyAEDT-MCP hardening kit v%s' % manifest['version'])
        if not looks_like_repo(repo):
            print('ERROR: not a complete target repository: '+repo)
            return 2
        if not verify_payload(manifest):
            return 1
        if not verify_dependencies(manifest,repo):
            return 1
        if args.install:
            if not do_install(manifest,repo,pyproject=args.pyproject,pin_pyaedt=args.pyaedt):
                return 1
            counts = do_check(manifest,repo,run_tests=True)
            if counts['base'] or counts['missing'] or counts['modified'] or not counts['tests_ok']:
                print('ERROR: post-install verification failed; inspect batch %s' % LAST_BATCH)
                return 1
            print('Verified. Restart the intended MCP service after its work is idle.')
            return 0
        counts = do_check(manifest,repo,run_tests=args.tests)
        py_ok = do_pyproject(repo,pin_pyaedt=args.pyaedt,dry=True) if args.pyproject else True
        print('Check only; no project or service changed.')
        return 0 if counts['tests_ok'] and py_ok and not counts['modified'] and not counts['missing_required'] else 1
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: %s' % exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
