#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for secret-command-guard.sh
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_secret_command_guard.py
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest

HOOK = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "hooks", "secret-command-guard.sh")


def run(command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([HOOK], input=payload, capture_output=True, text=True)


class SecretCommandGuard(unittest.TestCase):
    def test_HOK_02_block_is_exit_2_with_stderr(self) -> None:
        result = run("print" + "env")
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED", result.stderr)

    def test_HOK_03_blocks_inline_private_key_header(self) -> None:
        header = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
        self.assertEqual(run("echo '" + header + "' > k").returncode, 2)

    def test_blocks_key_file_read_but_not_public_key(self) -> None:
        self.assertEqual(run("cat ~/.ssh/id_" + "ed25519").returncode, 2)
        self.assertEqual(run("cat ~/.ssh/id_" + "ed25519.pub").returncode, 0)

    def test_blocks_token_echo(self) -> None:
        self.assertEqual(run("echo $MY_API_TOKEN").returncode, 2)

    def test_allows_normal_command_and_empty(self) -> None:
        self.assertEqual(run("ls -la").returncode, 0)
        self.assertEqual(run("").returncode, 0)


class SecretCommandGuardPatterns(unittest.TestCase):
    def assertBlocked(self, command: str) -> None:
        result = run(command)
        self.assertEqual(result.returncode, 2, command)
        self.assertIn("BLOCKED", result.stderr)

    def assertAllowed(self, command: str) -> None:
        self.assertEqual(run(command).returncode, 0, command)

    def test_os_secret_store_reads(self) -> None:
        self.assertBlocked("security find-generic-password -s myname -w")
        self.assertBlocked("security find-internet-password -s host -a me -w")
        self.assertBlocked("x=$(security find-generic-password -w -s myname)")
        self.assertBlocked("secret-tool lookup service myname")

    def test_os_secret_store_without_value_flag_is_allowed(self) -> None:
        self.assertAllowed("security find-generic-password -s myname")
        self.assertAllowed("security list-keychains")

    def test_gh_auth_token(self) -> None:
        self.assertBlocked("gh auth token")
        self.assertBlocked("export T=$(gh auth token)")
        self.assertAllowed("gh auth status")

    def test_variable_prints_quoted_and_braced(self) -> None:
        self.assertBlocked('echo "$MY_TOKEN"')
        self.assertBlocked("echo ${X_KEY}")
        self.assertBlocked("printf %s $DATABRICKS_TOKEN")
        self.assertBlocked("print $SOME_SECRET")
        self.assertBlocked("cat $DB_PASSWORD")
        self.assertBlocked('echo "pw is ${APP_PASSWD}"')
        self.assertBlocked("print" + "env MY_TOKEN")

    def test_variable_prints_of_other_names_are_allowed(self) -> None:
        self.assertAllowed("echo $HOME")
        self.assertAllowed('echo "$PATH"')
        self.assertAllowed("printf %s ${USER}")

    def test_bare_environment_dumps(self) -> None:
        self.assertBlocked("env")
        self.assertBlocked("env | sort")
        self.assertBlocked("set")
        self.assertBlocked("export -p")
        self.assertBlocked("declare -p")
        self.assertBlocked("cd /tmp && env")
        self.assertBlocked("set | less")

    def test_env_prefix_and_set_options_are_allowed(self) -> None:
        self.assertAllowed("env FOO=1 python3 x.py")
        self.assertAllowed("env -i bash -c true")
        self.assertAllowed("set -euo pipefail")
        self.assertAllowed("export FOO=bar")
        self.assertAllowed("env | cut -d= -f1")

    def test_env_files(self) -> None:
        self.assertBlocked("cat .env")
        self.assertBlocked("cat ./app/.env")
        self.assertBlocked("head -5 .env.local")
        self.assertBlocked("less 'config/.env'")
        self.assertAllowed("cat .env.example")
        self.assertAllowed("ls -la .env")
        self.assertAllowed("cat environment.md")

    def test_private_key_files_by_name(self) -> None:
        self.assertBlocked("f=~/.ssh/id_" + "rsa; cat $f")
        self.assertBlocked("cat deploy.pem")
        self.assertBlocked("less server.key")
        self.assertBlocked("head -2 /keys/id_" + "ed25519")
        self.assertAllowed("cat ~/.ssh/id_" + "rsa.pub")
        self.assertAllowed("ls ~/.ssh")

    def test_normal_commands_still_pass(self) -> None:
        for command in ["ls -la", "git status", "python3 -m unittest", "echo hello", "cat README.md",
                        "grep -rn TODO src", "npm test", "docker ps", "set -x", "pwd"]:
            self.assertAllowed(command)


if __name__ == "__main__":
    unittest.main()
