#!/usr/bin/env python3
"""Throwaway HOME factory for Tollgate tests.

Makes a temp HOME under a fake user name that is not the real user, runs a
command with HOME and every TOLLGATE_* variable pointed there, then cleans up.
"""
import contextlib
import getpass
import os
import shutil
import subprocess
import tempfile

FAKE_USER = "tgtester"
# TOLLGATE_HOME is the repo root (see docs/variables.md), not a folder in the throwaway home.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fake_user_name():
    """A fake user name guaranteed to differ from the real user."""
    real = getpass.getuser()
    name = FAKE_USER
    while name == real:
        name += "x"
    return name


def tollgate_env(home, base=None):
    """Return an env dict: real TOLLGATE_* removed, new ones pointed at home."""
    env = dict(base if base is not None else os.environ)
    for key in list(env):
        if key.startswith("TOLLGATE_"):
            del env[key]
    env["HOME"] = home
    env["USER"] = env["LOGNAME"] = os.path.basename(home)
    env["TOLLGATE_KNOWLEDGE"] = os.path.join(home, "vault")
    env["TOLLGATE_CODE_DIR"] = os.path.join(home, "code")
    env["TOLLGATE_STATE_DIR"] = os.path.join(home, ".tollgate", "state")
    env["TOLLGATE_CONFIG"] = os.path.join(home, ".claude", "tollgate-config")
    env["TOLLGATE_HOME"] = REPO_ROOT
    env["TOLLGATE_PATHS"] = os.path.join(home, ".tollgate", "paths.yaml")
    env["TOLLGATE_CONNECTORS"] = os.path.join(home, ".tollgate", "connectors")
    env["TOLLGATE_GATE_LOG"] = os.path.join(home, ".tollgate", "gate.log")
    env["TOLLGATE_NONINTERACTIVE"] = "1"
    return env


@contextlib.contextmanager
def throwaway_home(keep=False):
    """Yield (home_path, env). Home is <tmp>/<fake user>. Removed on exit."""
    root = tempfile.mkdtemp(prefix="tollgate-test-")
    home = os.path.join(root, fake_user_name())
    for sub in ("vault", "code", ".claude", ".tollgate/state"):
        os.makedirs(os.path.join(home, sub))
    try:
        yield home, tollgate_env(home)
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)


def run_in_home(cmd, input_text=None, timeout=60, extra_env=None):
    """Run cmd (list) in a throwaway home. Returns (CompletedProcess, home)."""
    with throwaway_home() as (home, env):
        if extra_env:
            env.update(extra_env)
        proc = subprocess.run(cmd, input=input_text, capture_output=True,
                              text=True, timeout=timeout, env=env, cwd=home)
        return proc, home
