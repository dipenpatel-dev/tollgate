"""Command file tests CMD-01 to CMD-05 (stdlib unittest).

Run: bash tests/commands/run.sh
Env: TOLLGATE_REQUIRE_SCRIPTS=1 makes every `$TOLLGATE_HOME/scripts/...` path a
required file (default: reported only).

Scope of CMD-01 to CMD-03: the commands in WAVE2 that exist in commands/.
Other command files are checked too, but a failure there is only an error if
the file is not listed in KNOWN_GAPS (commands with a known gap).
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CMD_DIR = os.path.join(ROOT, "commands")

WAVE2 = [
    "tg-spec", "tg-arch", "tg-dev", "tg-qa", "tg-support", "tg-ticket", "tg-explain",
    "tg-influence", "tg-devops", "tg-sre", "tg-terraform", "tg-doc-gen", "tg-retrieve",
    "tg-sweep", "tg-think-calibrate", "tg-pr-review",
]

# Every shipped command, exactly. Each file name carries the fixed `tg-` prefix.
ALL_COMMANDS = [
    "tg-arch", "tg-close", "tg-dev", "tg-devops", "tg-doc-gen", "tg-draft", "tg-explain",
    "tg-explore", "tg-handoff", "tg-influence", "tg-learn", "tg-pr-review", "tg-pull-notes",
    "tg-qa", "tg-retrieve", "tg-save", "tg-spec", "tg-sre", "tg-start", "tg-status",
    "tg-support", "tg-sweep", "tg-sync", "tg-terraform", "tg-think-calibrate", "tg-ticket",
    "tg-weekly", "tg-whiteboard",
]

# Commands outside the main list that are allowed to fail CMD-01 to CMD-03.
# Empty today. A command that fails and is not named here fails the run.
KNOWN_GAPS = set()

GENERIC_NAMES = {"user", "you", "runner", "shared", "tgtester", "name", "yourname", "me"}
REPO_AREAS = "hooks|standards|docs|scripts|templates|commands|memory|rag|tools|tests"

PERSONAL_PATH = re.compile(r"(?:/Users|/home)/([A-Za-z0-9._-]+)|/Volumes/[A-Za-z0-9._-]+")
PATH_REF = re.compile(
    r"(?<![\w./}$-])(?:(\$CLAUDE_DOTFILES|\$TOLLGATE_HOME)/)?"
    r"((?:%s)/[A-Za-z0-9_./-]*[A-Za-z0-9_])" % REPO_AREAS)
VAR_REF = re.compile(r"\$\{?(TOLLGATE_[A-Z0-9_]+|CLAUDE_DOTFILES)\}?")
PLACEHOLDER = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def command_files():
    if not os.path.isdir(CMD_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(CMD_DIR) if f.endswith(".md"))


def wave2_present():
    present = command_files()
    return [n for n in WAVE2 if n in present]


def other_files():
    return [n for n in command_files() if n not in WAVE2]


def text_of(name):
    return read(os.path.join(CMD_DIR, name + ".md"))


# ---- rule checks: each returns a list of problem strings ----

def check_cmd01(name):
    problems = []
    for no, line in enumerate(text_of(name).splitlines(), 1):
        for m in PERSONAL_PATH.finditer(line):
            who = m.group(1)
            if who is not None and who.lower() in GENERIC_NAMES:
                continue
            problems.append("%s.md:%d personal absolute path" % (name, no))
    return problems


def collect_paths(name):
    """Return (repo_files, script_files) as lists of (relative path, line)."""
    repo, scripts = [], []
    for no, line in enumerate(text_of(name).splitlines(), 1):
        for m in PATH_REF.finditer(line):
            rel = m.group(2)
            if re.search(r"[{}*<>\[\]]", rel) or rel.endswith("/"):
                continue
            if "." not in rel.rsplit("/", 1)[-1]:
                continue
            if rel.startswith("scripts/"):
                scripts.append((rel, no))
            else:
                repo.append((rel, no))
    return repo, scripts


def check_cmd02(name, require_scripts):
    problems = []
    repo, scripts = collect_paths(name)
    for rel, no in repo:
        if not os.path.exists(os.path.join(ROOT, rel)):
            problems.append("%s.md:%d missing repo file %s" % (name, no, rel))
    if require_scripts:
        for rel, no in scripts:
            if not os.path.exists(os.path.join(ROOT, rel)):
                problems.append("%s.md:%d missing script %s" % (name, no, rel))
    return problems


def defined_names():
    text = read(os.path.join(ROOT, "docs", "variables.md"))
    names = set(re.findall(r"`\$?\{?([A-Z][A-Z0-9_]+)\}?`", text))
    names |= set(re.findall(r"\b(TOLLGATE_[A-Z0-9_]+|CLAUDE_DOTFILES)\b", text))
    placeholders = set(re.findall(r"\{([A-Za-z][A-Za-z0-9_]*)\}", text))
    return names, placeholders


FILL_IN_UPPER = {"N", "NN", "TOTAL"}
FILL_IN_LOWER = re.compile(r"^[a-z0-9_]+(?:_NN)?$")


def placeholder_ok(word, defined):
    """A brace marker passes if defined, lower case/digits/underscore, or N, NN, TOTAL."""
    return word in defined or word in FILL_IN_UPPER or bool(FILL_IN_LOWER.match(word))


def check_cmd03(name):
    problems = []
    names, placeholders = defined_names()
    text = text_of(name)
    for no, line in enumerate(text.splitlines(), 1):
        for m in VAR_REF.finditer(line):
            if m.group(1) not in names:
                problems.append("%s.md:%d undefined variable %s" % (name, no, m.group(1)))
        for m in PLACEHOLDER.finditer(line):
            if not placeholder_ok(m.group(1), placeholders):
                problems.append("%s.md:%d undefined placeholder {%s}" % (name, no, m.group(1)))
    return problems


# ---- CMD-05 constants from the gate ----

def load_gate_rules():
    path = os.path.join(ROOT, "hooks", "gate_rules.py")
    spec = importlib.util.spec_from_file_location("gate_rules_for_cmd_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def cmd05_requirements(g):
    """command -> list of (label, accepted words). Any one word of a group is enough."""
    return {
        "tg-spec": [("spec status", [g.SPEC_APPROVED_STATUS]), ("spec state", [g.STATE_SPEC_APPROVED])],
        "tg-arch": [
            ("design drafting status", ["DESIGN_COMPLETE"]),
            ("design approved status", [g.DESIGN_APPROVED_STATUS]),
            ("design approved state", [g.STATE_DESIGN_APPROVED]),
        ],
        "tg-dev": [("in-dev state", [g.STATE_IN_DEV]), ("dev-complete state", [g.STATE_DEV_COMPLETE])],
        "tg-qa": [("validation status", list(g.VALIDATION_STATUSES))],
    }


def word_on_status_line(text, word):
    """The word sits on a line that names a status or a state (the write step)."""
    rx = re.compile(r"\b%s\b" % re.escape(word))
    for line in text.splitlines():
        if rx.search(line) and re.search(r"(?i)status|state", line):
            return True
    return False


def check_cmd05(name, g):
    problems = []
    text = text_of(name)
    for label, words in cmd05_requirements(g)[name]:
        if not any(word_on_status_line(text, w) for w in words):
            problems.append("%s.md: %s: none of %s on a status or state line" % (name, label, "/".join(words)))
    return problems


# ---- CMD-04 via the leak scanner ----

def scan_folder(folder):
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(folder, "LICENSE"))
    scanner = os.path.join(ROOT, "tests", "leak", "scan_leaks.py")
    env = dict(os.environ)
    env.pop("TOLLGATE_DENYLIST", None)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("# empty\n")
        empty = fh.name
    try:
        p = subprocess.run([sys.executable, "-B", scanner, folder, "--denylist", empty],
                           capture_output=True, text=True, env=env)
    finally:
        os.unlink(empty)
    return p.returncode, p.stdout + p.stderr


class TestCmd01(unittest.TestCase):
    def test_no_personal_path_wave2(self):
        problems = [p for n in wave2_present() for p in check_cmd01(n)]
        self.assertEqual(problems, [])

    def test_detector_flags_personal_path(self):
        self.assertTrue(PERSONAL_PATH.search("/Users/someone/x"))
        self.assertTrue(PERSONAL_PATH.search("/home/someone/x"))


class TestCmd02(unittest.TestCase):
    def test_repo_files_exist_wave2(self):
        require = os.environ.get("TOLLGATE_REQUIRE_SCRIPTS") == "1"
        problems = [p for n in wave2_present() for p in check_cmd02(n, require)]
        self.assertEqual(problems, [])

    def test_script_paths_reported(self):
        found = {}
        for n in wave2_present():
            for rel, _ in collect_paths(n)[1]:
                found.setdefault(rel, set()).add(n)
        missing = sorted(r for r in found if not os.path.exists(os.path.join(ROOT, r)))
        sys.stderr.write("\nCMD-02 script paths used: %d, not yet built: %d\n" % (len(found), len(missing)))
        for r in missing:
            sys.stderr.write("  %s  (%s)\n" % (r, ", ".join(sorted(found[r]))))

    def test_detector_finds_paths(self):
        self.assertEqual(PATH_REF.search("`$TOLLGATE_HOME/scripts/a/b.py`").group(2), "scripts/a/b.py")
        self.assertIsNone(PATH_REF.search("$TOLLGATE_KNOWLEDGE/docs/x.md"))


class TestCmd03(unittest.TestCase):
    def test_variables_defined_wave2(self):
        problems = [p for n in wave2_present() for p in check_cmd03(n)]
        self.assertEqual(problems, [])

    def test_lower_case_marker_passes(self):
        for w in ("path", "block_NN", "repo_root", "query2"):
            self.assertTrue(placeholder_ok(w, {"prefix"}))
        for w in ("N", "NN", "TOTAL", "prefix"):
            self.assertTrue(placeholder_ok(w, {"prefix"}))

    def test_other_upper_case_marker_fails(self):
        for w in ("PREFIX_UPPER", "NAME", "MRN", "Block"):
            self.assertFalse(placeholder_ok(w, {"prefix"}))

    def test_contract_has_known_names(self):
        names, placeholders = defined_names()
        for n in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_HOME", "TOLLGATE_CODE_DIR", "CLAUDE_DOTFILES"):
            self.assertIn(n, names)
        for p in ("KEY", "INITIALS"):
            self.assertIn(p, placeholders)


class TestCmd04(unittest.TestCase):
    def test_influence_is_clean(self):
        if not os.path.exists(os.path.join(CMD_DIR, "tg-influence.md")):
            self.skipTest("commands/tg-influence.md not present")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "influence.md"), "w", encoding="utf-8") as fh:
                fh.write(text_of("tg-influence"))
            code, out = scan_folder(d)
        self.assertEqual(code, 0, out)

    def test_bad_influence_is_flagged(self):
        bad = ("# influence\nAnna seems defensive about this.\n"
               "Build a power map of the stakeholders and note each trust level.\n")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "influence.md"), "w", encoding="utf-8") as fh:
                fh.write(bad)
            code, out = scan_folder(d)
        self.assertEqual(code, 1, out)
        self.assertIn("CMD-04", out)


class TestCmd05(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_gate_rules()

    def test_chain_commands_hold_gate_words(self):
        problems = []
        for n in ("tg-spec", "tg-arch", "tg-dev", "tg-qa"):
            if n in command_files():
                problems += check_cmd05(n, self.g)
        self.assertEqual(problems, [])

    def test_gate_constants_are_uppercase_words(self):
        for label, words in [x for v in cmd05_requirements(self.g).values() for x in v]:
            for w in words:
                self.assertRegex(w, r"^[A-Z_]+$")

    def test_design_complete_documented(self):
        self.assertIn("DESIGN_COMPLETE", read(os.path.join(ROOT, "docs", "gate-lines.md")))


class TestKnownGaps(unittest.TestCase):
    def test_other_commands_listed(self):
        """Commands outside the main list: any failure must be on the KNOWN_GAPS list."""
        failing = []
        for n in other_files():
            probs = check_cmd01(n) + check_cmd02(n, False) + check_cmd03(n)
            if probs:
                failing.append(n)
        sys.stderr.write("\nKnown gaps (older commands failing CMD-01 to CMD-03): %s\n" % ", ".join(failing))
        self.assertEqual(sorted(set(failing) - KNOWN_GAPS), [])


class TestGroundingQuoteSafe(unittest.TestCase):
    """Q-10: an apostrophe, dollar sign or backtick in the query must not break out of the quoting.

    Author: Dipen Patel. Added 2026-11-18.
    """
    NASTY = ["it's a $(touch MARKER) `touch MARKER` \"; touch MARKER; \" back\\slash",
             "plain words", "ends with '"]

    def snippet(self, name):
        text = read(os.path.join(CMD_DIR, name + ".md"))
        m = re.search(r"```bash\n(\$TOLLGATE_HOME/scripts/search/tg-search ground .*?)\n```", text, re.S)
        self.assertIsNotNone(m, name)
        return m.group(1)

    def test_dev_and_qa_use_a_quoted_heredoc_not_single_quotes(self):
        for name in ("tg-dev", "tg-qa"):
            snip = self.snippet(name)
            self.assertNotIn("'{query}'", snip, name)
            self.assertIn("<<'TG_QUERY'", snip, name)
            self.assertIn("tg-search ground '{skill}' -", snip, name)

    def test_nasty_query_arrives_as_one_unchanged_argument(self):
        for name in ("tg-dev", "tg-qa"):
            for query in self.NASTY:
                with tempfile.TemporaryDirectory() as tmp:
                    marker = os.path.join(tmp, "MARKER")
                    q = query.replace("MARKER", marker)
                    scripts = os.path.join(tmp, "scripts", "search")
                    os.makedirs(scripts)
                    # A stand-in for tg-search: records its arguments and stdin, then exits 0.
                    stub = os.path.join(scripts, "tg-search")
                    with open(stub, "w") as fh:
                        fh.write("#!%s\nimport sys, json\nopen(sys.argv[0] + '.out', 'w').write(json.dumps(sys.argv[1:] + [sys.stdin.read().strip()]))\n" % sys.executable)
                    os.chmod(stub, 0o755)
                    snip = self.snippet(name).replace("{skill}", "ex-" + name).replace("{query}", q)
                    snip = snip.replace(" 2>/dev/null", "")
                    r = subprocess.run(["bash", "-c", snip], capture_output=True, text=True,
                                       env=dict(os.environ, TOLLGATE_HOME=tmp))
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertFalse(os.path.exists(marker), "query ran as shell code: " + name)
                    import json
                    got = json.load(open(os.path.join(scripts, "tg-search.out")))
                    self.assertEqual(got, ["ground", "ex-" + name, "-", q])


class TestFixedPrefix(unittest.TestCase):
    """Every command carries the fixed `tg-` prefix. No per-install placeholder is left."""

    def test_exactly_the_shipped_commands(self):
        self.assertEqual(len(ALL_COMMANDS), 28)
        self.assertEqual(command_files(), sorted(ALL_COMMANDS))

    def test_no_prefix_placeholder_left(self):
        bad = []
        for n in command_files():
            for no, line in enumerate(text_of(n).splitlines(), 1):
                if re.search(r"\{prefix\}|PREFIX_UPPER|\$\{?PREFIX", line):
                    bad.append("%s.md:%d" % (n, no))
        self.assertEqual(bad, [])

    def test_slash_names_are_prefixed_and_exist(self):
        bad = []
        for n in command_files():
            for no, line in enumerate(text_of(n).splitlines(), 1):
                for m in re.finditer(r"(?<![\w./}$~-])/(tg-[a-z-]+)(?![\w/])", line):
                    if m.group(1) not in command_files():
                        bad.append("%s.md:%d %s" % (n, no, m.group(1)))
        self.assertEqual(bad, [])

    def test_search_is_called_through_tg_search(self):
        bad = []
        for n in command_files():
            for no, line in enumerate(text_of(n).splitlines(), 1):
                if re.search(r"python3?\b.*scripts/search/|TOLLGATE_PYTHON", line):
                    bad.append("%s.md:%d" % (n, no))
        self.assertEqual(bad, [])

    def test_close_does_not_run_commit_or_push(self):
        # Commit text may be printed in a plain fence; a ```bash fence is a command to run.
        text = text_of("tg-close")
        in_fence, kind, runs = False, "", []
        for line in text.splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
                kind = line[3:].strip() if in_fence else ""
                continue
            if in_fence and kind == "bash" and re.search(r"git .*\b(commit|push|add)\b", line):
                runs.append(line)
        self.assertEqual(runs, [])
        self.assertNotIn("PREFIX_UPPER", text)
        self.assertIn("$TOLLGATE_HOME/scripts/core/session_cost.py", text)


class TestVaultGitStep(unittest.TestCase):
    """The vault git setting: commands print add, commit and push lines and never run them."""

    VAULT_GIT = re.compile(r"git\s+-C\s+\{vault\}\s+(commit|add|push)\b")
    VAULT_READ = re.compile(r"git\s+-C\s+\{vault\}\s+(status|diff)\b")
    RUNNABLE = ("bash", "sh", "shell", "zsh", "console")

    def read(self, name):
        with open(os.path.join(CMD_DIR, name + ".md"), encoding="utf-8") as handle:
            return handle.read()

    def fences(self, text):
        """Yield (kind, line) for every line inside a fenced block."""
        in_fence, kind = False, ""
        for line in text.splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
                kind = line[3:].strip() if in_fence else ""
                continue
            if in_fence:
                yield kind, line

    def test_commands_look_up_the_mode(self):
        for name in ("tg-close", "tg-dev", "tg-qa"):
            self.assertIn("$TOLLGATE_HOME/scripts/core/tg_vault_git", self.read(name), name)

    def test_all_three_modes_are_described(self):
        for name in ("tg-close", "tg-dev", "tg-qa"):
            text = self.read(name)
            for phrase in ("`none`: skip git", "`local`: print the add and commit lines",
                           "`remote`: print the add, commit and push lines", "Never run them"):
                self.assertIn(phrase, text, name + ": " + phrase)

    def test_no_runnable_vault_git_step(self):
        for name in ("tg-close", "tg-dev", "tg-qa"):
            text = self.read(name)
            runs = [line for kind, line in self.fences(text)
                    if kind in self.RUNNABLE and (self.VAULT_GIT.search(line) or self.VAULT_READ.search(line))]
            self.assertEqual(runs, [], name)

    def test_vault_lines_only_in_printed_blocks(self):
        for name in ("tg-close", "tg-dev", "tg-qa"):
            text = self.read(name)
            for kind, line in self.fences(text):
                if self.VAULT_GIT.search(line):
                    self.assertEqual(kind, "text", name + ": " + line)
            self.assertIn("git -C {vault} push", text, name)

    def test_dev_and_qa_never_commit_the_vault(self):
        for name in ("tg-dev", "tg-qa"):
            text = self.read(name)
            self.assertNotIn("git -C {vault} add -A", text, name)
            self.assertNotIn("diff --cached --quiet", text, name)
            self.assertNotIn("The git guard hooks still apply and may ask first", text, name)

    def test_code_repo_commits_in_dev_are_kept(self):
        text = self.read("tg-dev")
        for step in ("git -C [REPO_PATH] checkout feature/{KEY}",
                     "git -C [REPO_PATH] merge --squash feature/{KEY}-B-{NN}",
                     "git -C [REPO_PATH] commit -m"):
            self.assertIn(step, text)

    def test_close_scans_written_files_not_vault_history(self):
        text = self.read("tg-close")
        self.assertNotIn("git -C {vault} diff", text)
        self.assertIn("each file written this run", text)


class TestCmdCleanText(unittest.TestCase):
    """No flat ticket paths, no flat wiki links and no em dash in any command (tg-doc-gen is owned elsewhere)."""

    FLAT_PATH = re.compile(r"\{tickets\}/(\[|\{KEY\})")
    FLAT_LINK = "[[02-tickets/{KEY}/"
    EM_DASH = "—"

    def files(self):
        return [n for n in ALL_COMMANDS if n != "tg-doc-gen"]

    def read(self, name):
        with open(os.path.join(CMD_DIR, name + ".md"), encoding="utf-8") as handle:
            return handle.read()

    def test_no_flat_ticket_path(self):
        for name in self.files():
            self.assertIsNone(self.FLAT_PATH.search(self.read(name)), name)

    def test_no_flat_ticket_wiki_link(self):
        for name in self.files():
            self.assertNotIn(self.FLAT_LINK, self.read(name), name)

    def test_no_em_dash(self):
        for name in self.files():
            self.assertNotIn(self.EM_DASH, self.read(name), name)

    def test_spec_and_arch_check_vault_git_mode(self):
        for name in ("tg-spec", "tg-arch"):
            self.assertIn("$TOLLGATE_HOME/scripts/core/tg_vault_git", self.read(name), name)
            self.assertNotIn("The owner commits.", self.read(name), name)


if __name__ == "__main__":
    unittest.main()
