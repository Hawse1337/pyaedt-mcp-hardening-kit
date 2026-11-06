# -*- coding: utf-8 -*-
"""Resolve PyAEDT project names without implicit, potentially destructive creation.

Existing explicit paths are opened, and bare names are searched in explicitly
configured directories and the current directory. Ambiguous names are refused.
Missing explicit paths are refused by default: intentional creation should use
``create_project(App, absolute_path, ...)``. The legacy
``AEDT_GUARD_ALLOW_CREATE=1`` option also allows missing names/paths, after checks.

``None`` and empty arguments are left to PyAEDT for active-project attachment;
this guard cannot prove which desktop/project PyAEDT selects in that case. Pass
an explicit target and a verified existing project path for reproducible work.
This is an accidental-creation guard, not a filesystem lock, save interceptor or
backup system. Concurrent writers and subsequent save operations remain outside
its protection. Classes imported before ``install()`` are not retroactively
rebound; install before importing application classes.
"""
from __future__ import annotations

import contextvars
import os
import sys

APP_CLASSES = (
    "Hfss", "Maxwell3d", "Maxwell2d", "Icepak", "Q3d", "Q2d", "Circuit",
    "TwinBuilder", "Mechanical", "Emit", "Rmxprt", "Hfss3dLayout",
    "MaxwellCircuit", "Simplorer", "EddyCurrent",
)

# Kept for compatibility with callers that inspected this constant. There are
# deliberately no machine-specific fallback paths in a distributable package.
DEFAULT_SEARCH_DIRS = ()
_LOG_PREFIX = "[aedt-guard] "
_creation_target = contextvars.ContextVar("aedt_guard_creation_target", default=None)
_open_target = contextvars.ContextVar("aedt_guard_open_target", default=None)


def _log(message: str) -> None:
    print(_LOG_PREFIX + message, file=sys.stderr, flush=True)


def _canonical(path) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _identity(path) -> str:
    return os.path.normcase(_canonical(path))


def _search_dirs(dirs=None) -> list[str]:
    if isinstance(dirs, (str, os.PathLike)):
        dirs = [dirs]
    candidates = list(dirs or ())
    candidates.extend(p.strip() for p in os.environ.get("AEDT_GUARD_SEARCH_DIRS", "").split(";") if p.strip())
    candidates.extend(DEFAULT_SEARCH_DIRS)
    candidates.append(os.getcwd())
    seen, output = set(), []
    for directory in candidates:
        canonical = _canonical(directory)
        key = os.path.normcase(canonical)
        if key not in seen:
            seen.add(key)
            output.append(canonical)
    return output


def _project_path_exists(path) -> bool:
    """Accept files and AEDB directories; refuse other directory arguments."""
    return os.path.isfile(path) or (path.lower().endswith(".aedb") and os.path.isdir(path))


def _check_new_target(target) -> None:
    # lexists also catches a dangling symlink, which must not become a new file.
    artifacts = [target, target + ".lock"]
    if target.lower().endswith(".aedt"):
        artifacts.append(target + "results")
    for path in artifacts:
        if os.path.lexists(path):
            raise RuntimeError(
                "create_project refused: %r already exists. Open the verified "
                "existing project or choose a new isolated path; no artifacts "
                "were deleted." % path
            )


def _text_path(value):
    if not isinstance(value, (str, os.PathLike)):
        raise TypeError("project must be a string or PathLike path, got %s" % type(value).__name__)
    text = os.fspath(value)
    if not isinstance(text, str):
        raise TypeError("project path must be text, not bytes")
    text = os.path.expanduser(text.strip())
    if "\x00" in text:
        raise ValueError("project path contains a NUL character")
    drive, _ = os.path.splitdrive(text)
    if drive and not os.path.isabs(text):
        raise ValueError("drive-relative project paths are ambiguous: %r" % text)
    return text


def resolve_project_argument(value, dirs=None):
    """Return a verified existing project path or an explicitly allowed new path.

    Empty/None preserve PyAEDT's active-project behavior. Relative paths with a
    separator are normalized to an absolute path before any constructor runs.
    Bare names must match one unique existing file across all search roots.
    """
    if value is None or value == "":
        return value
    text = _text_path(value)
    if not text:
        return value
    explicit = os.path.isabs(text) or os.sep in text or (os.altsep and os.altsep in text)
    if explicit:
        raw_target = os.path.abspath(text)
        if os.path.lexists(raw_target) and not _project_path_exists(raw_target):
            raise RuntimeError("aedt-guard refused invalid project path %r" % raw_target)
        target = _canonical(text)
        creation_allowed = _creation_target.get() == _identity(target)
        if creation_allowed:
            _check_new_target(target)
            return target
        if _project_path_exists(target):
            return target
        if os.path.lexists(target):
            raise RuntimeError("aedt-guard refused invalid project path %r" % target)
        if os.environ.get("AEDT_GUARD_ALLOW_CREATE") == "1" and _open_target.get() != _identity(target):
            _check_new_target(raw_target)
            _check_new_target(target)
            _log("legacy creation allowed at %r" % target)
            return target
        raise RuntimeError(
            "aedt-guard refused missing project path %r; a typo must not create "
            "an empty project. Use create_project(App, absolute_path, ...) for "
            "intentional creation." % target
        )

    name = text if text.lower().endswith((".aedt", ".aedb")) else text + ".aedt"
    roots = _search_dirs(dirs)
    matches = {}
    for directory in roots:
        candidate = _canonical(os.path.join(directory, name))
        if _project_path_exists(candidate):
            matches[_identity(candidate)] = candidate
    if len(matches) > 1:
        raise RuntimeError(
            "aedt-guard refused ambiguous project name %r: %s. Pass the verified "
            "absolute path." % (value, sorted(matches.values()))
        )
    if matches:
        target = next(iter(matches.values()))
        _log("project %r resolved to existing path %r" % (value, target))
        return target

    if os.environ.get("AEDT_GUARD_ATTACH_OPEN") == "1":
        raise RuntimeError(
            "aedt-guard refused unverified AEDT_GUARD_ATTACH_OPEN for %r; discover "
            "the exact project path in the explicitly targeted desktop and pass "
            "that path instead." % value
        )
    if os.environ.get("AEDT_GUARD_ALLOW_CREATE") == "1":
        raw_target = os.path.join(roots[0], name)
        _check_new_target(raw_target)
        target = _canonical(raw_target)
        _check_new_target(target)
        _log("legacy creation allowed at %r" % target)
        return target
    raise RuntimeError(
        "aedt-guard refused project=%r: no %r found in %s. Implicit creation can "
        "OVERWRITE project data. Pass an existing absolute path or use "
        "create_project(App, absolute_path, ...)." % (value, name, roots)
    )


def create_project(app_class, path, **kwargs):
    """Authorize one NEW absolute .aedt path during this constructor call only.

    Existing files, locks and result directories are never removed or reused.
    The existence check is not atomic against another process creating a file;
    callers must use an isolated location and a single writer.
    """
    text = _text_path(path)
    if not text or not os.path.isabs(text):
        raise ValueError("create_project requires an absolute path, got %r" % path)
    raw_target = text if text.lower().endswith(".aedt") else text + ".aedt"
    _check_new_target(raw_target)
    target = _canonical(raw_target)
    _check_new_target(target)
    if "project" in kwargs:
        raise TypeError("create_project takes its project path as path, not a project keyword")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _check_new_target(target)
    token = _creation_target.set(_identity(target))
    try:
        _log("creating NEW project at %r" % target)
        return app_class(project=target, **kwargs)
    finally:
        _creation_target.reset(token)


def open_project(app_class, path, **kwargs):
    """Open one verified existing absolute project path without allowing creation."""
    text = _text_path(path)
    if not text or not os.path.isabs(text):
        raise ValueError("open_project requires an absolute path, got %r" % path)
    target = _canonical(text)
    if not _project_path_exists(target):
        raise RuntimeError("open_project refused missing or invalid project path %r" % target)
    if "project" in kwargs:
        raise TypeError("open_project takes its project path as path, not a project keyword")
    token = _open_target.set(_identity(target))
    try:
        return app_class(project=target, **kwargs)
    finally:
        _open_target.reset(token)


def _wrap(cls, name):
    """Keep application type behavior while sanitizing keyword/positional paths."""
    class Guarded(cls):
        def __init__(self, *args, **kwargs):
            if "project" in kwargs:
                kwargs["project"] = resolve_project_argument(kwargs["project"])
            elif args:
                args = (resolve_project_argument(args[0]),) + tuple(args[1:])
            super().__init__(*args, **kwargs)

    Guarded.__name__ = name
    Guarded.__qualname__ = name
    Guarded.__module__ = getattr(cls, "__module__", __name__)
    Guarded.__doc__ = getattr(cls, "__doc__", None)
    return Guarded


def install(namespace=None) -> list[str]:
    """Wrap available application classes once; keep all import output off stdout.

    Returns newly wrapped class names. Repeated calls also populate a supplied
    namespace with already guarded classes without adding another wrapper.
    """
    import contextlib
    import io

    captured_out, captured_err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
            import ansys.aedt.core as aedt_core
    except Exception as exc:  # PyAEDT unavailable: no application was constructed.
        _log("PyAEDT not importable, guard not installed: %s" % exc)
        return []
    finally:
        for text in (captured_out.getvalue(), captured_err.getvalue()):
            if text.strip():
                _log("suppressed import output: " + " ".join(text.split())[:400])

    patched, available = [], []
    for name in APP_CLASSES:
        original = getattr(aedt_core, name, None)
        if original is None or not isinstance(original, type):
            continue
        available.append(name)
        if getattr(original, "_aedt_guard_patched", False):
            continue
        guarded = _wrap(original, name)
        guarded._aedt_guard_patched = True
        setattr(aedt_core, name, guarded)
        module = sys.modules.get(getattr(original, "__module__", "") or "")
        if module is not None and getattr(module, name, None) is original:
            setattr(module, name, guarded)
        patched.append(name)
    if isinstance(namespace, dict):
        for name in available:
            namespace[name] = getattr(aedt_core, name)
    _log("installed on %d new class(es): %s" % (len(patched), ", ".join(patched)))
    return patched
