"""Connection instructions wrap visually without shortening the command to copy.

Native browser acceptance also exercises the sanitised package's longer install
path. These guards keep the wrapping and full data fields on both instruction
lists; hiding overflow would conceal the instruction rather than fix it.
"""
from __future__ import annotations

import unittest

import support


class TestConnectionPaths(unittest.TestCase):
    def test_both_lists_wrap_and_keep_the_original_command_and_detail(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        self.assertIn(".assist-entry{min-width:0;overflow-wrap:anywhere}", page)
        self.assertIn(".assist-entry code{white-space:pre-wrap;overflow-wrap:anywhere}", page)
        start = page.index("async function viewAssistant(")
        view = page[start:page.index("\n}\n", start) + 2]
        self.assertEqual(2, view.count('class="list-item assist-entry"'))
        for field in ("${esc(e.how)}", "${esc(e.detail)}", "${esc(c.cmd)}"):
            self.assertIn(field, view)
