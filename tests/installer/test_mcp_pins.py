#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: every MCP server that install.sh starts through npx is registered with an exact pinned version
Ticket: none
ChangeLog:
  - Created.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALL = os.path.join(HERE, "..", "..", "install.sh")
# A package argument after "npx -y": optional @scope/, name, then @x.y.z (or a date version like 2025.4.25).
PINNED = re.compile(r"^(@[a-z0-9._-]+/)?[a-z0-9._-]+@\d+(\.\d+){1,3}$")


def registered_commands() -> list[str]:
    """Run the MCP step of install.sh with every method on API and a stub `claude`; return what it registered."""
    with open(INSTALL, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index('ATLASSIAN_MCP_URL="')
    end = text.index('ok "Service connections saved"')
    block = text[start:end]
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("claude", "npx"):
            path = os.path.join(tmp, name)
            with open(path, "w") as fh:
                fh.write('#!/bin/sh\necho "$@" >> "$LOGFILE"\n' if name == "claude" else "#!/bin/sh\nexit 0\n")
            os.chmod(path, 0o755)
        log = os.path.join(tmp, "claude.log")
        script = (
            "ok() { :; }; note() { :; }\n"
            "ATLASSIAN_METHOD=api; NOTION_METHOD=api; SLACK_METHOD=api\n"
            + block + "\nfi\n"
        )
        env = {"PATH": tmp + ":/usr/bin:/bin", "LOGFILE": log, "HOME": tmp}
        subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True)
        with open(log, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    return [ln for ln in lines if ln.startswith("mcp add")]


class McpPins(unittest.TestCase):
    def test_three_npx_servers_are_registered(self):
        cmds = registered_commands()
        self.assertEqual(3, len(cmds), cmds)

    def test_every_npx_package_is_pinned(self):
        for cmd in registered_commands():
            m = re.search(r"exec npx -y (\S+)", cmd)
            self.assertIsNotNone(m, cmd)
            self.assertRegex(m.group(1), PINNED, f"unpinned package in: {cmd}")

    def test_slack_summary_line_says_unsupported(self):
        with open(INSTALL, encoding="utf-8") as fh:
            text = fh.read()
        func = text[text.index("_conn_label() {"):]
        func = func[:func.index("\n}\n") + 3]
        line = next(ln for ln in text.splitlines() if '"Slack:"' in ln)
        script = func + "\nSLACK_METHOD=api\n" + line + "\n"
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
        self.assertIn("unsupported", out)
        self.assertIn("Connected (API key)", out)
        self.assertIn("unsupported", text.split("echo \"  ── Slack ──\"")[1].split("choose_connection")[0])


if __name__ == "__main__":
    unittest.main()
