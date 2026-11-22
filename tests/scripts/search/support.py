"""
module_name: support.py
description: Shared helpers for the search tests: paths, a throwaway environment, a synthetic vault, a script runner.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import contextlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SEARCH = ROOT / "scripts" / "search"
CORPUS = ROOT / "tests" / "rag_eval" / "corpus"
GOLDEN = ROOT / "tests" / "rag_eval" / "golden_questions.json"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(SEARCH))
from throwaway_home import throwaway_home  # noqa: E402,F401

try:
    import chromadb  # noqa: F401
    import yaml  # noqa: F401
    HAVE_STORE = True
except ImportError:
    HAVE_STORE = False

NOTE = "Set TOLLGATE_TEST_PYTHON to a python with chromadb and PyYAML."


def script_env(env, **extra):
    out = dict(env)
    out["TOLLGATE_EMBEDDER"] = "hash"
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    out.update(extra)
    return out


def run_script(name, args, env, input_text=None, timeout=300):
    return subprocess.run([sys.executable, "-B", str(SEARCH / name), *args], capture_output=True, text=True,
                          env=env, input=input_text, timeout=timeout)


@contextlib.contextmanager
def in_env(env):
    """Run in-process code with the throwaway environment, then restore the real one."""
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_vault(vault):
    """A small synthetic vault: two notes, one ticket, one conversation note with a dead link."""
    vault = pathlib.Path(vault)
    write(vault / "notes" / "alpha.md",
          "# Alpha\n\nThe nightly load retries twice and then pages the owner. See [[beta]] for the owner list.\n"
          "The retry limit is two and the wait between tries is five minutes for every job in the group.\n")
    write(vault / "notes" / "beta.md",
          "# Beta\n\nOwners rotate weekly. The rotation table lists the person on call for each service area.\n"
          "A dead link here: [[missing-note-one]] and again [[missing-note-one]].\n")
    write(vault / "02-tickets" / "T-001" / "T-001-state.md",
          "# T-001\n\nStatus: IN_DEV\n\nDuplicate rows appeared after a retry because the append was not idempotent.\n"
          "The fix is a merge on the encounter key so a second run changes nothing in the table.\n")
    return vault
