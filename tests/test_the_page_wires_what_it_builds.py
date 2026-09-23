"""The page shows what it builds, and one click does one thing.

Four defects of the web page found by the 0.5.7 review, each a piece of work
the page did and then dropped: the decision verdict and the genetic context of a
prescription were built and never inserted; the ACMG class chips were bound by a
function nobody called; a ClinVar finding opened the gene card with an rsID for a
gene; and the genome chooser shared its attribute with the folder picker, so one
click did both.
"""
from __future__ import annotations

import re
import unittest

import support

PAGE = (support.ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = PAGE.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function \w+\(", PAGE[start + 10:])
    return PAGE[start:start + 10 + (nxt.start() if nxt else len(PAGE))]


class TestThePage(unittest.TestCase):

    def test_the_prescription_card_inserts_its_verdict_and_context(self):
        body = _function("rxCard")
        self.assertIn("${verdictHtml}", body)
        self.assertIn("contextHtml(ctx)", body)

    def test_the_screen_chips_are_bound(self):
        self.assertIn("bindScreen();", PAGE)

    def test_a_variant_row_opens_the_variant(self):
        self.assertIn("data-rs-open", _function("genomeFindings"))
        self.assertIn("[data-rs-open]", PAGE)

    def test_the_genome_chooser_is_not_the_folder_picker(self):
        self.assertIn("data-choose-genome", PAGE)
        self.assertNotIn("post('/api/choose-genome',{path:b.dataset.pick}", PAGE)

    def test_a_failed_request_comes_back_as_an_error(self):
        body = _function("api")
        self.assertIn("r.ok", body.split("_apiCache.set")[0])


if __name__ == "__main__":
    unittest.main()
