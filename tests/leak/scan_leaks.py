#!/usr/bin/env python3
"""Tollgate leak scanner.

Scans every file under a repo folder (text, JSON, HTML, images, any binary)
and reports rule hits. Exit 0 when clean, 1 on any hit, 2 on usage error.

Rules
  LEK-01  a denylist term appears (case-insensitive). Denylist path comes from
          --denylist or the env var TOLLGATE_DENYLIST. One term per line,
          '#' starts a comment. The real list is private.
  LEK-02  an absolute personal path (/Users/<name>, /home/<name>).
  LEK-03  a key or token pattern, an AI attribution line, or a header
          'Date:' field that has a value.
  LEK-04  LICENSE is missing, or its copyright holder is not a personal name.
  CMD-04  a command file named influence.md or tg-influence.md holds analysis of named people,
          trust ratings or influence strategy.

Binary files and images: printable strings (4+ chars) are pulled out and
scanned, which also covers image metadata (EXIF, PNG text chunks, XMP).

Allowlist (tests/leak/allowed_fixtures.txt by default, or --allowlist):
  one entry per line, '#' comments.
    name_or_relative_path            skip that file for every rule
    name_or_relative_path : LEK-02   skip that file for the listed rules only
  An entry with no '/' matches the file base name anywhere in the tree.

A matched secret is never printed in full. Excerpts are masked.
"""
import argparse
import fnmatch
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ALLOWLIST = os.path.join(HERE, "allowed_fixtures.txt")
SKIP_DIRS = {".git", "__pycache__"}  # a worktree's .git is a file; walk() skips that by name too
MIN_STRING = 4
HEADER_LINES = 30  # the Date: rule only checks this many leading lines
MAX_BYTES = 64 * 1024 * 1024

# Names that are generic placeholders, not a real person.
GENERIC_PATH_NAMES = {
    "user", "username", "you", "yourname", "your-name", "name", "me",
    "example", "shared", "runner", "someone", "foo", "bar", "xxx",
    "tgtester", "tgtesterx",
}

# Built by concatenation so this file does not match its own rules.
_A = "Co-Authored" + "-By"
_G = "generated" + " with"
_KEY_PATTERNS = [
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("api secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE" + r" KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("quoted credential", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d)\b\s*[:=]\s*['\"]"
        r"([A-Za-z0-9/+_=.-]{16,})['\"]")),
]
_ATTRIBUTION = [
    ("ai attribution line", re.compile(re.escape(_A), re.I)),
    ("ai attribution line", re.compile(re.escape(_G), re.I)),
]
_DATE_HEADER = re.compile(r"(?im)^[ \t]*(?:#|//|\*|--|<!--)?[ \t]*Date:[ \t]*([^\s>-][^\n]*)$")
_PERSONAL_PATH = re.compile(r"(?<![A-Za-z0-9_.-])/(?:Users|home)/([A-Za-z0-9._-]+)")

_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING")
_ORG_WORDS = re.compile(
    r"(?i)\b(inc\.?|llc|ltd\.?|limited|corp\.?|corporation|company|co\.|gmbh|"
    r"plc|foundation|labs?|technolog(?:y|ies)|systems|solutions|health|"
    r"consulting|group|holdings|partners|institute|university|"
    r"contributors|authors|team|organi[sz]ation|ai)\b")

# CMD-04 rules (applies to files named influence.md or tg-influence.md).
_CMD04 = [
    ("trust rating", re.compile(
        r"(?i)\btrust(?:ed)?[ -](?:level|rating|score|assessment)\b|"
        r"\b(?:trust|trustworthiness)\s*[:=]\s*\S+|"
        r"\brate[sd]?\s+(?:their|his|her)\s+trust|\btrust\s*(?:/|out of)\s*10\b")),
    ("influence strategy", re.compile(
        r"(?i)\binfluence\s+(?:strategy|plan|map|tactics?)\b|\bpower\s+map\b|"
        r"\bstakeholder\s+(?:map|analysis)\b|\bmanipulat\w*|\bleverage\s+(?:over|against|on)\b|"
        r"\bhidden\s+agenda\b|\bsway\s+(?:him|her|them)\b|\bwin\s+over\b|"
        r"\b(?:ally|allies|adversar(?:y|ies)|rival|rivals)\b|\bpolitic(?:s|al)\b")),
    ("analysis of a named person", re.compile(
        r"\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?\s+"
        r"(?:is|seems|appears|tends to|wants|distrusts|resists|feels|"
        r"probably|likely|will likely|cannot be trusted|is hostile|is defensive)\b"
        r"(?!\s+(?:a|the|an)\s+(?:file|command|skill|rewrite))")),
    ("personality assessment", re.compile(
        r"(?i)\b(?:personality|motivations?|agenda|loyalt(?:y|ies)|insecure|"
        r"defensive|hostile)\b")),
]
# Words that begin a sentence and look like a name but are not.
_NOT_NAMES = {"This", "That", "The", "These", "Those", "It", "There", "Here",
              "What", "When", "Where", "Who", "Why", "How", "If", "Claude",
              "Tollgate", "Output", "Input", "Note", "Rewrite", "Each", "Every"}


def mask(text):
    """Mask a matched value: keep at most 2 leading chars and the length."""
    t = text.strip()
    if len(t) <= 4:
        return "*" * len(t)
    return "%s%s(len %d)" % (t[:2], "*" * 6, len(t))


def load_denylist(path):
    terms = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            terms.append(line.lower())
    return terms


def load_allowlist(path):
    """Return list of (pattern, rules_or_None)."""
    entries = []
    if not path or not os.path.isfile(path):
        return entries
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            rules = None
            if ":" in line:
                line, r = line.split(":", 1)
                rules = {x.strip().upper() for x in r.split(",") if x.strip()}
                line = line.strip()
            entries.append((line, rules))
    return entries


def allowed(rel, rule, entries):
    base = os.path.basename(rel)
    for pat, rules in entries:
        hit = fnmatch.fnmatch(rel, pat) if "/" in pat else fnmatch.fnmatch(base, pat)
        if hit and (rules is None or rule in rules):
            return True
    return False


def extract_text(data):
    """Return text to scan. Text files decode; binary gets printable strings."""
    if b"\x00" not in data[:8192]:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            pass
    parts = [m.group().decode("ascii", "replace")
             for m in re.finditer(rb"[\x20-\x7e]{%d,}" % MIN_STRING, data)]
    # UTF-16LE strings (common in some image/office metadata)
    parts += [m.group().decode("utf-16le", "replace")
              for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % MIN_STRING, data)]
    return "\n".join(parts)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


class Scanner:
    def __init__(self, root, denylist=None, allow=None):
        self.root = os.path.abspath(root)
        self.denylist = denylist or []
        self.allow = allow or []
        self.hits = []  # (rule, rel, line, detail)
        self.files = 0

    def add(self, rule, rel, line, detail):
        if allowed(rel, rule, self.allow):
            return
        self.hits.append((rule, rel, line, detail))

    def walk(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if name in SKIP_DIRS or os.path.islink(full):
                    continue
                yield full, os.path.relpath(full, self.root)

    def scan(self):
        for full, rel in self.walk():
            self.files += 1
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    self.add("SCAN", rel, 0, "file too large to scan")
                    continue
                with open(full, "rb") as f:
                    data = f.read()
            except OSError as e:
                self.add("SCAN", rel, 0, "unreadable: %s" % e.__class__.__name__)
                continue
            text = extract_text(data)
            self.check_denylist(rel, text)
            self.check_paths(rel, text)
            self.check_secrets(rel, text)
            if os.path.basename(rel) in ("influence.md", "tg-influence.md"):
                self.check_cmd04(rel, text)
        self.check_license()
        return self.hits

    def check_denylist(self, rel, text):
        low = text.lower()
        for i, term in enumerate(self.denylist, 1):
            if term in rel.lower():
                self.add("LEK-01", rel, 0, "denylist term #%d in file name" % i)
            start = 0
            while True:
                pos = low.find(term, start)
                if pos < 0:
                    break
                self.add("LEK-01", rel, line_of(text, pos),
                         "denylist term #%d: %s" % (i, mask(text[pos:pos + len(term)])))
                start = pos + len(term)

    def check_paths(self, rel, text):
        for m in _PERSONAL_PATH.finditer(text):
            name = m.group(1)
            if name.lower() in GENERIC_PATH_NAMES:
                continue
            self.add("LEK-02", rel, line_of(text, m.start()),
                     "personal path: /%s/%s" % (m.group(0).split("/")[1], mask(name)))

    def check_secrets(self, rel, text):
        for label, rx in _KEY_PATTERNS:
            for m in rx.finditer(text):
                self.add("LEK-03", rel, line_of(text, m.start()),
                         "%s: %s" % (label, mask(m.group(0))))
        for label, rx in _ATTRIBUTION:
            for m in rx.finditer(text):
                self.add("LEK-03", rel, line_of(text, m.start()), label)
        zone_end = 0
        for _ in range(HEADER_LINES):
            nl = text.find("\n", zone_end)
            if nl < 0:
                zone_end = len(text)
                break
            zone_end = nl + 1
        for m in _DATE_HEADER.finditer(text[:zone_end]):
            self.add("LEK-03", rel, line_of(text, m.start()),
                     "Date: header has a value (%s)" % mask(m.group(1)))

    def check_license(self):
        found = None
        for n in _LICENSE_NAMES:
            if os.path.isfile(os.path.join(self.root, n)):
                found = n
                break
        if not found:
            self.add("LEK-04", "LICENSE", 0, "LICENSE file missing")
            return
        with open(os.path.join(self.root, found), "r", encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
        holders = re.findall(r"(?im)^\s*copyright\s*(?:\(c\)|©)?\s*(?:\d{4}(?:\s*[-,]\s*\d{4})*)?\s*(.*)$", text)
        holders = [h.strip() for h in holders if h.strip()]
        if not holders:
            self.add("LEK-04", found, 0, "no copyright holder line")
            return
        for h in holders:
            if _ORG_WORDS.search(h):
                self.add("LEK-04", found, 0, "holder looks like an organization: %s" % mask(h))
            elif len(h.split()) < 2:
                self.add("LEK-04", found, 0, "holder is not a full personal name")
            elif "@" in h or "http" in h:
                self.add("LEK-04", found, 0, "holder line carries an address, name only")

    def check_cmd04(self, rel, text):
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, rx in _CMD04:
                m = rx.search(line)
                if not m:
                    continue
                if label == "analysis of a named person":
                    first = m.group(0).split()[0]
                    if first in _NOT_NAMES:
                        continue
                self.add("CMD-04", rel, lineno, "%s: %s" % (label, mask(m.group(0))))


def report(sc, out=sys.stdout):
    by_rule = {}
    for rule, rel, line, detail in sc.hits:
        by_rule[rule] = by_rule.get(rule, 0) + 1
        loc = "%s:%d" % (rel, line) if line else rel
        out.write("%s  %s  %s\n" % (rule, loc, detail))
    out.write("scanned %d files, %d hits" % (sc.files, len(sc.hits)))
    if by_rule:
        out.write(" (" + ", ".join("%s=%d" % (k, by_rule[k]) for k in sorted(by_rule)) + ")")
    out.write("\n")
    return by_rule


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tollgate leak scanner")
    ap.add_argument("root", help="repo folder to scan")
    ap.add_argument("--denylist", help="denylist file (default: env TOLLGATE_DENYLIST)")
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST,
                    help="allowlist file (default: tests/leak/allowed_fixtures.txt)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        sys.stderr.write("not a folder: %s\n" % args.root)
        return 2
    dl_path = args.denylist or os.environ.get("TOLLGATE_DENYLIST")
    terms = []
    if dl_path:
        if not os.path.isfile(dl_path):
            sys.stderr.write("denylist file not found\n")
            return 2
        terms = load_denylist(dl_path)
    else:
        sys.stderr.write("warning: no denylist given, LEK-01 skipped\n")
    sc = Scanner(args.root, terms, load_allowlist(args.allowlist))
    sc.scan()
    report(sc)
    return 1 if sc.hits else 0


if __name__ == "__main__":
    sys.exit(main())
