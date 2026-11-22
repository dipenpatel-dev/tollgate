#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: requirements files carry version bounds; the AGPL epub library is only in the optional file
Ticket: none
ChangeLog:
  - Created.
"""

from __future__ import annotations

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "scripts"))
BOUNDED = re.compile(r"^[A-Za-z0-9_.-]+>=\d[\w.]*,<\d[\w.]*$")


def packages(name: str) -> list[str]:
    with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]


class Requirements(unittest.TestCase):
    def test_every_line_has_a_lower_and_upper_bound(self):
        for name in ("requirements.txt", "requirements-epub.txt", "requirements-extras.txt"):
            lines = packages(name)
            self.assertTrue(lines, name)
            for ln in lines:
                self.assertRegex(ln, BOUNDED, f"{name}: {ln}")

    def test_ebooklib_is_only_in_the_optional_epub_file(self):
        self.assertFalse([p for p in packages("requirements.txt") if p.lower().startswith("ebooklib")])
        self.assertTrue([p for p in packages("requirements-epub.txt") if p.lower().startswith("ebooklib")])

    def test_extras_name_the_lazy_imports(self):
        names = {re.split(r"[<>=]", p)[0].lower() for p in packages("requirements-extras.txt")}
        self.assertEqual({"anthropic", "aiohttp"}, names)


if __name__ == "__main__":
    unittest.main()
