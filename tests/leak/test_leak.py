#!/usr/bin/env python3
"""LEK-01..LEK-04 and CMD-04 tests for the leak scanner. Synthetic data only.

Fake secrets and fake names are built at run time so this file holds no whole
literal key.
"""
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_leaks as S  # noqa: E402

SCRIPT = os.path.join(HERE, "scan_leaks.py")
FAKE_TERM = "zork" + "wick"          # synthetic denylist term
FAKE_NAME = "bob" + "smith"          # synthetic user name
MIT_OK = "MIT License\n\nCopyright (c) 2026 Jane Q Example\n\nPermission is hereby granted\n"


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)


def png_with_text(text):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"tEXt", b"Comment\x00" + text.encode())
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        put(os.path.join(self.root, "LICENSE"), MIT_OK)
        self.denylist = os.path.join(self.root + "-deny.txt")
        put(self.denylist, "# comment\n\n%s\n" % FAKE_TERM)

    def tearDown(self):
        self.tmp.cleanup()
        if os.path.exists(self.denylist):
            os.remove(self.denylist)

    def scan(self, deny=True, allow=None):
        terms = S.load_denylist(self.denylist) if deny else []
        sc = S.Scanner(self.root, terms, allow or [])
        sc.scan()
        return sc.hits

    def rules(self, hits):
        return sorted(h[0] for h in hits)


class Lek01(Base):
    def test_LEK_01a_text_hit_case_insensitive(self):
        put(os.path.join(self.root, "a.md"), "hello %s world\n" % FAKE_TERM.upper())
        hits = self.scan()
        self.assertEqual(self.rules(hits), ["LEK-01"])

    def test_LEK_01b_json_html_hits(self):
        put(os.path.join(self.root, "a.json"), '{"k": "%s"}' % FAKE_TERM)
        put(os.path.join(self.root, "b.html"), "<p>%s</p>" % FAKE_TERM)
        self.assertEqual(self.rules(self.scan()), ["LEK-01", "LEK-01"])

    def test_LEK_01c_binary_and_image_metadata(self):
        put(os.path.join(self.root, "x.bin"), b"\x00\x01\x02junk" + FAKE_TERM.encode() + b"\x00\x03")
        put(os.path.join(self.root, "p.png"), png_with_text("by " + FAKE_TERM))
        hits = self.scan()
        self.assertEqual(sorted(h[1] for h in hits), ["p.png", "x.bin"])

    def test_LEK_01d_file_name_hit(self):
        put(os.path.join(self.root, FAKE_TERM + ".txt"), "clean")
        self.assertEqual(self.rules(self.scan()), ["LEK-01"])

    def test_LEK_01e_clean_tree_and_comments(self):
        put(os.path.join(self.root, "a.md"), "nothing here\n")
        self.assertEqual(self.scan(), [])

    def test_LEK_01f_git_dir_skipped(self):
        put(os.path.join(self.root, ".git", "config"), FAKE_TERM)
        self.assertEqual(self.scan(), [])

    def test_LEK_01g_match_is_masked(self):
        put(os.path.join(self.root, "a.md"), FAKE_TERM + "\n")
        sc = S.Scanner(self.root, [FAKE_TERM])
        out = io.StringIO()
        sc.scan()
        S.report(sc, out)
        self.assertNotIn(FAKE_TERM, out.getvalue())

    def test_LEK_01h_denylist_from_env_and_flag(self):
        put(os.path.join(self.root, "a.md"), FAKE_TERM)
        env = dict(os.environ, TOLLGATE_DENYLIST=self.denylist)
        p = subprocess.run([sys.executable, SCRIPT, self.root, "--allowlist", "/nonexistent"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 1)
        self.assertIn("LEK-01", p.stdout)
        self.assertNotIn(FAKE_TERM, p.stdout)
        env.pop("TOLLGATE_DENYLIST")
        p = subprocess.run([sys.executable, SCRIPT, self.root, "--allowlist", "/nonexistent",
                            "--denylist", self.denylist], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 1)

    def test_LEK_01i_allowlist_by_name(self):
        put(os.path.join(self.root, "fixture.txt"), FAKE_TERM)
        hits = self.scan(allow=[("fixture.txt", None)])
        self.assertEqual(hits, [])


class Lek02(Base):
    def test_LEK_02a_personal_paths_flagged(self):
        put(os.path.join(self.root, "a.sh"), "cd /Users/%s/code\nls /home/%s/x\n" % (FAKE_NAME, FAKE_NAME))
        self.assertEqual(self.rules(self.scan(deny=False)), ["LEK-02", "LEK-02"])

    def test_LEK_02b_generic_and_variable_paths_ok(self):
        put(os.path.join(self.root, "a.md"),
            "$HOME/x /Users/<name>/x /Users/you/x /home/user/x /home/runner/w ~/x\n")
        self.assertEqual(self.scan(deny=False), [])

    def test_LEK_02c_allowlisted_fixture(self):
        put(os.path.join(self.root, "fx.txt"), "/Users/%s/a\n" % FAKE_NAME)
        self.assertEqual(self.scan(deny=False, allow=[("fx.txt", {"LEK-02"})]), [])
        # allowlist for LEK-02 only does not hide other rules
        put(os.path.join(self.root, "fx.txt"), "/Users/%s/a\n%s\n" % (FAKE_NAME, FAKE_TERM))
        self.assertEqual(self.rules(self.scan(allow=[("fx.txt", {"LEK-02"})])), ["LEK-01"])

    def test_LEK_02d_path_inside_binary(self):
        put(os.path.join(self.root, "b.bin"), b"\x00\x00/Users/" + FAKE_NAME.encode() + b"/z\x00")
        self.assertEqual(self.rules(self.scan(deny=False)), ["LEK-02"])


class Lek03(Base):
    def test_LEK_03a_key_patterns(self):
        aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
        gh = "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
        sk = "s" + "k-" + "abcdefghijklmnopqrstuvwx"
        pem = "-----BEGIN " + "RSA PRIVATE " + "KEY-----"
        put(os.path.join(self.root, "k.txt"), "\n".join([aws, gh, sk, pem]) + "\n")
        hits = self.scan(deny=False)
        self.assertEqual(self.rules(hits), ["LEK-03"] * 4)
        report = "\n".join(h[3] for h in hits)
        for secret in (aws, gh, sk):
            self.assertNotIn(secret, report)

    def test_LEK_03b_quoted_credential(self):
        val = "Zx9" * 8
        put(os.path.join(self.root, "c.py"), 'api_' + 'key = "%s"\n' % val)
        hits = self.scan(deny=False)
        self.assertEqual(self.rules(hits), ["LEK-03"])
        self.assertNotIn(val, hits[0][3])

    def test_LEK_03c_attribution_lines(self):
        a = "Co-Authored" + "-By: Someone <x@example.invalid>"
        g = "Generated" + " with a tool"
        put(os.path.join(self.root, "m.md"), a + "\n" + g + "\n")
        self.assertEqual(self.rules(self.scan(deny=False)), ["LEK-03", "LEK-03"])

    def test_LEK_03d_date_header(self):
        put(os.path.join(self.root, "h.sh"), "#!/bin/bash\n# Date: 2026-11-18\n")
        put(os.path.join(self.root, "empty.sh"), "#!/bin/bash\n# Date:\n")
        put(os.path.join(self.root, "empty2.sh"), "# Date: \n")
        hits = self.scan(deny=False)
        self.assertEqual([h[1] for h in hits], ["h.sh"])

    def test_LEK_03f_date_only_in_header_zone(self):
        lines = ["line %d" % i for i in range(1, 100)]
        early = list(lines)
        early[4] = "# Date: 2026-11-18"          # line 5
        late = list(lines)
        late[79] = "Date: YYYY-MM-DD"            # line 80
        put(os.path.join(self.root, "early.md"), "\n".join(early) + "\n")
        put(os.path.join(self.root, "late.md"), "\n".join(late) + "\n")
        hits = self.scan(deny=False)
        self.assertEqual([(h[1], h[2]) for h in hits], [("early.md", 5)])

    def test_LEK_03e_clean_file(self):
        put(os.path.join(self.root, "ok.md"), "No secrets. Token budget is a number.\n")
        self.assertEqual(self.scan(deny=False), [])


class Lek04(Base):
    def run_license(self, text):
        put(os.path.join(self.root, "LICENSE"), text)
        return [h for h in self.scan(deny=False) if h[0] == "LEK-04"]

    def test_LEK_04a_personal_name_ok(self):
        self.assertEqual(self.run_license(MIT_OK), [])

    def test_LEK_04b_missing_license(self):
        os.remove(os.path.join(self.root, "LICENSE"))
        self.assertEqual(len([h for h in self.scan(deny=False) if h[0] == "LEK-04"]), 1)

    def test_LEK_04c_company_wording(self):
        for holder in ("Example Widgets Inc.", "Acme Health LLC", "The Example Contributors",
                       "Example Labs", "Example Technologies"):
            self.assertEqual(len(self.run_license("Copyright (c) 2026 %s\n" % holder)), 1, holder)

    def test_LEK_04d_no_holder(self):
        self.assertEqual(len(self.run_license("MIT License\nPermission granted\n")), 1)

    def test_LEK_04e_email_in_holder(self):
        self.assertEqual(len(self.run_license("Copyright (c) 2026 Jane Example <j@example.invalid>\n")), 1)


class Cmd04(Base):
    def influence(self, body):
        put(os.path.join(self.root, "commands", "influence.md"), body)
        return [h for h in self.scan(deny=False) if h[0] == "CMD-04"]

    def test_CMD_04g_tg_influence_file_is_checked_too(self):
        put(os.path.join(self.root, "commands", "tg-influence.md"), "Trust level: 3 of 5\n")
        self.assertTrue([h for h in self.scan(deny=False) if h[0] == "CMD-04"])

    def test_CMD_04a_clean_rewrite_command(self):
        body = ("# influence\nRewrite the message the user pastes so it reads clearly.\n"
                "Keep the meaning. Return only the new text.\n")
        self.assertEqual(self.influence(body), [])

    def test_CMD_04b_trust_rating(self):
        self.assertTrue(self.influence("Trust level: 3 of 5\n"))
        self.assertTrue(self.influence("Give a trust score for each person.\n"))

    def test_CMD_04c_influence_strategy(self):
        self.assertTrue(self.influence("Build an influence strategy for the meeting.\n"))
        self.assertTrue(self.influence("Make a power map of allies and adversaries.\n"))

    def test_CMD_04d_named_person_analysis(self):
        self.assertTrue(self.influence("Marcus seems defensive about the budget.\n"))

    def test_CMD_04e_only_applies_to_influence_md(self):
        put(os.path.join(self.root, "commands", "other.md"), "Build an influence strategy.\n")
        self.assertEqual([h for h in self.scan(deny=False) if h[0] == "CMD-04"], [])


class Cli(Base):
    def test_exit_codes(self):
        put(os.path.join(self.root, "a.md"), "clean\n")
        p = subprocess.run([sys.executable, SCRIPT, self.root, "--allowlist", "/nonexistent"],
                           capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != "TOLLGATE_DENYLIST"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = subprocess.run([sys.executable, SCRIPT, "/nonexistent-folder"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
