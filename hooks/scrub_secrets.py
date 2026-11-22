#!/usr/bin/env python3
"""
Trigger: PreToolUse (Bash, Write, Edit, NotebookEdit) and PostToolUse (all tools)
Scope: one secret scrubber with two modes, chosen from the hook payload
Action:
  PreToolUse  - scan the Bash command, or the text being written to a file, for real
                credential values. A match is denied before the tool runs.
  PostToolUse - scan the tool output, redact matches, and hand Claude the scrubbed copy
                as additionalContext. PostToolUse cannot hide the raw result.
Fails closed: bad input or an internal error exits 2 with a stderr message
Registry: secret_var_registry.txt (next to this file, or SCRUB_REGISTRY_PATH) lists extra
          variable names whose values must never appear. One name per line.
Known limit: it cannot scrub a secret the user types into the chat.
Messages carry the label only, never the matched text.

Author: Dipen Patel (dipenpatel-dev)
Date:
ChangeLog:
  - Added more value shapes (sk-proj and other hyphenated OpenAI keys, Stripe, Google, npm, Hugging
    Face, GitLab, SendGrid, JWT, URL credentials, Slack webhook, curl -u, Bearer tokens), fixed the
    word boundary so KEY_AKIA... is caught, added the quoted password/token assignment scan for
    text being written, and normalise zero-width and compatibility characters before matching.
  - Added the Plane key shape (plane_api_ plus 20 or more characters) and the JSON quoted form
    "api_key": "<long value>" (also token and secret).
  - Fails closed: bad input or an internal error exits 2.
  - Merged the PostToolUse output scrubber and the PreToolUse command scan into one entry point.
  - Added the PreToolUse file write scan and the variable name registry.
"""

from __future__ import annotations

import json
import os
import re
import sys

# Tools whose output cannot hold an outside credential (internal status only).
POST_DENYLIST = {"Edit", "Write", "MultiEdit", "NotebookEdit", "TodoWrite"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# A JSON object member such as "api_key": "<long value>". The quote between the name and the colon
# is why the loose name=value pattern below misses this form.
JSON_SECRET_PATTERN = (
    r'(?i)"(?:api_?key|api_?token|access_?token|client_?secret|token|secret)"\s*:\s*'
    r'"[A-Za-z0-9!@#$%^&*()+\-_./=]{20,}"'
)

# Value shapes that are specific enough to block on. Order matters: the more specific
# label must come before the generic one that could match the same text.
SPECIFIC_PATTERNS = [
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "ANTHROPIC_KEY"),
    (r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])", "AWS_ACCESS_KEY"),
    (r"ATATT[A-Za-z0-9]{30,}", "ATLASSIAN_TOKEN"),
    (r"dapi[0-9a-f]{32}", "DATABRICKS_PAT"),
    (r"github_pat_[A-Za-z0-9_]{40,}", "GITHUB_PAT"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GITHUB_TOKEN"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "SLACK_TOKEN"),
    (r"sk-[A-Za-z0-9]{20,}", "OPENAI_KEY"),
    (r"(?<![A-Za-z0-9])sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}", "OPENAI_KEY"),
    (r"plane_api_[A-Za-z0-9]{20,}", "PLANE_KEY"),
    (r"(?<![A-Za-z0-9])[sr]k_live_[A-Za-z0-9]{16,}", "STRIPE_KEY"),
    (r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}", "GOOGLE_API_KEY"),
    (r"(?<![A-Za-z0-9])npm_[A-Za-z0-9]{36}", "NPM_TOKEN"),
    (r"(?<![A-Za-z0-9])hf_[A-Za-z0-9]{30,}", "HUGGINGFACE_TOKEN"),
    (r"(?<![A-Za-z0-9])glpat-[A-Za-z0-9_-]{20,}", "GITLAB_TOKEN"),
    (r"(?<![A-Za-z0-9])SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}", "SENDGRID_KEY"),
    (r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}", "JWT"),
    (r"://[^\s/:@'\"]+:(?![<$\{%\[]|(?:pass(?:word)?|secret|changeme|x{3,}|\*+)@)[^\s/@'\"]{3,}@[A-Za-z0-9.-]+", "URL_CREDENTIAL"),
    (r"hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9/_-]{20,}", "SLACK_WEBHOOK"),
    (r"(?i)\bcurl\b[^\n;&|]*?\s(?:-u\s*|--user[\s=]+)['\"]?[^\s'\":$<{]+:(?![<$\{%\[])[^\s'\"]{3,}",
     "CURL_CREDENTIAL"),
    (r"(?i)\bBearer\s+(?![<$\{%\[])(?=[A-Za-z._~+/=-]*\d)[A-Za-z0-9._~+/=-]{24,}", "BEARER_TOKEN"),
    (JSON_SECRET_PATTERN, "JSON_CREDENTIAL"),
    (r"AccountKey=[A-Za-z0-9+/=]{40,}", "AZURE_STORAGE_KEY"),
    (r"(?i)\bsig=[A-Za-z0-9%+/=]{20,}", "AZURE_SAS"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "PRIVATE_KEY"),
]

# A quoted value assigned to a name that ends in password, secret, token or api key, in text being
# written (password = "...", "token": "..."). Used only for file writes, never for output scrubbing.
WRITE_ASSIGNMENT_PATTERNS = [
    (
        r'(?i)\b\w*(?:password|passwd|secret|token|api_?key)["\']?\s*[:=]\s*["\']'
        r'(?![<$\{%\[*]|[^"\'\s]*(?:your|change|example|placeholder|redacted|x{4}|dummy|fake|sample)'
        r'|(?:test|none|null|true|false|env|todo)(?:\W|$)|[A-Z0-9]+_[A-Z0-9_]+["\'])'
        r'[^"\'\s]{8,}["\']',
        "ASSIGNED_SECRET",
    ),
]

# Looser shapes. Used only when scrubbing output, where a false hit costs nothing.
LOOSE_PATTERNS = [
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

# A command that exports a secret with a literal value (not a variable or a subshell).
COMMAND_EXPORT = re.compile(
    r'(?i)\bexport\s+\w*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\w*=["\']?(?![$`(])[^\s"\'$`]{8,}'
)


def normalize(text: str) -> str:
    """Drop zero-width characters and fold compatibility forms (shared with the PHI scanner)."""
    if text.isascii():
        return text
    from phi_patterns import normalize_text  # same folder as this file; an import error blocks
    return normalize_text(text)


def registry_path() -> str:
    override = os.environ.get("SCRUB_REGISTRY_PATH")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret_var_registry.txt")


def load_registry() -> list[str]:
    """Variable names from the registry file. A missing or unreadable file gives no names."""
    names: list[str] = []
    try:
        with open(registry_path(), encoding="utf-8") as fh:
            for line in fh:
                token = line.split("#", 1)[0].strip()
                if token and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                    names.append(token)
    except OSError:
        pass
    return names


def registry_patterns() -> list[tuple[str, str]]:
    return [
        (r'(?i)\b' + re.escape(name) + r'''\s*[=:]\s*(?![$`(])[^\s"']{8,}''', "CUSTOM_CRED")
        for name in load_registry()
    ]


def collect_strings(value: object, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            collect_strings(item, out)
    elif isinstance(value, list):
        for item in value:
            collect_strings(item, out)


def extract_text(resp: object) -> str:
    parts: list[str] = []
    collect_strings(resp, parts)
    return "\n".join(p for p in parts if p and p.strip())


def labels_in(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    text = normalize(text)
    for pattern, label in patterns:
        if re.search(pattern, text) and label not in found:
            found.append(label)
    return found


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def written_texts(tool: str, tool_input: dict) -> list[str]:
    if tool == "Write":
        values = [tool_input.get("content")]
    elif tool == "Edit":
        values = [tool_input.get("new_string")]
    elif tool == "MultiEdit":  # not a current tool name; kept so an old payload parses harmlessly
        values = [e.get("new_string") for e in (tool_input.get("edits") or []) if isinstance(e, dict)]
    elif tool == "NotebookEdit":
        values = [tool_input.get("new_source")]
    else:
        values = []
    return [v for v in values if isinstance(v, str) and v]


def run_pre(payload: dict) -> None:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    patterns = SPECIFIC_PATTERNS + registry_patterns()
    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command:
            return
        labels = labels_in(command, patterns)
        if COMMAND_EXPORT.search(command) and "ENV_SECRET" not in labels:
            labels.append("ENV_SECRET")
        if labels:
            deny("A credential value (" + ", ".join(labels) + ") is in this command. "
                 "Keep secrets in your secret store or an environment variable, never typed "
                 "into a command. Remove the value and retry.")
    elif tool in WRITE_TOOLS:
        labels = []
        for text in written_texts(tool, tool_input):
            for label in labels_in(text, patterns + WRITE_ASSIGNMENT_PATTERNS):
                if label not in labels:
                    labels.append(label)
        if labels:
            deny("A credential value (" + ", ".join(labels) + ") is in the text being written. "
                 "Secrets never go into files. Write a placeholder or read the value from the "
                 "environment, then retry.")


def run_post(payload: dict) -> None:
    if payload.get("tool_name", "") in POST_DENYLIST:
        return
    response = payload.get("tool_response")
    if response is None:
        return
    output = extract_text(response)
    if not output.strip():
        return
    findings: list[str] = []
    scrubbed = normalize(output)
    for pattern, label in SPECIFIC_PATTERNS + LOOSE_PATTERNS + registry_patterns():
        def _replace(match: re.Match, lbl: str = label) -> str:
            findings.append(lbl)
            return "[REDACTED:" + lbl + "]"
        scrubbed = re.sub(pattern, _replace, scrubbed)
    if not findings:
        return
    types = ", ".join(sorted(set(findings)))
    additional = (
        "SECURITY HOOK: " + str(len(findings)) + " credential(s) scrubbed from tool output.\n"
        "Types detected: " + types + "\n"
        "Do not use or repeat the raw values. Use this sanitized copy.\n\n"
        "Sanitized output:\n" + scrubbed
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": additional}
    }))


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.stderr.write("scrub_secrets: payload is not JSON; blocking (fails closed).\n")
        sys.exit(2)
    if not isinstance(payload, dict):
        sys.stderr.write("scrub_secrets: payload is not an object; blocking (fails closed).\n")
        sys.exit(2)
    event = payload.get("hook_event_name")
    if event == "PostToolUse" or (event is None and "tool_response" in payload):
        run_post(payload)
    elif event == "PreToolUse" or event is None:
        run_pre(payload)


def scrub_text(text: str) -> tuple[str, list[str]]:
    """Redact every credential shape in text. Return (scrubbed text, labels found, never the values).

    Imported by scripts that write transcripts into the vault, so they use the same rules as the hook.
    """
    labels: list[str] = []
    scrubbed = normalize(text)
    for pattern, label in SPECIFIC_PATTERNS + LOOSE_PATTERNS + registry_patterns():
        def _replace(match: re.Match, lbl: str = label) -> str:
            if lbl not in labels:
                labels.append(lbl)
            return "[REDACTED:" + lbl + "]"
        scrubbed = re.sub(pattern, _replace, scrubbed)
    if not labels:
        return text, labels  # nothing found: hand back the original, not the folded copy
    return scrubbed, labels


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        sys.stderr.write("scrub_secrets: %s; blocking (fails closed).\n" % type(exc).__name__)
        sys.exit(2)
    sys.exit(0)
