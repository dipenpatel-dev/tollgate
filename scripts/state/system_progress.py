#!/usr/bin/env python3
# Module:      system_progress.py
# Description: Scorecard for a Tollgate install. Layer 1 checks that the command files
#              carry their gates, layer 2 checks that hooks and scripts are in place,
#              layer 3 measures memory bloat (size and file counts). Read only.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Install health scorecard, read only
# Version:     1.0
# ChangeLog:
#   Initial version
"""Run:
    system_progress.py [--root DIR] [--memory-dir DIR] [--json]

DIR for --root is the installed Tollgate folder (default: the folder this script sits in,
two levels up). The memory folder defaults to the memory path from the path loader.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict, dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp  # noqa: E402

LAYER_1_TARGET = 95
LAYER_2_TARGET = 85
LAYER_3_TARGET = 40
MEMORY_KB_CAP = 60
MEMORY_KB_TARGET = 30
FEEDBACK_TARGET = 150
BAR_WIDTH = 20
MEMORY_INDEX = "MEMORY.md"
MEMORY_PREFIXES = ("feedback_", "project_", "reference_", "user_")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


def file_contains(path: pathlib.Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def size_kb(path: pathlib.Path) -> float:
    try:
        return path.stat().st_size / 1024
    except OSError:
        return 0.0


def layer_1_checks(root: pathlib.Path) -> list[Check]:
    """Layer 1: the command files exist and carry their gates."""
    cmd = root / "commands"
    return [
        Check("arch command exists", (cmd / "tg-arch.md").exists()),
        Check("dev command exists", (cmd / "tg-dev.md").exists()),
        Check("qa command exists", (cmd / "tg-qa.md").exists()),
        Check("spec command exists", (cmd / "tg-spec.md").exists()),
        Check("close command exists", (cmd / "tg-close.md").exists()),
        Check("handoff command exists", (cmd / "tg-handoff.md").exists()),
        Check("dev command names DOCUMENTED and VALIDATED",
              file_contains(cmd / "tg-dev.md", "DOCUMENTED") and file_contains(cmd / "tg-dev.md", "VALIDATED")),
        Check("gate lines page present", (root / "docs" / "gate-lines.md").exists()),
        Check("variables page present", (root / "docs" / "variables.md").exists()),
    ]


def layer_2_checks(root: pathlib.Path) -> list[Check]:
    """Layer 2: mechanisms that enforce the rules."""
    hooks = root / "hooks"
    scripts = root / "scripts"
    return [
        Check("gate rules hook present", (hooks / "gate_rules.py").exists()),
        Check("gate check hook present", (hooks / "pre-prompt-expansion-check-gates.py").exists()),
        Check("secret scan hook present", (hooks / "post-tool-bash-scan-secrets.py").exists()),
        Check("settings file present", (root / "settings.json").exists()),
        Check("hooks wired in settings", file_contains(root / "settings.json", "hooks")),
        Check("path loader present", (scripts / "core" / "paths.py").exists()),
        Check("search scripts present", (scripts / "search").is_dir()),
        Check("sweep script present", (scripts / "sync" / "sweep").exists()),
        Check("state scripts present", (scripts / "state").is_dir()),
        Check("cron folder present", (scripts / "cron").is_dir()),
    ]


def layer_3_metrics(memory_dir: pathlib.Path) -> dict:
    """Layer 3: memory bloat. Lower is better."""
    memory_kb = size_kb(memory_dir / MEMORY_INDEX)
    counts = {prefix.rstrip("_"): 0 for prefix in MEMORY_PREFIXES}
    if memory_dir.is_dir():
        for entry in memory_dir.iterdir():
            if not entry.is_file() or not entry.name.endswith(".md"):
                continue
            for prefix in MEMORY_PREFIXES:
                if entry.name.startswith(prefix):
                    counts[prefix.rstrip("_")] += 1
                    break
    size_pct = min(memory_kb / MEMORY_KB_CAP, 5.0) * 100
    count_pct = min(counts["feedback"] / FEEDBACK_TARGET, 5.0) * 100
    return {
        "memory_kb": round(memory_kb, 1),
        "memory_cap_kb": MEMORY_KB_CAP,
        "memory_target_kb": MEMORY_KB_TARGET,
        "feedback_count": counts["feedback"],
        "feedback_target": FEEDBACK_TARGET,
        "project_count": counts["project"],
        "reference_count": counts["reference"],
        "user_count": counts["user"],
        "bloat_pct": round((size_pct + count_pct) / 2),
    }


def bar(pct: int, width: int = BAR_WIDTH) -> str:
    capped = max(0, min(pct, 100))
    filled = int(width * capped / 100)
    return "#" * filled + "." * (width - filled)


def _pct(checks: list[Check]) -> int:
    return round(sum(1 for c in checks if c.passed) / len(checks) * 100) if checks else 0


def render_text(layer1: list[Check], layer2: list[Check], layer3: dict) -> str:
    lines = ["=" * 64, "TOLLGATE SYSTEM PROGRESS", "=" * 64, ""]
    for title, checks, target, ok_word, bad_word in (
        ("LAYER 1: RULEBOOK", layer1, LAYER_1_TARGET, "PASS", "FAIL"),
        ("LAYER 2: MECHANISMS", layer2, LAYER_2_TARGET, "LIVE", "PEND"),
    ):
        pct = _pct(checks)
        gap = "HIT TARGET" if pct >= target else "{} pts to {}%".format(target - pct, target)
        lines.append("{:<28}{:>3}%   {}".format(title, pct, bar(pct)))
        lines.append("    Target: {}%    {}".format(target, gap))
        for c in checks:
            lines.append("    {}  {}".format(ok_word if c.passed else bad_word, c.name))
        lines.append("")
    bloat = layer3["bloat_pct"]
    gap = "HIT TARGET" if bloat <= LAYER_3_TARGET else "{} pts over {}%".format(bloat - LAYER_3_TARGET, LAYER_3_TARGET)
    lines.append("{:<28}{:>3}%   {}".format("LAYER 3: MEMORY BLOAT", bloat, bar(min(bloat, 100))))
    lines.append("    Target: {}% or below    {}".format(LAYER_3_TARGET, gap))
    lines.append("    {} size:  {} KB (cap {}, target {})".format(
        MEMORY_INDEX, layer3["memory_kb"], layer3["memory_cap_kb"], layer3["memory_target_kb"]))
    lines.append("    Feedback files:  {} (target {})".format(layer3["feedback_count"], layer3["feedback_target"]))
    lines.append("    Project files:   {}".format(layer3["project_count"]))
    lines.append("    Reference files: {}".format(layer3["reference_count"]))
    lines.append("    User files:      {}".format(layer3["user_count"]))
    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def render_json(layer1: list[Check], layer2: list[Check], layer3: dict) -> str:
    return json.dumps({
        "layer_1": {"pct": _pct(layer1), "target": LAYER_1_TARGET, "checks": [asdict(c) for c in layer1]},
        "layer_2": {"pct": _pct(layer2), "target": LAYER_2_TARGET, "checks": [asdict(c) for c in layer2]},
        "layer_3": layer3,
    }, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tollgate install scorecard.")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument("--memory-dir", type=pathlib.Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)
    try:
        memory_dir = args.memory_dir if args.memory_dir else get_path("memory")
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return 2
    layer1 = layer_1_checks(args.root)
    layer2 = layer_2_checks(args.root)
    layer3 = layer_3_metrics(memory_dir)
    print(render_json(layer1, layer2, layer3) if args.json else render_text(layer1, layer2, layer3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
