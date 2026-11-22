#!/usr/bin/env python3
"""
Trigger: PostToolUse - all tools (matcher: ""); internal write tools skipped via TOOL_DENYLIST
Scope: every tool result (Bash stdout/stderr, Read file content, MCP text) before the model reasons over it
Action: scan output text for credential patterns, redact matches
On secrets found: prints JSON with hookEventName + additionalContext containing scrubbed output and warning
Note: PostToolUse cannot suppress results; the model has already received the raw text.
      additionalContext instructs Claude not to use or repeat raw secrets.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phi_patterns import collect_texts  # noqa: E402
from scrub_secrets import SPECIFIC_PATTERNS as SHARED_SPECIFIC, normalize  # noqa: E402

HOOK_EVENT = "PostToolUse"


def extract_text(resp: object) -> str:
    """Join stdout, stderr, file content, and MCP text; fall back to the raw response."""
    texts = collect_texts(resp)
    if texts:
        return "\n".join(texts)
    return json.dumps(resp) if resp else ""


# Tools whose output cannot contain externally-sourced credentials.
# Write/Edit/MultiEdit/NotebookEdit/TodoWrite return only internal operation status.
TOOL_DENYLIST = {"Edit", "Write", "MultiEdit", "NotebookEdit", "TodoWrite"}

SECRET_PATTERNS = [
    # Anthropic key must precede the generic sk- pattern so ANTHROPIC_KEY label wins
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "ANTHROPIC_KEY"),
    (r"ATATT[A-Za-z0-9]{30,}", "JIRA_TOKEN"),
    (r"dapi[0-9a-f]{32}", "DATABRICKS_PAT"),
    # github_pat_ must precede gh[pousr]_ so the fine-grained PAT label wins
    (r"github_pat_[A-Za-z0-9_]{40,}", "GITHUB_PAT"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GITHUB_TOKEN"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "SLACK_TOKEN"),
    # sk- comes after sk-ant- so the Anthropic label wins when both could match
    (r"sk-[A-Za-z0-9]{20,}", "OPENAI_KEY"),
    (r"plane_api_[A-Za-z0-9]{20,}", "PLANE_KEY"),
    (
        r'(?i)"(?:api_?key|api_?token|access_?token|client_?secret|token|secret)"\s*:\s*'
        r'"[A-Za-z0-9!@#$%^&*()+\-_./=]{20,}"',
        "JSON_CREDENTIAL",
    ),
    (r"AccountKey=[A-Za-z0-9+/=]{40,}", "AZURE_STORAGE_KEY"),
    (r"(?i)\bsig=[A-Za-z0-9%+/=]{20,}", "AZURE_SAS"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "PRIVATE_KEY"),
    (r"(?i)(?:Authorization|Bearer):\s*\S{20,}", "AUTH_TOKEN"),
    (
        r'(?i)(?:api_?key|api_?token|access_?token|secret_?key|password|passwd'
        r'|token|client_?secret|connection_?string)'
        r'\s*[=:]\s*["\']?[A-Za-z0-9!@#$%^&*()+\-_./=]{16,}["\']?',
        "CREDENTIAL",
    ),
    (
        r'(?i)export\s+\w*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\w*=["\']?[^\s"\']{8,}["\']?',
        "ENV_SECRET",
    ),
]

# Shapes added after the first release live in scrub_secrets.py so the two scanners cannot drift.
# They go first; the lists above keep their own labels (JIRA_TOKEN here, ATLASSIAN_TOKEN there).
_SHARED_LABELS = {"AWS_ACCESS_KEY", "STRIPE_KEY", "GOOGLE_API_KEY", "NPM_TOKEN", "HUGGINGFACE_TOKEN",
                  "GITLAB_TOKEN", "SENDGRID_KEY", "JWT", "URL_CREDENTIAL", "SLACK_WEBHOOK",
                  "CURL_CREDENTIAL", "BEARER_TOKEN"}
_OPENAI_SHARED = [(p, lbl) for p, lbl in SHARED_SPECIFIC if lbl == "OPENAI_KEY" and "proj" in p]
SECRET_PATTERNS = ([(p, lbl) for p, lbl in SHARED_SPECIFIC if lbl in _SHARED_LABELS]
                   + _OPENAI_SHARED + SECRET_PATTERNS)


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        sys.stderr.write("post-tool-bash-scan-secrets: payload is not JSON (fails closed).\n")
        sys.exit(2)
    if not isinstance(payload, dict):
        sys.stderr.write("post-tool-bash-scan-secrets: payload is not an object (fails closed).\n")
        sys.exit(2)

    if payload.get("tool_name", "") in TOOL_DENYLIST:
        sys.exit(0)

    tool_response = payload.get("tool_response")
    if tool_response is None:
        sys.exit(0)

    output = extract_text(tool_response)
    if not output.strip():
        sys.exit(0)

    findings = []
    scrubbed = normalize(output)

    for pattern, label in SECRET_PATTERNS:
        def _make_replacer(lbl):
            def _replace(m):
                findings.append((lbl, m.group(0)[:30]))
                return "[REDACTED:" + lbl + "]"
            return _replace
        scrubbed = re.sub(pattern, _make_replacer(label), scrubbed)

    if not findings:
        sys.exit(0)

    n = len(findings)
    types_found = ", ".join(sorted(set(lbl for lbl, _ in findings)))
    additional = (
        "SECURITY HOOK: " + str(n) + " credential(s) scrubbed from tool output.\n"
        "Types detected: " + types_found + "\n\n"
        "Sanitized output:\n" + scrubbed
    )

    result = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "additionalContext": additional,
        }
    }
    print(json.dumps(result))
    sys.exit(0)


main()
