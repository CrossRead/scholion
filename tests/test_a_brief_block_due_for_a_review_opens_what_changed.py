"""A brief block due for a review opens what changed, instead of saying that something did.

The lifestyle tab printed «the brief needs a review» as a label — 21 labels and
buttons on one tab of a real profile (14.09.2026) — and nothing in the product
performed a review. The numbers inside a block are substituted live and never go
stale; what can go stale is the conclusion, and judging a conclusion is not the
program's to do. So the review is everything that judgement needs: for every
watched marker, the value at the review date and every point since, where each
stands against its range, and whether that position moved — plus a request for
the assistant built from the same facts, carrying the block's live tokens.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import engine

ROOT = support.ROOT

LABS = {"markers": {
    "triglycerides": {"name": "Triglycerides", "unit": "mmol/L", "ref_low": 0.4, "ref_high": 1.7,
                      "series": [{"date": "2026-05-01", "value": 1.2},
                                 {"date": "2026-09-01T08:30", "value": 2.4}]},
    "insulin": {"name": "Insulin", "unit": "µIU/mL", "ref_low": 2.6, "ref_high": 24.9,
                "series": [{"date": "2026-04-01", "value": 9.0}]},
    "vitamin_d": {"name": "Vitamin D", "unit": "ng/mL", "ref_low": 30, "ref_high": 100,
                  "series": [{"date": "2026-03-01", "value": 41}]},
}}

BRIEF = {
    "_meta": {"updated": "2026-06-01"}, "title": "Brief", "compiled": "2026-06-01",
    "sections": [{"id": "key", "title": "Key"}],
    "blocks": [
        {"id": "ir", "section": "key", "title": "Insulin resistance", "reviewed": "2026-06-01",
         "body": "Triglycerides now {{lab:triglycerides}}.", "review_hint": "watch the triglycerides",
         "watch": [{"kind": "lab", "key": "triglycerides"}, {"kind": "lab", "key": "insulin"}]},
        {"id": "calm", "section": "key", "title": "Vitamin D", "reviewed": "2026-06-01",
         "body": "Vitamin D {{lab:vitamin_d}}.", "watch": [{"kind": "lab", "key": "vitamin_d"}]},
    ],
}


class _Profile(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brief_review_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        (self.profile / "labs.json").write_text(json.dumps(LABS), encoding="utf-8")
        (self.profile / "lifestyle_brief.json").write_text(json.dumps(BRIEF), encoding="utf-8")
        self.addCleanup(support.pin_profile(self.profile))
        from scholion import core
        core.reset_cache()
        self.addCleanup(core.reset_cache)


class TestTheReview(_Profile):

    def test_a_block_shows_the_value_at_its_review_date_and_every_point_since(self):
        r = engine.brief_review("ir")
        self.assertTrue(r["ok"], r)
        (blk,) = r["blocks"]
        self.assertTrue(blk["stale"])
        tg = next(m for m in blk["markers"] if m["key"] == "triglycerides")
        self.assertEqual({"date": "2026-05-01", "value": 1.2, "status": "ok"}, tg["before"])
        self.assertEqual([{"date": "2026-09-01T08:30", "value": 2.4, "status": "high"}], tg["after"])
        self.assertEqual(("up", True), (tg["direction"], tg["status_changed"]))
        ins = next(m for m in blk["markers"] if m["key"] == "insulin")
        self.assertEqual([], ins["after"], "a marker with nothing new is shown as unchanged")

    def test_with_no_block_named_only_the_blocks_due_are_reviewed(self):
        r = engine.brief_review()
        self.assertEqual(["ir"], [b["id"] for b in r["blocks"]])

    def test_the_request_names_the_changes_and_keeps_the_live_tokens(self):
        request = engine.brief_review("ir")["blocks"][0]["request"]
        for part in ("«ir»", "2026-06-01", "{{lab:triglycerides}}", "2.4", "watch the triglycerides"):
            self.assertIn(part, request)
        self.assertNotIn("⟦", request)

    def test_an_unknown_block_is_refused_by_name(self):
        r = engine.brief_review("nope")
        self.assertEqual((False, "no_block"), (r["ok"], r["reason"]))
        self.assertIn("nope", r["message"])

    def test_the_command_line_prints_the_review_and_the_request(self):
        code, out, err = support.run(["brief-review", "ir"], profile_dir=self.profile)
        self.assertEqual(0, code, err[-600:])
        self.assertIn("Triglycerides", out)
        self.assertIn("{{lab:triglycerides}}", out)


class TestThePageOffersAButton(unittest.TestCase):

    def test_the_review_flag_is_a_button_on_both_tabs(self):
        html = (ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-brv-all", html, "the lifestyle tab's flag is a button that opens the reviews")
        self.assertIn("data-open-brief", html, "the assistant tab's flag is a button that goes to them")
        self.assertIn("/api/brief-review", html)
        self.assertNotIn("<span class=\"badge b-warning\">${esc(t('web.brief.needs_review'))}</span>", html,
                         "the flag is no longer a label beside the wording")


if __name__ == "__main__":
    unittest.main()
