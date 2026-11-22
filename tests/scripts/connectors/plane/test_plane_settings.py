# Module:      test_plane_settings.py
# Description: Tests for the settings file: the shipped example loads, bad keys raise with the key name only, no address or key lives in it.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import json
import tempfile
import unittest
from pathlib import Path

from connectors.plane.plane_sync_settings import (
    PlaneSyncConfigError,
    default_settings_path,
    load_settings,
)
from plane_sync_test_support import EXAMPLE_SETTINGS


class TestSettings(unittest.TestCase):
    def _variant(self, mutate) -> Path:
        data = json.loads(EXAMPLE_SETTINGS.read_text(encoding="utf-8"))
        mutate(data)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "variant.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_the_shipped_example_loads(self) -> None:
        settings = load_settings(EXAMPLE_SETTINGS, {})
        self.assertEqual(settings.external_source_name, "tollgate")
        self.assertEqual(settings.min_seconds_between_calls, 1.2)
        self.assertEqual(settings.page_size, 100)
        self.assertEqual(settings.comment_max_chars, 15000)
        self.assertEqual(settings.new_ticket_board_status, "Backlog")
        row = settings.prefix_table["T"]
        self.assertEqual((row.project_key, row.number_width), ("T", 3))
        self.assertEqual(row.ticket_pattern, r"^T-(\d+)$")
        self.assertEqual(settings.status_map["QA_BLOCKED"], "Waiting")
        self.assertEqual(settings.blocked_words, ("QA_BLOCKED",))

    def test_secret_patterns_default_to_the_built_in_set(self) -> None:
        settings = load_settings(EXAMPLE_SETTINGS, {})
        self.assertEqual(
            sorted(settings.secret_patterns),
            ["aws_access_key", "bearer_token", "github_token", "json_quoted_secret", "long_mixed_token",
             "named_secret_assignment", "plane_api_key", "private_key_block", "slack_token", "url_credentials"],
        )

    def test_the_example_holds_no_address_and_no_key(self) -> None:
        text = EXAMPLE_SETTINGS.read_text(encoding="utf-8").lower()
        for word in ("http:", "https:", "token", "api_key", "secret", "password"):
            self.assertNotIn(word, text)

    def test_the_settings_file_sits_next_to_the_paths_file(self) -> None:
        path = default_settings_path({"TOLLGATE_PATHS": "/somewhere/cfg/paths.yaml"})
        self.assertEqual(path, Path("/somewhere/cfg/plane-sync.json"))
        with self.assertRaises(PlaneSyncConfigError):
            default_settings_path({})

    def test_a_prefix_table_can_come_from_the_ticket_prefix_variable(self) -> None:
        path = self._variant(lambda data: data.pop("prefix_table"))
        settings = load_settings(path, {"TOLLGATE_TICKET_PREFIX": "QQ"})
        self.assertEqual(list(settings.prefix_table), ["QQ"])
        self.assertEqual(settings.prefix_table["QQ"].project_key, "QQ")
        with self.assertRaises(PlaneSyncConfigError) as caught:
            load_settings(path, {})
        self.assertEqual(str(caught.exception), "prefix_table")

    def test_missing_required_key_names_the_key_only(self) -> None:
        for key in ("workspace_slug", "new_ticket_board_status", "status_map"):
            path = self._variant(lambda data, key=key: data.pop(key))
            with self.assertRaises(PlaneSyncConfigError) as caught:
                load_settings(path, {})
            self.assertEqual(str(caught.exception), key)

    def test_wrong_type_names_the_key_only(self) -> None:
        path = self._variant(lambda data: data.update(page_size="many"))
        with self.assertRaises(PlaneSyncConfigError) as caught:
            load_settings(path, {})
        self.assertEqual(str(caught.exception), "page_size")

    def test_bool_is_not_a_number(self) -> None:
        path = self._variant(lambda data: data.update(min_seconds_between_calls=True))
        with self.assertRaises(PlaneSyncConfigError):
            load_settings(path, {})

    def test_a_bad_status_map_entry_is_refused(self) -> None:
        path = self._variant(lambda data: data["status_map"].update(SHIPPED=5))
        with self.assertRaises(PlaneSyncConfigError) as caught:
            load_settings(path, {})
        self.assertEqual(str(caught.exception), "status_map")

    def test_missing_or_broken_file_raises_a_config_error(self) -> None:
        with self.assertRaises(PlaneSyncConfigError):
            load_settings(Path("/nonexistent/plane-sync.json"), {})
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        broken = Path(temp.name) / "plane-sync.json"
        broken.write_text("{not json", encoding="utf-8")
        with self.assertRaises(PlaneSyncConfigError):
            load_settings(broken, {})


if __name__ == "__main__":
    unittest.main()
