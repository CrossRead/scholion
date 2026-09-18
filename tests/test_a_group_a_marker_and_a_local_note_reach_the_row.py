"""Three entries of task 199 that were left after the levels: groups, the marker's genetics, the local note.

* A group is one row for N positions — name, count, one sentence, one level,
  one source — and opens into its members. A group naming a position the
  system does not hold, or without a sentence in both languages, is refused
  whole and counted, never shown half-empty.
* A laboratory marker with positions behind it carries them (static: gene,
  rsID, level, direction) so that «the genetics of this marker» is the third
  entry into the same rows, without reading the genome fifteen times.
* A clinician's local note lives in the PROFILE, prints on the row it is
  about in its own voice, and never reaches the package — the profile is not
  shipped, and the note is not a field of the shipped book.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import core
from scholion.engine import panel_book, system_panels as SP


class TestAGroupIsOneRowForItsPositions(unittest.TestCase):

    def _rows(self):
        return [{"unit": "position", "rsid": "rsA", "gene": "GA", "state": "het", "level": "B"},
                {"unit": "position", "rsid": "rsB", "gene": "GB", "state": "absent", "level": "B"},
                {"unit": "gene", "gene": "GC"}]

    def test_a_whole_group_prints_once_and_marks_its_members(self):
        rows = self._rows()
        spec = {"groups": [{"key": "g1", "label": {"en": "Group one", "ru": "Группа один"},
                            "positions": ["rsA", "rsB"], "text": {"en": "one sentence", "ru": "одна фраза"},
                            "source": "PMID 1", "evidence": {"level": "B"}}]}
        out = SP._groups("thyroid", spec, rows)
        self.assertEqual(1, len(out))
        g = out[0]
        self.assertEqual(2, g["count"])
        self.assertEqual({"het": 1, "absent": 1}, g["states"])
        self.assertEqual("g1", rows[0]["group"])
        self.assertEqual(2, len(g["members"]))

    def test_a_group_naming_a_position_the_system_lacks_is_refused_whole(self):
        spec = {"groups": [{"key": "g1", "label": {"en": "G", "ru": "Г"}, "positions": ["rsA", "rsZ"],
                            "text": {"en": "s", "ru": "ф"}, "source": "PMID 1", "evidence": {"level": "B"}}]}
        out = SP._groups("thyroid", spec, self._rows())
        self.assertEqual("group_position_not_in_system", out[0]["refused"])

    def test_a_group_without_a_source_or_a_level_is_refused(self):
        base = {"key": "g1", "label": {"en": "G", "ru": "Г"}, "positions": ["rsA"], "text": {"en": "s", "ru": "ф"}}
        self.assertEqual("group_without_source", SP._groups("thyroid", {"groups": [{**base, "evidence": {"level": "B"}}]}, self._rows())[0]["refused"])
        self.assertEqual("group_level_missing", SP._groups("thyroid", {"groups": [{**base, "source": "PMID 1"}]}, self._rows())[0]["refused"])


class TestAMarkerCarriesItsPositions(unittest.TestCase):

    def test_the_index_names_a_position_by_the_marker_its_expectation_names(self):
        book = {"systems": {"thyroid": {"positions": [
            {"rsid": "rs1", "gene": "G1", "kind": "asked_about", "expect": {"marker": "tsh", "direction": "higher"},
             "evidence": {"level": "B"}},
            {"rsid": "rs2", "gene": "G2", "kind": "asked_about"}]}}}
        with mock.patch.object(SP, "_curated", lambda: book):
            idx = SP.positions_by_marker()
        self.assertEqual(["rs1"], [p["rsid"] for p in idx.get("tsh", [])])
        self.assertEqual("higher", idx["tsh"][0]["direction"])
        self.assertEqual("thyroid", idx["tsh"][0]["system"])
        self.assertNotIn("rs2", str(idx))

    def test_a_broken_index_is_an_error_and_not_a_silent_blank(self):
        """A missing file is an empty index; a broken one is an error somebody
        sees — the reader never hides it (review, 18.09.2026)."""
        from scholion.engine import labs
        with mock.patch("scholion.engine.system_panels.positions_by_marker", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                labs._positions_by_marker()

    def test_a_gene_whose_name_starts_with_rs_is_still_a_gene(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "local_notes.json").write_text(json.dumps({"notes": [{"gene": "RSPO1", "text": "n"}]}), encoding="utf-8")
        with mock.patch.object(core, "profile_dir", lambda: tmp):
            self.assertIn("RSPO1", panel_book._local_notes())

    def test_the_labs_analysis_carries_the_index_on_the_marker_row(self):
        from scholion.engine import labs
        rows = labs.analyze_labs().get("markers") or []
        self.assertTrue(rows, "the fixture profile holds markers")
        self.assertTrue(all("positions" in m for m in rows))


class TestALocalNoteStaysLocal(unittest.TestCase):

    def test_a_note_in_the_profile_prints_on_its_row_and_nowhere_in_the_book(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "local_notes.json").write_text(json.dumps({"notes": [
            {"rsid": "rs123", "text": "seen in clinic", "by_role": "clinician", "on": "2026-09-18"},
            {"gene": "GY", "text": "family history"}]}), encoding="utf-8")
        with mock.patch.object(core, "profile_dir", lambda: tmp):
            rows = [{"unit": "position", "rsid": "rs123", "gene": "GX"}, {"unit": "gene", "gene": "GY"},
                    {"unit": "gene", "gene": "GZ"}]
            SP._attach_local_notes(rows)
        self.assertEqual("seen in clinic", rows[0]["local_note"]["text"])
        self.assertEqual("family history", rows[1]["local_note"]["text"])
        self.assertIsNone(rows[2].get("local_note"))
        raw = core.knowledge_path("system_gene_panels.json").read_text(encoding="utf-8")
        self.assertNotIn("local_note", raw, "a note is the profile's, never the book's")

    def test_a_missing_or_broken_file_is_no_note_at_all(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(core, "profile_dir", lambda: tmp):
            self.assertEqual({}, panel_book._local_notes())
        (tmp / "local_notes.json").write_text("{not json", encoding="utf-8")
        with mock.patch.object(core, "profile_dir", lambda: tmp):
            self.assertEqual({}, panel_book._local_notes())


if __name__ == "__main__":
    unittest.main()
