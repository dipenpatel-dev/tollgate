# Module:      test_plane_standards.py
# Description: Package standards for the plane connector: headers, no print, short typed functions, no request library, no outside imports.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; reads the connector source files
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import ast
import re
import unittest

from plane_sync_test_support import SCRIPTS

PACKAGE_DIR = SCRIPTS / "connectors" / "plane"
MAX_FUNCTION_LINES = 40
EM_DASH_CODE = 0x2014
BANNED_IMPORTS = {"requests", "urllib.request", "urllib.error", "urllib3", "http", "socket", "yaml", "markdown_it", "httpx", "aiohttp"}
SKIP_HINTS = {"__main__.py", "plane_sync.py", "__init__.py"}


def sources() -> list:
    return sorted(PACKAGE_DIR.glob("*.py"))


class TestStandards(unittest.TestCase):
    def test_the_package_has_every_expected_file(self) -> None:
        names = {p.name for p in sources()} | {p.name for p in PACKAGE_DIR.iterdir()}
        for expected in ("cli.py", "plane_sync.py", "plane_work_item_client.py", "plane_ticket_syncer.py",
                         "plane_drift_checker.py", "vault_ticket_creator.py", "vault_ticket_files.py",
                         "plane_ticket_state_template.md", "plane_sync_settings.example.json"):
            self.assertIn(expected, names)

    def test_no_request_library_or_outside_package_is_imported(self) -> None:
        for path in sources():
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = {alias.name for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = {node.module}
                else:
                    continue
                for name in names:
                    banned = [b for b in BANNED_IMPORTS if name == b or name.startswith(b + ".")]
                    self.assertEqual(banned, [], f"{path.name} imports {name}")

    def test_the_framework_is_the_only_way_out(self) -> None:
        text = (PACKAGE_DIR / "plane_work_item_client.py").read_text(encoding="utf-8")
        self.assertIn("self._http.request(", text)
        cli_text = (PACKAGE_DIR / "cli.py").read_text(encoding="utf-8")
        self.assertIn("registry.register(CONNECTOR_NAME", cli_text)
        self.assertIn("registry.ensure(CONNECTOR_NAME", cli_text)

    def test_no_print_calls_no_todo_no_em_dash(self) -> None:
        for path in sources():
            text = path.read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "print", path.name)
            self.assertNotIn("TODO", text)
            self.assertNotIn(chr(EM_DASH_CODE), text)

    def test_functions_are_forty_lines_or_fewer(self) -> None:
        for path in sources():
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = node.end_lineno - node.lineno + 1
                    self.assertLessEqual(length, MAX_FUNCTION_LINES, f"{path.name}:{node.name}")

    def test_every_function_has_type_hints(self) -> None:
        for path in sources():
            if path.name in SKIP_HINTS:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.FunctionDef):
                    self.assertIsNotNone(node.returns, f"{path.name}:{node.name}")
                    for arg in node.args.args + node.args.kwonlyargs:
                        if arg.arg not in ("self", "cls"):
                            self.assertIsNotNone(arg.annotation, f"{path.name}:{node.name}:{arg.arg}")

    def test_every_file_has_the_header_fields(self) -> None:
        for path in sources():
            head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:14])
            for field in ("Author:      Dipen Patel (dipenpatel-dev)", "Date:", "Scope:", "ChangeLog:"):
                self.assertIn(field, head, f"{path.name} {field}")
            self.assertNotRegex(head, r"Ticket:|20\d\d-\d\d-\d\d")

    def test_no_company_host_or_person_words_in_the_connector_or_its_tests(self) -> None:
        pattern = re.compile(r"https?://[A-Za-z0-9.-]+\.(?:us|lan|local|internal|home)\b|/Users/|infisical", re.I)
        for folder in (PACKAGE_DIR, PACKAGE_DIR.parents[2] / "tests" / "scripts" / "connectors" / "plane"):
            for path in folder.iterdir():
                if path.is_file() and path.name != "test_plane_standards.py":
                    self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), str(path))


if __name__ == "__main__":
    unittest.main()
