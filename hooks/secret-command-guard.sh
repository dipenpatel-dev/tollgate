#!/usr/bin/env bash
# Trigger: PreToolUse, Bash
# Scope: all repos
# Action: block command shapes that print a credential or private key
# On result: exit 2 with a stderr message blocks; exit 0 allows
# If filter: the command matches a known secret leaking shape
# SPEED BUMP, NOT A SECURITY BOUNDARY: this is a pattern check on the command text, not a sandbox and not a shell parser.
#             It does not catch indirect exposure (a script that reads a secret and prints it,
#             a name built from pieces, a value copied through a file or a variable chain it
#             cannot see). The main protection is a secret store plus environment variables.
#             This hook catches the common ways a secret ends up typed into Bash directly.
#             Credential values inside a command are caught by scrub_secrets.py.
#
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# ChangeLog:
#   - Merged the older command scan with the SSH and private key checks.
#   - Fails closed (exit 2) when the payload cannot be parsed. Also blocks security -g and
#     dump-keychain, reads of the AWS credentials file, .netrc, the Databricks config and
#     /proc/self/environ, and /usr/bin/env with no command.
#   - Added OS secret store reads, gh auth token, quoted and braced variable prints, bare
#     environment dumps, .env files and private key files by name.

set -uo pipefail

input=$(cat)

# Fail closed: a payload that cannot be read blocks the command (exit 2). A readable payload with
# no command in it is allowed.
cmd=$(python3 -c "
import sys, json
d = json.load(sys.stdin)
if not isinstance(d, dict):
    raise ValueError('payload is not an object')
ti = d.get('tool_input') or {}
c = ti.get('command') if isinstance(ti, dict) else None
print(c if isinstance(c, str) else '')
" <<< "$input" 2>/dev/null) || {
    printf '\nBLOCKED: secret-command-guard could not read the tool payload, so the command is blocked.\n\n' >&2
    exit 2
}

if [ -z "$cmd" ]; then
    exit 0
fi

block() {
    printf '\nBLOCKED: This command may expose a credential or private key.\n' >&2
    printf 'Pattern: %s\n' "$1" >&2
    printf '%s\n\n' "$2" >&2
    exit 2
}

# SSH or PEM private key material read or printed directly
if printf '%s' "$cmd" | grep -qE '(cat|less|more|head|tail|bat|pbcopy|cp|scp)\b[^|&;]*(\.ssh/id_(rsa|dsa|ecdsa|ed25519)(\.pub)?\b|\.ssh/[A-Za-z0-9_.-]*\bkey\b|\.pem\b)'; then
    if ! printf '%s' "$cmd" | grep -qE '\.pub\b'; then
        block "SSH or PEM private key file read" "Keys belong in your secret store or keychain, not printed to a session. If this is a .pub file, say so explicitly; public keys are not secret."
    fi
fi

if printf '%s' "$cmd" | grep -qiE 'BEGIN( [A-Z]+)? PRIVATE KEY'; then
    block "inline PEM private key header" "A private key is being written inline in a command. Stop and move it to your secret store."
fi

if printf '%s' "$cmd" | grep -qE 'ssh-keygen[[:space:]]+-y\b'; then
    block "ssh-keygen with the -y flag (derives a public key from a private key file)" "Confirm this is intentional and the output is a public key only before proceeding."
fi

# Credential config dumps, environment dumps and token echoes
if printf '%s' "$cmd" | grep -qE 'databricks configure'; then
    block "databricks configure" "Verify no secrets will appear before proceeding. Use the keychain or environment variables instead."
fi

if printf '%s' "$cmd" | grep -qE 'env[[:space:]]*\|.*grep|printenv'; then
    block "env pipe or printenv" "Verify no secrets will appear before proceeding."
fi

# Credential files read by name (reader command or a < redirect), and the process environment
if printf '%s' "$cmd" | grep -qE '(\.aws/credentials|\.netrc|\.databrickscfg|/proc/self/environ)' \
   && printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])(cat|less|more|head|tail|bat|pbcopy|xxd|od|strings|base64|grep|egrep|awk|sed|cut|tr|tee|cp|scp|source|python3?|perl|ruby|node)\b|<'; then
    block "credential file read (AWS credentials, .netrc, Databricks config or /proc/self/environ)" "These files hold secrets. Name the one setting you need and check its presence instead."
fi

if printf '%s' "$cmd" | grep -qiE 'echo[[:space:]]+\$[A-Za-z_]*(TOKEN|KEY|SECRET|PASSWORD)[A-Za-z_]*'; then
    block "echo of a TOKEN, KEY, SECRET or PASSWORD variable" "Verify no secrets will appear before proceeding."
fi

# OS secret store reads: the password value is printed with -w
if printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])security[[:space:]]+(find-generic-password|find-internet-password)\b' \
   && printf '%s' "$cmd" | grep -qE '[[:space:]]-[A-Za-z]*[wg][A-Za-z]*([[:space:]]|$)'; then
    block "OS keychain password read (security find-*-password with -w or -g)" "Do not print a stored password into the session. Use the secret store from your own terminal."
fi

if printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])security[[:space:]]+dump-keychain\b'; then
    block "security dump-keychain" "This lists keychain items and can print their secrets. Run it yourself outside the session if you need it."
fi

if printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])secret-tool[[:space:]]+lookup\b'; then
    block "secret-tool lookup" "Do not print a stored secret into the session."
fi

if printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])gh[[:space:]]+auth[[:space:]]+token\b'; then
    block "gh auth token" "This prints a live access token. Run it yourself outside the session if you need it."
fi

# Printing a secret variable, quoted, braced or not (echo, printf, print, cat)
if printf '%s' "$cmd" | grep -qiE '(^|[^A-Za-z0-9_-])(echo|printf|print|cat)\b[^;&|]*\$\{?[A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Za-z0-9_]*'; then
    block "print of a KEY, TOKEN, SECRET, PASSWORD or PASSWD variable" "Verify no secrets will appear before proceeding."
fi

# Bare environment dumps. A prefix such as `env VAR=x cmd` is allowed. A dump that keeps only the
# names (cut -d= -f1 or sed 's/=.*//') is allowed.
NAMES_ONLY=0
if printf '%s' "$cmd" | grep -qE "cut[[:space:]]+-d[[:space:]]*['\"]?=['\"]?[[:space:]]+-f1|s/=\.\*//"; then
    NAMES_ONLY=1
fi
if [ "$NAMES_ONLY" -eq 0 ] && printf '%s' "$cmd" | grep -qE '(^|[;&|(`]|\$\()[[:space:]]*([^[:space:];&|()`]*/)?(env|set|(export|declare|typeset)[[:space:]]+-[A-Za-z]*p[A-Za-z]*)[[:space:]]*($|[;&|)`<>])'; then
    block "bare environment dump (env, set, export -p, declare -p)" "A dump prints every secret in the environment. Name the one variable you need and check its length or presence instead."
fi

# .env files and private key files read by name
if printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])(cat|less|more|head|tail|bat|pbcopy|xxd|od|strings|base64|grep|awk|sed)\b[^|&;]*(^|[/[:space:]'"'"'"~])\.env(\.[A-Za-z0-9_-]+)?($|[[:space:]'"'"'"/;&|)])'; then
    if ! printf '%s' "$cmd" | grep -qE '\.env\.(example|sample|template|dist)\b'; then
        block ".env file read" "An .env file holds secrets. Read the variable names from .env.example instead."
    fi
fi

no_pub=$(printf '%s' "$cmd" | sed -E 's#[A-Za-z0-9_./~-]*\.pub([^A-Za-z0-9_]|$)# #g')
if printf '%s' "$no_pub" | grep -qE '(^|[^A-Za-z0-9_-])(cat|less|more|head|tail|bat|pbcopy|xxd|od|strings|base64|cp|scp)\b' \
   && printf '%s' "$no_pub" | grep -qE '(id_(rsa|dsa|ecdsa|ed25519)($|[^A-Za-z0-9_])|[A-Za-z0-9_-]\.(pem|key|p12|pfx)($|[^A-Za-z0-9_]))'; then
    block "private key file read by name" "Keys belong in your secret store or keychain, not printed to a session. A .pub file is fine."
fi

exit 0
