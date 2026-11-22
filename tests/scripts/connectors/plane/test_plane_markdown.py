# Module:      test_plane_markdown.py
# Description: Tests for the built-in markdown renderer: escaping, structure, links, no images.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import unittest

from connectors.plane.plane_markdown import markdown_to_html


class TestMarkdown(unittest.TestCase):
    def test_raw_html_is_shown_as_text(self) -> None:
        html = markdown_to_html("hello <script>alert(1)</script>\n\n**bold**")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_headings_paragraphs_and_lists(self) -> None:
        html = markdown_to_html("## Title\n\nfirst line\nsecond line\n\n- a\n- b\n\n1. one\n2. two\n")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<p>first line\nsecond line</p>", html)
        self.assertIn("<ul>\n<li>a</li>\n<li>b</li>\n</ul>", html)
        self.assertIn("<ol>\n<li>one</li>\n<li>two</li>\n</ol>", html)

    def test_a_trailing_hash_is_kept_unless_a_space_separates_it(self) -> None:
        self.assertIn("<h2>Using C#</h2>", markdown_to_html("## Using C#\n"))
        self.assertIn("<h2>Title</h2>", markdown_to_html("## Title ##\n"))
        self.assertIn("<h2>Title</h2>", markdown_to_html("## Title #\n"))

    def test_a_fenced_block_is_escaped_and_kept_whole(self) -> None:
        html = markdown_to_html("```mermaid\nflowchart TD\n    a --> b\n```\n")
        self.assertIn("<pre><code", html)
        self.assertIn("a --&gt; b", html)
        self.assertNotIn("<p>", html)

    def test_inline_code_is_not_formatted_inside(self) -> None:
        html = markdown_to_html("use `**raw**` here")
        self.assertIn("<code>**raw**</code>", html)

    def test_images_make_no_img_tag_but_http_links_stay(self) -> None:
        html = markdown_to_html("![x](https://example.invalid/p.png) and [link](https://example.invalid/a)")
        self.assertNotIn("<img", html)
        self.assertIn('<a href="https://example.invalid/a">link</a>', html)

    def test_a_script_link_is_not_made_a_link(self) -> None:
        html = markdown_to_html("[click](javascript:alert(1))")
        self.assertNotIn("<a ", html)

    def test_empty_text_gives_empty_html(self) -> None:
        self.assertEqual(markdown_to_html(""), "")

    def test_a_status_line_with_underscores_is_left_alone(self) -> None:
        self.assertIn("SPEC_APPROVED", markdown_to_html("Status: SPEC_APPROVED to SHIPPED"))


if __name__ == "__main__":
    unittest.main()
