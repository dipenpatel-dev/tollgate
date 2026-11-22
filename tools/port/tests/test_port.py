import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_DIR = os.path.dirname(HERE)
sys.path.insert(0, PORT_DIR)
import port  # noqa: E402

EM = "\u2014"
CONFIG = {
    "paths": {"/home/tester/vault": "$TOLLGATE_KNOWLEDGE", "/home/tester": "$HOME"},
    "ticket_prefixes": ["ZZ", "QQ"],
    "skill_prefixes": ["zz-"],
    "initials": ["ABC"],
}
DENY = [("Acme", "Client A"), ("Jane Roe", "a colleague")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src")
        self.root = os.path.join(self.tmp, "repo")
        self.dest = os.path.join(self.root, "out")
        os.makedirs(self.src)
        os.makedirs(self.root)
        self.rw = port.Rewriter(CONFIG, DENY)

    def put(self, name, text, mode=0o644):
        p = os.path.join(self.src, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(p, mode)
        return p

    def rewrite(self, text, name="a.md"):
        return port.rewrite_text(text, name, self.rw)

    def go(self, **kw):
        with open(os.devnull, "w") as dn:
            return port.run(self.src, self.dest, CONFIG, DENY, root=self.root, out=dn, **kw)

    def read(self, rel):
        with open(os.path.join(self.dest, rel), encoding="utf-8") as fh:
            return fh.read()


class RewriteTypes(Base):
    def test_paths_longest_first(self):
        new, c, _, _ = self.rewrite("cd /home/tester/vault/x and /home/tester/y")
        self.assertEqual(new, "cd $TOLLGATE_KNOWLEDGE/x and $HOME/y")

    def test_path_boundary(self):
        new, *_ = self.rewrite("/home/tester2/z")
        self.assertEqual(new, "/home/tester2/z")

    def test_ticket_skill_initials(self):
        new, *_ = self.rewrite("See ZZ-12 and QQ-3, run zz-arch. By ABC.")
        self.assertEqual(
            new, "See ${TOLLGATE_TICKET_PREFIX}-12 and ${TOLLGATE_TICKET_PREFIX}-3, run "
                 "tg-arch. By ${TOLLGATE_INITIALS}.")

    def test_denylist(self):
        new, *_ = self.rewrite("Ask Jane Roe about acme's plan.")
        self.assertEqual(new, "Ask a colleague about Client A's plan.")

    def test_header_date_and_changelog(self):
        text = "# Date: 2026-01-02\n\n## Change log\n- 2026-01-03: fixed it\n- (2026-01-04) more\n\n## Body\n- 2026-02-02: keep\n"
        new, *_ = self.rewrite(text)
        self.assertIn("# Date:\n", new)
        self.assertIn("- fixed it\n", new)
        self.assertIn("- more\n", new)
        self.assertIn("- 2026-02-02: keep", new)

    def test_header_date_shell_and_bold(self):
        new, *_ = self.rewrite("#!/bin/sh\n# Date: 2026-05-05\necho 2026-05-05\n", "a.sh")
        self.assertIn("# Date:\n", new)
        self.assertIn("echo 2026-05-05", new)
        new, *_ = self.rewrite("**Date:** 2026-05-05\n")
        self.assertEqual(new, "**Date:**\n")

    def test_changelog_in_shell_comments(self):
        text = "# Changelog\n# 2026-03-03 first\n# 2026-03-04 second\necho 2026-03-05\n"
        new, *_ = self.rewrite(text, "a.sh")
        self.assertEqual(new, "# Changelog\n# first\n# second\necho 2026-03-05\n")

    def test_attribution_and_em_dash(self):
        text = "Fix thing " + EM + " it works\nCo-Authored-By: Claude <x@y>\nDone" + EM + "Next step\nOne" + EM + "two\n"
        new, c, em, attr = self.rewrite(text)
        self.assertNotIn(EM, new)
        self.assertNotIn("Co-Authored", new)
        self.assertEqual(attr, [2])
        self.assertEqual([e[0] for e in em], [1, 3, 4])
        self.assertIn("Fix thing, it works", new)
        self.assertIn("Done. Next step", new)

    def test_json_and_yaml_stay_valid(self):
        new, *_ = self.rewrite(json.dumps({"p": "/home/tester/vault/a", "t": "ZZ-9"}), "a.json")
        self.assertEqual(json.loads(new), {"p": "$TOLLGATE_KNOWLEDGE/a", "t": "${TOLLGATE_TICKET_PREFIX}-9"})
        new, *_ = self.rewrite("key: /home/tester/vault\nowner: Acme\n", "a.yaml")
        self.assertEqual(new, "key: $TOLLGATE_KNOWLEDGE\nowner: Client A\n")

    def test_python_file(self):
        new, *_ = self.rewrite('P = "/home/tester/vault"  # ZZ-4\n', "a.py")
        self.assertEqual(new, 'P = "$TOLLGATE_KNOWLEDGE"  # ${TOLLGATE_TICKET_PREFIX}-4\n')

    def test_idempotent_text(self):
        text = "Date: 2026-1-1\nZZ-1 zz-dev ABC Acme /home/tester/vault Co-Authored-By: Claude\nx " + EM + " y\n"
        once, *_ = self.rewrite(text)
        twice, *_ = self.rewrite(once)
        self.assertEqual(once, twice)


class Leftovers(Base):
    def kinds(self, text, name="a.md"):
        return [r for _, r in port.find_leftovers(text, name)]

    def test_each_kind(self):
        fake_key = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0"
        self.assertIn("IP address", self.kinds("host 10.1.2.3 here"))
        self.assertIn("email address", self.kinds("write bob@corp.test now"))
        self.assertNotIn("email address", self.kinds("write hello@dipenpatel.dev now"))
        self.assertIn("host name", self.kinds("open box.home.test.lan today"))
        self.assertNotIn("host name", self.kinds("see github.com"))
        self.assertIn("possible token or secret", self.kinds("t = " + fake_key))
        self.assertIn("possible token or secret", self.kinds("api_key = " + "abcd1234" * 3))
        self.assertIn("political word, remove or rewrite by hand", self.kinds("Office politics here"))
        self.assertIn("unknown name that looks like a person", self.kinds("ping Maria Lopez today"))
        self.assertNotIn("unknown name that looks like a person", self.kinds("with Python today"))
        self.assertIn("personal absolute path with no mapping", self.kinds("cat /Users/someone/x"))
        self.assertIn("@handle that may be a person", self.kinds("thanks @maria99"))
        self.assertNotIn("@handle that may be a person", self.kinds("@dataclass", "a.py"))

    def test_leftovers_file_has_no_content(self):
        self.put("a.md", "contact 10.9.8.7 please\n")
        self.go()
        rep = self.read("leftovers.md")
        self.assertIn("| a.md | 1 | IP address |", rep)
        self.assertNotIn("10.9.8.7", rep)


class Behaviour(Base):
    def test_mode_bits_preserved(self):
        self.put("run.sh", "#!/bin/sh\necho ZZ-1\n", 0o755)
        self.put("plain.md", "ZZ-2\n", 0o640)
        self.go()
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.dest, "run.sh")).st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.dest, "plain.md")).st_mode), 0o640)

    def test_dry_run_writes_nothing(self):
        self.put("a.md", "ZZ-1\n")
        self.go(dry_run=True)
        self.assertFalse(os.path.exists(self.dest))

    def test_idempotent_run(self):
        self.put("a/b.md", "Date: 2026-01-01\nZZ-1 Acme " + EM + " ok\n")
        self.put("c.sh", "echo /home/tester/vault\n", 0o755)
        self.go()
        first = self.snapshot()
        self.go()
        self.assertEqual(first, self.snapshot())
        self.assertEqual(self.read("a/b.md"), "Date:\n${TOLLGATE_TICKET_PREFIX}-1 Client A, ok\n")

    def snapshot(self):
        snap = {}
        for base, _, files in os.walk(self.dest):
            for f in files:
                p = os.path.join(base, f)
                with open(p, "rb") as fh:
                    snap[os.path.relpath(p, self.dest)] = (fh.read(), os.stat(p).st_mode)
        return snap

    def test_source_untouched(self):
        p = self.put("a.md", "ZZ-1\n")
        self.go()
        with open(p, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "ZZ-1\n")

    def test_refuses_destination_outside_root(self):
        self.put("a.md", "x\n")
        outside = os.path.join(self.tmp, "elsewhere")
        with open(os.devnull, "w") as dn:
            with self.assertRaises(SystemExit):
                port.run(self.src, outside, CONFIG, DENY, root=self.root, out=dn)
        self.assertFalse(os.path.exists(outside))

    def test_refuses_overlap(self):
        self.put("a.md", "x\n")
        with open(os.devnull, "w") as dn:
            with self.assertRaises(SystemExit):
                port.run(self.src, os.path.join(self.src, "sub"), CONFIG, DENY, root=self.tmp, out=dn)

    def test_binary_copied(self):
        p = os.path.join(self.src, "b.bin")
        with open(p, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        self.go()
        with open(os.path.join(self.dest, "b.bin"), "rb") as fh:
            self.assertEqual(fh.read(), b"\xff\xfe\x00\x01")

    def test_single_file_source(self):
        p = self.put("one.md", "ZZ-1\n")
        with open(os.devnull, "w") as dn:
            port.run(p, self.dest, CONFIG, DENY, root=self.root, out=dn)
        self.assertEqual(self.read("one.md"), "${TOLLGATE_TICKET_PREFIX}-1\n")

    def test_cli_with_private_files(self):
        self.put("a.md", "ZZ-1 Acme\n")
        m = os.path.join(self.tmp, "map.json")
        d = os.path.join(self.tmp, "deny.txt")
        with open(m, "w") as fh:
            json.dump({"ticket_prefixes": ["ZZ"]}, fh)
        with open(d, "w") as fh:
            fh.write("# comment\nAcme => Client B\n")
        r = subprocess.run([os.path.join(PORT_DIR, "run.sh"), self.src, self.dest, "--root", self.root,
                            "--map", m, "--denylist", d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("a.md"), "${TOLLGATE_TICKET_PREFIX}-1 Client B\n")


if __name__ == "__main__":
    unittest.main()
