# Module:      minipytest.py
# Description: A small stand-in for the parts of pytest the state script tests use, so the
#              tests run with the standard library only (pytest is not installed). It gives
#              fixtures (function, class and module scope), parametrize, raises, skip, fail,
#              and the tmp_path, monkeypatch, capsys and caplog helpers.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# ChangeLog:
#   Initial version
"""A tiny pytest look-alike. The test files import it as `pytest`.

The bridge in test_pytest_bridge.py finds the tests and runs each one as a unittest case.
"""
import contextlib
import functools
import inspect
import io
import itertools
import logging
import os
import re
import shutil
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path


# ---------------------------------------------------------------- markers and helpers

class _Param:
    def __init__(self, values, id=None):
        self.values = values
        self.id = id


def param(*values, id=None):
    return _Param(values, id)


def skip(reason=""):
    raise unittest.SkipTest(reason)


def fail(reason="", pytrace=True):
    raise AssertionError(reason)


class _Mark:
    def parametrize(self, argnames, argvalues, ids=None):
        def deco(fn):
            fn.__dict__.setdefault("_mp_params", []).append((argnames, list(argvalues), ids))
            return fn
        return deco

    def skipif(self, condition, reason=""):
        def deco(fn):
            fn.__dict__.setdefault("_mp_skips", []).append((condition, reason))
            return fn
        return deco

    def __getattr__(self, name):
        def deco_factory(*args, **kwargs):
            def deco(fn):
                return fn
            return deco
        return deco_factory


mark = _Mark()


def fixture(fn=None, scope="function", autouse=False, **_kwargs):
    def deco(f):
        f._mp_fixture = {"scope": scope, "autouse": autouse}
        return f
    if fn is not None and callable(fn):
        return deco(fn)
    return deco


class ExceptionInfo:
    def __init__(self):
        self.value = None
        self.type = None


@contextlib.contextmanager
def raises(expected, match=None):
    info = ExceptionInfo()
    try:
        yield info
    except expected as exc:
        info.value = exc
        info.type = type(exc)
        if match is not None and not re.search(match, str(exc)):
            raise AssertionError("exception text %r does not match %r" % (str(exc), match))
        return
    raise AssertionError("did not raise %r" % (expected,))


# ---------------------------------------------------------------- built-in fixtures

class MonkeyPatch:
    _MISSING = object()

    def __init__(self):
        self._undo = []

    @classmethod
    @contextlib.contextmanager
    def context(cls):
        mp = cls()
        try:
            yield mp
        finally:
            mp.undo()

    def setattr(self, target, name, value=_MISSING, raising=True):
        if value is self._MISSING:
            raise TypeError("string targets are not supported")
        old = getattr(target, name, self._MISSING)
        if raising and old is self._MISSING:
            raise AttributeError(name)
        self._undo.append(("attr", target, name, old))
        setattr(target, name, value)

    def delattr(self, target, name, raising=True):
        old = getattr(target, name, self._MISSING)
        if old is self._MISSING:
            if raising:
                raise AttributeError(name)
            return
        self._undo.append(("attr", target, name, old))
        delattr(target, name)

    def setitem(self, mapping, key, value):
        self._undo.append(("item", mapping, key, mapping.get(key, self._MISSING)))
        mapping[key] = value

    def delitem(self, mapping, key, raising=True):
        if key not in mapping:
            if raising:
                raise KeyError(key)
            return
        self._undo.append(("item", mapping, key, mapping[key]))
        del mapping[key]

    def setenv(self, name, value, prepend=None):
        self.setitem(os.environ, name, str(value))

    def delenv(self, name, raising=True):
        self.delitem(os.environ, name, raising=raising)

    def chdir(self, path):
        self._undo.append(("cwd", os.getcwd()))
        os.chdir(str(path))

    def syspath_prepend(self, path):
        self._undo.append(("syspath", list(sys.path)))
        sys.path.insert(0, str(path))

    def undo(self):
        while self._undo:
            entry = self._undo.pop()
            kind = entry[0]
            if kind == "attr":
                _, target, name, old = entry
                if old is self._MISSING:
                    if hasattr(target, name):
                        delattr(target, name)
                else:
                    setattr(target, name, old)
            elif kind == "item":
                _, mapping, key, old = entry
                if old is self._MISSING:
                    mapping.pop(key, None)
                else:
                    mapping[key] = old
            elif kind == "cwd":
                os.chdir(entry[1])
            elif kind == "syspath":
                sys.path[:] = entry[1]


_Out = namedtuple("CaptureResult", "out err")


class CaptureFixture:
    def __init__(self):
        self._out = io.StringIO()
        self._err = io.StringIO()
        self._old = (sys.stdout, sys.stderr)
        sys.stdout, sys.stderr = self._out, self._err

    def __class_getitem__(cls, item):
        return cls

    def readouterr(self):
        out, err = self._out.getvalue(), self._err.getvalue()
        self._out.seek(0)
        self._out.truncate()
        self._err.seek(0)
        self._err.truncate()
        return _Out(out, err)

    def close(self):
        sys.stdout, sys.stderr = self._old


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=0)
        self.records = []
        self.setFormatter(logging.Formatter(
            "%(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s"))

    def emit(self, record):
        self.records.append(record)


class LogCaptureFixture:
    def __init__(self):
        self.handler = _ListHandler()
        self._root = logging.getLogger()
        self._root.addHandler(self.handler)
        self._saved = []

    @property
    def records(self):
        return self.handler.records

    @property
    def text(self):
        return "\n".join(self.handler.format(r) for r in self.handler.records) + "\n" \
            if self.handler.records else ""

    @property
    def messages(self):
        return [r.getMessage() for r in self.handler.records]

    @property
    def record_tuples(self):
        return [(r.name, r.levelno, r.getMessage()) for r in self.handler.records]

    def clear(self):
        self.handler.records.clear()

    def set_level(self, level, logger=None):
        target = logging.getLogger(logger)
        self._saved.append((target, target.level))
        target.setLevel(level)

    @contextlib.contextmanager
    def at_level(self, level, logger=None):
        target = logging.getLogger(logger)
        old = target.level
        target.setLevel(level)
        try:
            yield
        finally:
            target.setLevel(old)

    def close(self):
        self._root.removeHandler(self.handler)
        for target, level in reversed(self._saved):
            target.setLevel(level)


class TempPathFactory:
    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix="minipytest-"))
        self._count = 0

    def mktemp(self, name, numbered=True):
        self._count += 1
        path = self.base / ("%s%d" % (name, self._count))
        path.mkdir(parents=True)
        return path

    def close(self):
        shutil.rmtree(self.base, ignore_errors=True)


# ---------------------------------------------------------------- runner

_BUILTIN = {"tmp_path", "monkeypatch", "capsys", "caplog", "tmp_path_factory"}


class Scope:
    """Holds fixture values for one scope and tears them down."""

    def __init__(self):
        self.values = {}
        self.stack = contextlib.ExitStack()

    def close(self):
        self.stack.close()


class Session:
    """One per process: the temp factory is shared by every test."""
    factory = None

    @classmethod
    def get_factory(cls):
        if cls.factory is None:
            cls.factory = TempPathFactory()
            import atexit
            atexit.register(cls.factory.close)
        return cls.factory


def _fixtures_in(module):
    found = {}
    for name, obj in vars(module).items():
        if callable(obj) and hasattr(obj, "_mp_fixture"):
            found[name] = obj
    return found


def _arg_names(fn, skip_self=True):
    names = list(inspect.signature(fn).parameters)
    if skip_self and names and names[0] == "self":
        names = names[1:]
    return names


def _resolve(name, fixtures, scopes, function_scope, factory):
    """Return the value of fixture `name`. scopes maps scope name to a Scope."""
    if name in function_scope.values:
        return function_scope.values[name]
    if name in fixtures:
        fx = fixtures[name]
        scope_name = fx._mp_fixture["scope"]
        scope = scopes.get(scope_name, function_scope)
        if name in scope.values:
            return scope.values[name]
        kwargs = {a: _resolve(a, fixtures, scopes, function_scope, factory)
                  for a in _arg_names(fx, skip_self=False)}
        result = fx(**kwargs)
        if inspect.isgenerator(result):
            gen = result
            value = next(gen)

            def _finish(gen=gen):
                try:
                    next(gen)
                except StopIteration:
                    pass
            scope.stack.callback(_finish)
        else:
            value = result
        scope.values[name] = value
        return value
    if name == "tmp_path_factory":
        value = factory
    elif name == "tmp_path":
        value = factory.mktemp("t")
    elif name == "monkeypatch":
        value = MonkeyPatch()
        function_scope.stack.callback(value.undo)
    elif name == "capsys":
        value = CaptureFixture()
        function_scope.stack.callback(value.close)
    elif name == "caplog":
        value = LogCaptureFixture()
        function_scope.stack.callback(value.close)
    else:
        raise LookupError("unknown fixture: %s" % name)
    function_scope.values[name] = value
    return value


def collect(module):
    """Yield (class_or_None, function, param_id, param_kwargs) for every test in a module."""
    items = []
    for name, obj in sorted(vars(module).items(), key=lambda kv: _lineno(kv[1])):
        if inspect.isfunction(obj) and name.startswith("test") and obj.__module__ == module.__name__:
            items.append((None, obj))
        elif inspect.isclass(obj) and name.startswith("Test") and obj.__module__ == module.__name__:
            for mname, meth in vars(obj).items():
                if inspect.isfunction(meth) and mname.startswith("test"):
                    items.append((obj, meth))
    out = []
    for cls, fn in items:
        for pid, kwargs in expand_params(fn):
            out.append((cls, fn, pid, kwargs))
    return out


def _lineno(obj):
    try:
        return inspect.getsourcelines(obj)[1]
    except (OSError, TypeError):
        return 0


def expand_params(fn):
    specs = getattr(fn, "_mp_params", [])
    if not specs:
        return [("", {})]
    axes = []
    for argnames, values, ids in specs:
        names = [n.strip() for n in argnames.split(",")] if isinstance(argnames, str) else list(argnames)
        axis = []
        for i, val in enumerate(values):
            pid = None
            if isinstance(val, _Param):
                vals, pid = list(val.values), val.id
            elif len(names) == 1:
                vals = [val]
            else:
                vals = list(val)
            if pid is None and ids is not None:
                pid = ids[i] if not callable(ids) else ids(vals[0])
            if pid is None:
                pid = "-".join(_idpart(v) for v in vals) if all(
                    isinstance(v, (str, int, float, bool, type(None))) for v in vals) else "p%d" % i
            axis.append((str(pid), dict(zip(names, vals))))
        axes.append(axis)
    combos = []
    for combo in itertools.product(*axes):
        kwargs = {}
        for _, kw in combo:
            kwargs.update(kw)
        combos.append(("-".join(c[0] for c in combo), kwargs))
    return combos


def _idpart(v):
    return re.sub(r"\W+", "_", str(v))[:40] or "empty"


def run_one(module, cls, fn, kwargs, module_scope, class_scope, fixtures):
    for cond, reason in getattr(fn, "_mp_skips", []):
        if cond:
            raise unittest.SkipTest(reason)
    factory = Session.get_factory()
    function_scope = Scope()
    scopes = {"module": module_scope, "class": class_scope or module_scope,
              "function": function_scope, "session": module_scope}
    try:
        for name, fx in fixtures.items():
            if fx._mp_fixture["autouse"]:
                _resolve(name, fixtures, scopes, function_scope, factory)
        call = {}
        for a in _arg_names(fn):
            if a in kwargs:
                call[a] = kwargs[a]
            else:
                call[a] = _resolve(a, fixtures, scopes, function_scope, factory)
        if cls is not None:
            instance = cls()
            fn(instance, **call)
        else:
            fn(**call)
    finally:
        function_scope.close()


def make_cases(module):
    """Build unittest TestCase classes for every test in `module`."""
    fixtures = _fixtures_in(module)
    module_scope = Scope()
    import atexit
    atexit.register(module_scope.close)
    groups = {}
    for cls, fn, pid, kwargs in collect(module):
        groups.setdefault(cls, []).append((fn, pid, kwargs))
    cases = []
    for cls, entries in groups.items():
        class_scope = Scope() if cls is not None else None
        attrs = {}
        counter = {}
        for fn, pid, kwargs in entries:
            name = "test_" + fn.__name__.replace("test_", "", 1) if fn.__name__.startswith("test_") else fn.__name__
            if pid:
                name += "[" + pid + "]"
            counter[name] = counter.get(name, 0) + 1
            if counter[name] > 1:
                name += "#%d" % counter[name]

            def runner(self, fn=fn, kwargs=kwargs, cls=cls, class_scope=class_scope):
                run_one(module, cls, fn, kwargs, module_scope, class_scope, fixtures)
            attrs[name] = runner

        def tearDownClass(klass, class_scope=class_scope):
            if class_scope is not None:
                class_scope.close()
        attrs["tearDownClass"] = classmethod(tearDownClass)
        label = module.__name__ + ("." + cls.__name__ if cls else "")
        case = type("Bridge_" + re.sub(r"\W", "_", label), (unittest.TestCase,), attrs)
        case.__module__ = module.__name__
        cases.append(case)
    return cases
