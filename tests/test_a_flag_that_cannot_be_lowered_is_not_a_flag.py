"""«The brief needs review» could be raised and never lowered.

The comparison behind it is sound: a block of the lifestyle brief names the
markers it was written from, and when one of them arrives with a date later than
the wording's `reviewed`, the block is stale. The date is a person's statement —
«I read this text beside these numbers» — and there was no way to make that
statement from anywhere in the product. So the flag went up the first time a
watched marker arrived, and stayed up, at the top of the tab, above the content.

A warning that cannot be answered is not a warning; it is furniture, and the
reader learns to look past it. What it takes to lower it is one write, and the
write records exactly the claim the button makes — nothing about the wording
itself is touched.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, store
from scholion.engine import lifestyle_brief

META = {"purpose": "SYNTHETIC — a test fixture", "synthetic": True}


def _profile(reviewed="2026-01-01", newest="2026-06-01"):
    d = Path(tempfile.mkdtemp(prefix="brief_"))
    (d / "labs.json").write_text(json.dumps({"_meta": META, "markers": {
        "ldl": {"name": "LDL", "unit": "mmol/L", "ref_high": 3.0,
                "series": [{"date": newest, "value": 3.4}]}}}, ensure_ascii=False),
        encoding="utf-8")
    (d / "lifestyle_brief.json").write_text(json.dumps({
        "_meta": META,
        "title": "Brief", "compiled": reviewed,
        "sections": [{"id": "lipids", "title": "Lipids", "lead": ""}],
        "blocks": [
            {"id": "ldl_block", "section": "lipids", "title": "LDL",
             "body": "The wording a person wrote.", "weight": 9,
             "watch": [{"kind": "lab", "key": "ldl"}], "reviewed": reviewed,
             "review_hint": "check the number against the sentence"},
            {"id": "quiet_block", "section": "lipids", "title": "Quiet",
             "body": "Nothing watches this one.", "weight": 1,
             "watch": [], "reviewed": reviewed},
        ]}, ensure_ascii=False), encoding="utf-8")
    return d


class _OnAProfile(unittest.TestCase):

    def setUp(self):
        self.dir = _profile()
        self._env = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir)
        core.reset_cache()

    def tearDown(self):
        if self._env is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._env
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def brief(self):
        core.reset_cache()
        return lifestyle_brief()


class TestTheFlagCanBeLowered(_OnAProfile):

    def test_it_is_raised_by_data_that_arrived_after_the_wording(self):
        b = self.brief()
        self.assertTrue(b["needs_review"], "the fixture does not reproduce the case")
        self.assertEqual([s["id"] for s in b["stale_blocks"]], ["ldl_block"])

    def test_saying_the_wording_still_holds_lowers_it(self):
        r = store.mark_brief_reviewed("ldl_block")
        self.assertTrue(r["ok"], r)
        self.assertFalse(self.brief()["needs_review"],
                         "the one statement that can answer this flag did not answer it")

    def test_the_date_written_is_the_day_it_was_said(self):
        from datetime import date
        store.mark_brief_reviewed("ldl_block")
        raw = json.loads((self.dir / "lifestyle_brief.json").read_text(encoding="utf-8"))
        hit = next(b for b in raw["blocks"] if b["id"] == "ldl_block")
        self.assertEqual(hit["reviewed"], date.today().isoformat())

    def test_nothing_but_the_date_moves(self):
        """The button says the wording still holds. It must not edit the wording,
        the other blocks, or anything else the file carries."""
        before = json.loads((self.dir / "lifestyle_brief.json").read_text(encoding="utf-8"))
        store.mark_brief_reviewed("ldl_block")
        after = json.loads((self.dir / "lifestyle_brief.json").read_text(encoding="utf-8"))
        # `_meta` is the writer's own stamp and is expected to move; everything
        # a reader reads must not.
        before.pop("_meta", None), after.pop("_meta", None)
        for b in before["blocks"] + after["blocks"]:
            b.pop("reviewed", None)
        self.assertEqual(before, after, "something other than the review date changed")
        self.assertEqual([b["id"] for b in after["blocks"]], ["ldl_block", "quiet_block"],
                         "a block was lost by a write that only had a date to make")

    def test_it_goes_up_again_when_the_next_measurement_arrives(self):
        """Lowering it is not switching it off. The block is stale again the moment
        a watched marker is measured after the day the wording was confirmed."""
        store.mark_brief_reviewed("ldl_block")
        self.assertFalse(self.brief()["needs_review"])
        labs = json.loads((self.dir / "labs.json").read_text(encoding="utf-8"))
        labs["markers"]["ldl"]["series"].append({"date": "2099-01-01", "value": 3.9})
        (self.dir / "labs.json").write_text(json.dumps(labs, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(self.brief()["needs_review"])


class TestItRefusesRatherThanGuesses(_OnAProfile):

    def test_a_block_nobody_has_is_refused_and_writes_nothing(self):
        before = (self.dir / "lifestyle_brief.json").read_text(encoding="utf-8")
        r = store.mark_brief_reviewed("no_such_block")
        self.assertFalse(r["ok"])
        self.assertEqual(before, (self.dir / "lifestyle_brief.json").read_text(encoding="utf-8"))

    def test_an_empty_id_is_not_a_wildcard(self):
        r = store.mark_brief_reviewed("")
        self.assertFalse(r["ok"], "an empty id confirmed something")

    def test_a_profile_with_no_brief_says_so(self):
        (self.dir / "lifestyle_brief.json").unlink()
        core.reset_cache()
        r = store.mark_brief_reviewed("ldl_block")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
