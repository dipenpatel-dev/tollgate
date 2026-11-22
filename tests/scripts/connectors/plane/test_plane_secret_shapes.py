# Module:      test_plane_secret_shapes.py
# Description: The default secret patterns match the Plane key shape and a JSON quoted credential member, and leave short or placeholder values alone.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; keys are obviously fake and built at run time from parts
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import re
import unittest

from connectors.plane.plane_comment_builder import find_secret_pattern
from connectors.plane.plane_sync_settings import DEFAULT_SECRET_PATTERNS


def fake_plane_key() -> str:
    return "plane_" + "api_" + "FAKEFAKEFAKEFAKEFAKE12345"


def fake_member(name: str, value: str = "FAKE" * 6) -> str:
    return '{"%s": "%s"}' % (name, value)


class TestPlaneSecretShapes(unittest.TestCase):
    def test_plane_key_shape_is_matched(self) -> None:
        pattern = DEFAULT_SECRET_PATTERNS["plane_api_key"]
        self.assertIsNotNone(re.search(pattern, "header X-Api-Key: " + fake_plane_key()))
        self.assertIsNone(re.search(pattern, "plane_api_ prefix only"))
        self.assertIsNone(re.search(pattern, "plane_api_short"))

    def test_json_quoted_members_are_matched(self) -> None:
        pattern = DEFAULT_SECRET_PATTERNS["json_quoted_secret"]
        for name in ("api_key", "apikey", "token", "secret", "access_token", "client_secret", "API_KEY"):
            self.assertIsNotNone(re.search(pattern, fake_member(name)), name)

    def test_short_and_placeholder_values_are_not_matched(self) -> None:
        pattern = DEFAULT_SECRET_PATTERNS["json_quoted_secret"]
        for text in (fake_member("api_key", "short"), fake_member("token", "<your token here>"),
                     fake_member("name", "FAKE" * 6)):
            self.assertIsNone(re.search(pattern, text), text)

    def test_find_secret_pattern_blocks_both_shapes(self) -> None:
        for text in ("note " + fake_plane_key(), fake_member("api_key")):
            self.assertIsNotNone(find_secret_pattern(text, DEFAULT_SECRET_PATTERNS), text)


if __name__ == "__main__":
    unittest.main()
