#!/usr/bin/env python3
"""Tollgate port tool: rewrite a source file or folder into a destination folder.

Date:
Reads the source (never changes it), writes a rewritten copy under the
destination, and writes leftovers.md for what it could not safely rewrite.
See docs/tools/port.md.

ChangeLog:
  Skill prefixes now rewrite to the fixed `tg-` command prefix, not a per-install variable.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(os.path.dirname(HERE))
SKIP_NAMES = {".git", "__pycache__", ".DS_Store", "leftovers.md"}
EM = "\u2014"
DATE = r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?"

HEADER_DATE = re.compile(
    r"^(\s*(?:#|//|\*|<!--)?\s*(?:\*\*)?Date(?::\*\*|\*\*:|:))[ \t]*(.*?)(\r?\n?)$",
    re.I)
CL_START = re.compile(
    r"^\s*(?:#{1,6}|//|\*|<!--)?\s*(?:\*\*)?(?:change ?log|change history|"
    r"revision history|history)(?:\*\*)?\s*:?\s*(?:-->)?\s*$", re.I)
ATTRIBUTION = re.compile(
    r"co-authored-by:.*(claude|anthropic|\bai\b|copilot|gpt)"
    r"|generated (with|by) .*(claude|anthropic|copilot|chatgpt|\bai\b)", re.I)

POLITICAL = re.compile(
    r"politic(al|s|ally)|influence strateg|trust (rating|assessment|score)|"
    r"power dynamic|interpersonal dynamic|office politics|manipulat(e|ion|ing)", re.I)
IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
EMAIL_OK = re.compile(r"@(example\.(com|org|net)|users\.noreply\.[a-z.]+)$|^hello@dipenpatel\.dev$", re.I)
HOST = re.compile(
    r"(?<![\w@./-])(?:[a-z0-9][a-z0-9-]*\.)+(?:local|lan|internal|home|corp|us|com|net|org|io|dev|ai)\b",
    re.I)
HOST_OK = re.compile(
    r"(^|\.)(example\.(com|org|net)|github\.com|githubusercontent\.com|anthropic\.com|claude\.com|"
    r"claude\.ai|python\.org|localhost|pypi\.org|npmjs\.com|docker\.com|mozilla\.org|w3\.org|"
    r"readthedocs\.io|shields\.io|cloudflare\.com|jsdelivr\.net|unpkg\.com)$", re.I)
HOST_SHAPE = re.compile(r"\b[a-z]{2,}-[a-z]{2,}-[a-z]\d{2}\b")
TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|xox[abpr]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{12,}|glpat-[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{16,}|"
    r"Bearer\s+[A-Za-z0-9._~+/=-]{16,})")
SECRET_ASSIGN = re.compile(
    r"(?i)(api[_-]?key|token|secret|passw(or)?d)\"?\s*[:=]\s*[\"']?(?![\$\{<])[A-Za-z0-9_\-/+=.]{12,}")
PERSONAL_PATH = re.compile(r"(?<![\w$])/(?:Users|home)/[A-Za-z0-9._-]+")
NAME_CUE = re.compile(
    r"\b(?:with|from|ask|ping|cc|thanks|thank you|told|per|met|call|email|message|ask)\s+"
    r"([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b")
HANDLE = re.compile(r"(?<![\w.@/])@[A-Za-z][\w-]{2,}")
NOT_NAMES = {
    "Claude", "Code", "Python", "Git", "GitHub", "Docker", "Jira", "Slack", "Notion", "Plane",
    "Markdown", "Tollgate", "Linux", "Mac", "Windows", "Gitea", "Dagster", "Ansible", "Client",
    "The", "This", "That", "These", "Those", "Each", "Every", "Any", "All", "Some", "None",
    "Dotfiles", "Anthropic", "Infisical", "Terraform", "Kubernetes", "Bash", "Zsh", "Homebrew",
    "Databricks", "Unity", "Catalog", "Sonnet", "Opus", "Haiku", "Chroma", "ChromaDB", "Ollama",
}
CLIENT_RE = re.compile(r"^Client [A-Z]$")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def merge_config(base, extra):
    out = {"paths": dict(base.get("paths", {})), "ticket_prefixes": list(base.get("ticket_prefixes", [])),
           "skill_prefixes": list(base.get("skill_prefixes", [])), "initials": list(base.get("initials", []))}
    out["paths"].update(extra.get("paths", {}))
    for key in ("ticket_prefixes", "skill_prefixes", "initials"):
        for item in extra.get(key, []):
            if item not in out[key]:
                out[key].append(item)
    return out


def load_denylist(path):
    terms = []
    if not path:
        return terms
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                term, rep = [p.strip() for p in line.split("=>", 1)]
            else:
                term, rep = line, "Client A"
            if term and rep and term.lower() not in rep.lower():
                terms.append((term, rep))
    terms.sort(key=lambda t: -len(t[0]))
    return terms


class Rewriter:
    def __init__(self, config, denylist):
        paths = sorted(config["paths"].items(), key=lambda kv: -len(kv[0]))
        self.paths = [(re.compile(re.escape(k.rstrip("/")) + r"(?![\w-])"), v) for k, v in paths if k]
        self.tickets = [re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(p) + r"-(?=\d)")
                        for p in config["ticket_prefixes"] if p]
        self.skills = [re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(p.rstrip("-")) + r"-(?=[A-Za-z])")
                       for p in config["skill_prefixes"] if p]
        self.initials = [re.compile(r"(?<![A-Za-z0-9_])" + re.escape(p) + r"(?![A-Za-z0-9_])")
                         for p in config["initials"] if p]
        self.deny = [(re.compile(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"(?![A-Za-z0-9_])", re.I), r)
                     for t, r in denylist]

    def line(self, text, counts):
        def sub(rx, rep, s, key):
            s2, n = rx.subn(lambda m: rep, s)
            if n:
                counts[key] = counts.get(key, 0) + n
            return s2
        for rx, rep in self.paths:
            text = sub(rx, rep, text, "path")
        for rx in self.tickets:
            text = sub(rx, "${TOLLGATE_TICKET_PREFIX}-", text, "ticket-prefix")
        for rx in self.skills:
            text = sub(rx, "tg-", text, "skill-prefix")
        for rx in self.initials:
            text = sub(rx, "${TOLLGATE_INITIALS}", text, "initials")
        for rx, rep in self.deny:
            text = sub(rx, rep, text, "denylist")
        return text


def strip_changelog_dates(line):
    new = re.sub(r"\|\s*" + DATE + r"\s*(?=\|)", "| ", line)
    new = re.sub(r"[\[(]" + DATE + r"[\])]\s*[:|-]?\s*", "", new)
    new = re.sub(r"(?<![\w-])" + DATE + r"(?![\w-])\s*(?:[:|]|-(?!\d))?\s*", "", new)
    if new != line:
        body = new.rstrip("\r\n")
        tail = new[len(body):]
        new = body.rstrip(" \t") + tail if not body.lstrip().startswith("|") else new
    return new


def fix_em_dashes(line, lineno, events):
    if EM not in line:
        return line
    out = []
    parts = line.split(EM)
    out.append(parts[0])
    for nxt in parts[1:]:
        prev = out[-1]
        stripped_prev = prev.rstrip(" \t")
        after = nxt.lstrip(" \t")
        if not stripped_prev.strip():
            out[-1] = prev
            rep = ""
            kind = "removed"
            out.append(after)
        elif not after.strip():
            out[-1] = stripped_prev
            kind = "removed"
            out.append(after)
        elif re.match(r"[A-Z]", after) and re.search(r"[a-z0-9\)]$", stripped_prev) and len(after) > 0 and \
                re.match(r"[A-Z][a-z]", after):
            out[-1] = stripped_prev + "."
            out.append(" " + after)
            kind = "period"
        else:
            out[-1] = stripped_prev + ","
            out.append(" " + after)
            kind = "comma"
        events.append((lineno, kind))
    return "".join(out)


def rewrite_text(text, name, rw):
    """Return (new_text, counts, events, removed_attr). events are em dash records by source line."""
    ext = os.path.splitext(name)[1].lower()
    is_md = ext in (".md", ".markdown")
    is_json = ext == ".json"
    counts, em_events, attr_lines = {}, [], []
    out = []
    in_cl = False
    for i, line in enumerate(text.splitlines(keepends=True), start=1):
        if ATTRIBUTION.search(line):
            attr_lines.append(i)
            continue
        if not is_json and i <= 30:
            m = HEADER_DATE.match(line)
            if m:
                tail = " -->" if m.group(2).rstrip().endswith("-->") else ""
                new = m.group(1) + tail + m.group(3)
                if new != line:
                    counts["header-date"] = counts.get("header-date", 0) + 1
                line = new
        if not is_json:
            if CL_START.match(line):
                in_cl = True
            elif in_cl:
                if is_md:
                    if re.match(r"^#{1,6}\s", line):
                        in_cl = False
                else:
                    s = line.strip()
                    if not s or not re.match(r"^(#|//|\*|--|<!--)", s):
                        in_cl = False
                if in_cl:
                    new = strip_changelog_dates(line)
                    if new != line:
                        counts["changelog-date"] = counts.get("changelog-date", 0) + 1
                        line = new
        line = rw.line(line, counts)
        line = fix_em_dashes(line, i, em_events)
        out.append(line)
    if em_events:
        counts["em-dash"] = len(em_events)
    if attr_lines:
        counts["ai-attribution"] = len(attr_lines)
    return "".join(out), counts, em_events, attr_lines


def find_leftovers(text, name):
    ext = os.path.splitext(name)[1].lower()
    code = ext in (".py", ".json", ".js", ".ts")
    found = []
    for i, line in enumerate(text.splitlines(), start=1):
        def add(reason):
            found.append((i, reason))
        if POLITICAL.search(line):
            add("political word, remove or rewrite by hand")
        if PERSONAL_PATH.search(line):
            add("personal absolute path with no mapping")
        for m in IP.finditer(line):
            if m.group(0) not in ("127.0.0.1", "0.0.0.0"):
                add("IP address")
                break
        for m in EMAIL.finditer(line):
            if not EMAIL_OK.search(m.group(0)):
                add("email address")
                break
        for m in HOST.finditer(line):
            if not HOST_OK.search(m.group(0)):
                add("host name")
                break
        else:
            if HOST_SHAPE.search(line):
                add("host-like name")
        if TOKEN.search(line) or SECRET_ASSIGN.search(line):
            add("possible token or secret")
        for m in NAME_CUE.finditer(line):
            words = m.group(1).split()
            if all(w not in NOT_NAMES for w in words) and not CLIENT_RE.match(m.group(1)):
                add("unknown name that looks like a person")
                break
        if not code and HANDLE.search(line):
            add("@handle that may be a person")
    seen, uniq = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def file_kind_ok(path):
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        return data.decode("utf-8"), data
    except UnicodeDecodeError:
        return None, data


def collect(src):
    if os.path.isfile(src):
        return [(os.path.basename(src), src)]
    items = []
    for base, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        for f in sorted(files):
            if f in SKIP_NAMES:
                continue
            full = os.path.join(base, f)
            items.append((os.path.relpath(full, src), full))
    return items


def inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


def run(src, dest, config, denylist, dry_run=False, root=DEFAULT_ROOT, out=sys.stdout):
    src, dest = os.path.abspath(src), os.path.abspath(dest)
    if not os.path.exists(src):
        raise SystemExit("port: source not found: " + src)
    if not inside(dest, root):
        raise SystemExit("port: destination must be inside " + os.path.realpath(root))
    if inside(dest, src) or inside(src, dest):
        raise SystemExit("port: source and destination must not overlap")
    rw = Rewriter(config, denylist)
    results = []
    for rel, full in collect(src):
        if os.path.islink(full):
            results.append((rel, None, {}, [], [], [], "symlink skipped"))
            continue
        text, raw = file_kind_ok(full)
        mode = os.stat(full).st_mode & 0o7777
        if text is None:
            results.append((rel, (None, raw, mode), {}, [], [], [], "binary or unreadable, copied as is"))
            continue
        new, counts, em, attr = rewrite_text(text, rel, rw)
        left = find_leftovers(new, rel)
        results.append((rel, (new, None, mode), counts, em, attr, left, ""))
    for rel, payload, counts, em, attr, left, note in results:
        label = ", ".join("%s=%d" % kv for kv in sorted(counts.items())) or "no changes"
        out.write("%s: %s%s\n" % (rel, label, " (%s)" % note if note else ""))
        for ln, reason in left:
            out.write("  leftover %s:%d %s\n" % (rel, ln, reason))
    report = build_report(results)
    if dry_run:
        out.write("dry run: nothing written\n")
        return results
    for rel, payload, *_ in results:
        if payload is None:
            continue
        target = os.path.join(dest, rel)
        if not inside(target, dest):
            raise SystemExit("port: refusing to write outside destination: " + rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        text, raw, mode = payload
        with open(target, "wb") as fh:
            fh.write(raw if text is None else text.encode("utf-8"))
        os.chmod(target, mode)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "leftovers.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    return results


def build_report(results):
    lines = ["# Port leftovers", "",
             "Lines the tool could not safely rewrite. Line numbers are in the output file.",
             "No line content is repeated here on purpose.", "",
             "| File | Line | Reason |", "|---|---|---|"]
    n = 0
    for rel, payload, counts, em, attr, left, note in results:
        for ln, reason in left:
            lines.append("| %s | %d | %s |" % (rel, ln, reason))
            n += 1
    if n == 0:
        lines.append("| none | | |")
    lines += ["", "## Removed and replaced", "",
              "Line numbers are in the source file.", ""]
    any_change = False
    for rel, payload, counts, em, attr, left, note in results:
        for ln in attr:
            lines.append("- %s line %d: AI attribution line removed" % (rel, ln))
            any_change = True
        for ln, kind in em:
            lines.append("- %s line %d: em dash replaced (%s)" % (rel, ln, kind))
            any_change = True
        if note:
            lines.append("- %s: %s" % (rel, note))
            any_change = True
    if not any_change:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rewrite a source file or folder for Tollgate.")
    ap.add_argument("source")
    ap.add_argument("dest", help="destination folder, inside the Tollgate repo")
    ap.add_argument("--map", default=os.environ.get("TOLLGATE_PORT_MAP"),
                    help="private mapping file (env TOLLGATE_PORT_MAP)")
    ap.add_argument("--denylist", default=os.environ.get("TOLLGATE_DENYLIST"),
                    help="private term file, one per line (env TOLLGATE_DENYLIST)")
    ap.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="destination must be inside this folder")
    a = ap.parse_args(argv)
    config = load_json(os.path.join(HERE, "mappings.json"))
    if a.map:
        config = merge_config(config, load_json(a.map))
    run(a.source, a.dest, config, load_denylist(a.denylist), a.dry_run, a.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
