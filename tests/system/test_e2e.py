#!/usr/bin/env python3
"""
module_name: test_e2e.py
description: End to end tests E2E-01 and E2E-02. A stranger install into a throwaway home under a
             fake user name, then one scenario: make a synthetic ticket, pass the gate for spec, arch,
             dev and qa, build an index and run a search, see one connector report not set up, and
             trigger one hook block. The class also proves the real settings file and the real vault
             folders are the same before and after the whole run.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
usage: bash tests/system/run.sh   (set TOLLGATE_TEST_PYTHON for the search step)
  TOLLGATE_REAL_VAULT  optional path of the owner's real vault. When set, the folders 01-system-map and
                       02-tickets inside it are checksummed before and after the run.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tests", "harness"))

from real_guard import RealStateGuard, file_checksum, folder_checksum  # noqa: E402

FAKE_USER = "e2e_stranger"
TICKET_PREFIX = "tk"
KEY = "TK-001"
TIMEOUT = 120
# Each body is longer than the index minimum chunk length (80 characters), or it is not indexed.
CORPUS = {
    "notes/retry-policy.md": "# Retry policy\n\nFailed jobs are retried three times with a growing backoff delay "
                             "between each attempt. After the third failed attempt an alert is raised for the owner.\n",
    "notes/backup-plan.md": "# Backup plan\n\nThe whole vault folder is copied to a second disk every night at "
                            "two in the morning, and the oldest copy is removed after thirty days.\n",
    "notes/naming-rules.md": "# Naming rules\n\nTables use snake case names and carry the layer name as the first "
                             "word, so a reader can tell raw data from cleaned data at a glance.\n",
}


def clean_env(home, extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("TOLLGATE_")}
    for k in ("CLAUDE_DOTFILES", "CLAUDE_CONFIG_DIR"):
        env.pop(k, None)
    env.update({"HOME": home, "USER": FAKE_USER, "LOGNAME": FAKE_USER, "SHELL": "/bin/zsh",
                "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                "PYTHONDONTWRITEBYTECODE": "1"})
    env["PATH"] = os.path.join(home, "bin") + os.pathsep + env.get("PATH", "")
    if extra:
        env.update(extra)
    return env


class StrangerInstall(unittest.TestCase):
    """One install shared by every scenario step, in a throwaway home."""

    @classmethod
    def setUpClass(cls):
        cls.guard = RealStateGuard(vault_path=None)
        cls.before = cls.guard.record()
        real_vault = os.environ.get("TOLLGATE_REAL_VAULT", "")
        cls.vault_dirs = [os.path.join(real_vault, d) for d in ("01-system-map", "02-tickets")] if real_vault else []
        cls.vault_before = {d: folder_checksum(d) for d in cls.vault_dirs}

        cls.root = tempfile.mkdtemp(prefix="tollgate-e2e-")
        cls.home = os.path.join(cls.root, FAKE_USER)
        os.makedirs(os.path.join(cls.home, "bin"))
        stub = os.path.join(cls.home, "bin", "security")
        with open(stub, "w") as f:
            f.write("#!/bin/sh\necho \"$@\" >> \"%s/security.log\"\n" % cls.home)
        os.chmod(stub, 0o755)
        cls.repo = os.path.join(cls.root, "repo")
        os.makedirs(cls.repo)
        subprocess.run("tar -C %s --exclude=.git --exclude=__pycache__ --exclude=ticket_states -cf - . | tar -C %s -xf -"
                       % (REPO, cls.repo), shell=True, check=True)
        cls.vault = os.path.join(cls.root, "vault")
        cls.install = subprocess.run(
            ["bash", os.path.join(cls.repo, "install.sh"), "--non-interactive", "--name", "Ada Stranger",
             "--vault", cls.vault, "--initials", "as", "--ticket-prefix", TICKET_PREFIX],
            cwd=cls.home, env=clean_env(cls.home), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT)
        settings_path = os.path.join(cls.home, ".claude", "settings.json")
        cls.settings = {}
        if os.path.isfile(settings_path):
            with open(settings_path) as handle:
                cls.settings = json.load(handle)
        cls.env_block = cls.settings.get("env", {})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def env(self, extra=None):
        env = clean_env(self.home, {k: str(v) for k, v in self.env_block.items()})
        env["TOLLGATE_HOME"] = self.repo
        env["TOLLGATE_KNOWLEDGE"] = self.vault
        env["TOLLGATE_NONINTERACTIVE"] = "1"
        if extra:
            env.update(extra)
        return env

    # ---- E2E-01 step 1: the install ----
    def test_01_install_ok(self):
        self.assertEqual(self.install.returncode, 0, self.install.stdout[-800:] + self.install.stderr[-800:])
        self.assertTrue(self.settings.get("hooks"), "settings.json has hooks")
        self.assertIn("TOLLGATE_KNOWLEDGE", self.env_block)
        self.assertNotIn("TOLLGATE_SKILL_PREFIX", self.env_block)
        text = json.dumps(self.settings)
        self.assertIn(self.repo, text, "hooks point into the installed repo copy")
        self.assertNotIn(REPO + "/hooks", text.replace(self.repo, ""), "hooks do not point at the source repo")

    # ---- step 2: synthetic ticket through the gate chain ----
    def put(self, suffix, status):
        d = os.path.join(self.vault, "02-tickets", KEY)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "%s-%s.md" % (KEY, suffix)), "w") as f:
            f.write("# %s %s\nStatus: %s\n" % (KEY, suffix, status))

    def gate(self, skill):
        name = "tg-%s" % skill
        body = json.dumps({"command_name": name, "command_args": KEY, "command_source": "user",
                           "cwd": self.home, "expansion_type": "slash_command",
                           "hook_event_name": "UserPromptExpansion", "prompt": "/%s %s" % (name, KEY)})
        hook = os.path.join(self.repo, "hooks", "pre-prompt-expansion-check-gates.py")
        r = subprocess.run([hook], input=body, capture_output=True, text=True, env=self.env(),
                           timeout=TIMEOUT)
        self.assertEqual(r.returncode, 0, r.stderr)
        return bool(r.stdout.strip()) and json.loads(r.stdout).get("decision") == "block"

    def test_02_gate_chain(self):
        self.put("state", "ROUTED")
        self.assertFalse(self.gate("spec"), "spec is never gated")
        self.assertTrue(self.gate("arch"), "arch blocked before the spec is approved")
        self.put("spec", "APPROVED")
        self.put("state", "SPEC_APPROVED")
        self.assertFalse(self.gate("arch"))
        self.assertTrue(self.gate("dev"), "dev blocked before the design is approved")
        self.put("design", "DESIGN_APPROVED")
        self.put("state", "DESIGN_APPROVED")
        self.assertFalse(self.gate("dev"))
        self.put("state", "DEV_COMPLETE")
        self.assertTrue(self.gate("qa"), "qa blocked while the validation file is missing")
        self.put("edge-case-validation", "DOCUMENTED")
        self.assertFalse(self.gate("qa"))

    # ---- step 3: ticket state check on the same ticket ----
    def test_03_ticket_state_check(self):
        self.put("state", "SPEC_APPROVED")
        r = subprocess.run([sys.executable, "-B", os.path.join(self.repo, "scripts", "state", "ticket_state_check.py"),
                            KEY], capture_output=True, text=True, env=self.env(), timeout=TIMEOUT)
        self.assertIn(r.returncode, (0, 1), r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    # ---- step 4: index and search ----
    def test_04_search(self):
        py = os.environ.get("TOLLGATE_TEST_PYTHON", "")
        if not py or not os.path.isfile(py):
            self.skipTest("set TOLLGATE_TEST_PYTHON to a Python with chromadb")
        for rel, text in CORPUS.items():
            path = os.path.join(self.vault, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        env = self.env({"TOLLGATE_EMBEDDER": "hash"})
        b = subprocess.run([py, "-B", os.path.join(self.repo, "scripts", "search", "build_index.py"),
                            "--full", "--embedder", "hash"], capture_output=True, text=True, env=env,
                           timeout=TIMEOUT * 3)
        self.assertEqual(b.returncode, 0, b.stdout[-600:] + b.stderr[-600:])
        q = subprocess.run([py, "-B", os.path.join(self.repo, "scripts", "search", "query_index.py"),
                            "how often are failed jobs retried", "--top", "3"], capture_output=True, text=True,
                           env=env, timeout=TIMEOUT)
        self.assertEqual(q.returncode, 0, q.stdout[-600:] + q.stderr[-600:])
        self.assertIn("retry-policy", q.stdout)

    # ---- step 5: one connector is off until set up ----
    def test_05_connector_not_set_up(self):
        r = subprocess.run([sys.executable, "-B", os.path.join(self.repo, "scripts", "connectors", "plane", "plane_sync.py"),
                            "drift", KEY], capture_output=True, text=True, env=self.env(), timeout=TIMEOUT)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not set up", r.stdout + r.stderr)

    # ---- step 6: one hook block ----
    def test_06_hook_blocks_a_secret(self):
        fake = "sk-ant-" + "api03-" + "A" * 24 + "B" * 24
        body = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write",
                           "tool_input": {"file_path": os.path.join(self.vault, "notes", "x.md"),
                                          "content": "key = " + fake}})
        r = subprocess.run([os.path.join(self.repo, "hooks", "scrub_secrets.py")], input=body,
                           capture_output=True, text=True, env=self.env(), timeout=TIMEOUT)
        self.assertIn("deny", r.stdout.lower())
        self.assertNotIn(fake, r.stdout + r.stderr, "the secret is never echoed back")

    # ---- E2E-02: isolation. Runs last (name sorts after the others). ----
    def test_zz_real_state_untouched(self):
        self.assertEqual(self.guard.snapshot(), self.before, "real settings.json changed during the run")
        for d, before in self.vault_before.items():
            self.assertEqual(folder_checksum(d), before, "real vault folder changed: %s" % os.path.basename(d))
        self.assertEqual(file_checksum(os.path.join(os.path.expanduser("~"), ".claude", "settings.json")),
                         self.before["settings"])


if __name__ == "__main__":
    unittest.main()
