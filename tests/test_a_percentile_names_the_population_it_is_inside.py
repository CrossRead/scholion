"""A percentile carries the panel it was computed against, and says where it came from.

A percentile is a position within a population. Against another population it is
not that person's position — so which panel was used is part of what the number
means, and it has to travel with it.

THE DEFECT THIS FILE WAS WRITTEN FOR. `stats` reported a stored panel beside a
flag called `ancestry_stated`, and the flag asked the PROFILE whether a panel was
known — not the file whether these percentiles had been computed against it. The
two were independent, and nothing compared them. When the panel began to be
determined from the genome, the flag went true for everybody who had one, while
the numbers went on being scored against whatever the scoring run was given,
which defaulted to EUR in a function signature. The interface then said the panel
was settled and showed percentiles computed against a different one. No error, no
gap: an ordinary number with a wrong claim attached.

So three facts are reported where one was: the panel the numbers used, where THAT
came from, and which panel applies now — plus whether the two agree, said out
loud in the caveats rather than left as a field for somebody to notice.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, engine, prs
from scholion.engine import genomics


@contextmanager
def profile(*, stored_panel=None, stored_source=None, genome_verdict=None, stated=None):
    """A profile with a stored PRS result and, optionally, a determination."""
    tmp = Path(tempfile.mkdtemp(prefix="panel-")).resolve()
    (tmp / "metrics.json").write_text(json.dumps(
        {"profile": ({"ancestry": stated} if stated else {}), "metrics": {}}), encoding="utf-8")
    meta = {"updated": "2026-08-01"}
    if stored_panel:
        meta["superpopulation"] = stored_panel
    if stored_source:
        meta["superpopulation_source"] = stored_source
    (tmp / "prs_results.json").write_text(json.dumps(
        {"_meta": meta,
         "traits": [{"label": "Type 2 diabetes", "percentile": 71,
                     "percentile_reliable": True}]}), encoding="utf-8")
    if genome_verdict:
        (tmp / "ancestry_check.json").write_text(json.dumps(
            {"date": "2026-08-24", "verdict_superpop": genome_verdict,
             "posterior": {genome_verdict: 0.97}}), encoding="utf-8")
    old = os.environ.get("SCHOLION_PROFILE_DIR")
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp)
    core.reset_cache()
    try:
        yield tmp
    finally:
        if old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = old
        core.reset_cache()
        shutil.rmtree(tmp, ignore_errors=True)


def panel_caveats(report):
    return [c["key"] for c in report["method_caveats"] if c["key"].startswith("panel_")]


class TestThePanelIsResolvedRatherThanDefaulted(unittest.TestCase):
    """`superpopulation: str = "EUR"` in a signature is the quietest way a
    parameter of a medical answer can be chosen: by whoever typed the default."""

    def test_nothing_known_falls_back_and_says_it_fell_back(self):
        with profile():
            got = prs.resolve_superpopulation()
        self.assertEqual("EUR", got["value"])
        self.assertEqual("default", got["source"],
                         "a fallback that does not announce itself is a decision nobody made")

    def test_the_genome_answers_when_it_has(self):
        with profile(genome_verdict="SAS"):
            got = prs.resolve_superpopulation()
        self.assertEqual({"value": "SAS", "source": "genome"}, got)

    def test_a_caller_that_names_one_wins(self):
        with profile(genome_verdict="SAS"):
            got = prs.resolve_superpopulation("AFR")
        self.assertEqual({"value": "AFR", "source": "asked"}, got)

    def test_a_deliberate_override_in_the_profile_wins_over_the_genome(self):
        with profile(genome_verdict="SAS", stated="EUR"):
            got = prs.resolve_superpopulation()
        self.assertEqual({"value": "EUR", "source": "stated"}, got)


class TestTheStoredNumbersSayWhatTheyWereScoredAgainst(unittest.TestCase):

    def test_the_defect_itself_the_panel_that_was_used_and_the_one_that_applies(self):
        """Numbers on EUR, a genome saying SAS. This is what used to report
        «ancestry stated» and print the percentile as if the question were
        settled."""
        with profile(stored_panel="EUR", genome_verdict="SAS"):
            stats = engine.prs_findings()["stats"]
        self.assertEqual("EUR", stats["superpopulation"], "the numbers used EUR and must say so")
        self.assertEqual("SAS", stats["ancestry_determined"])
        self.assertTrue(stats["panel_out_of_date"])
        self.assertFalse(stats["ancestry_stated"],
                         "the stored numbers were never scored against a chosen panel")

    def test_the_disagreement_is_printed_and_not_merely_recorded(self):
        with profile(stored_panel="EUR", genome_verdict="SAS"):
            report = engine.prs_findings()
        self.assertEqual(["panel_out_of_date"], panel_caveats(report))
        note = next(c["note"] for c in report["method_caveats"]
                    if c["key"] == "panel_out_of_date")
        self.assertIn("EUR", note)
        self.assertIn("SAS", note, "the caveat does not name the panel that now applies")

    def test_agreement_is_quiet(self):
        with profile(stored_panel="SAS", stored_source="genome", genome_verdict="SAS"):
            report = engine.prs_findings()
        self.assertEqual([], panel_caveats(report))
        self.assertTrue(report["stats"]["ancestry_stated"])
        self.assertFalse(report["stats"]["panel_out_of_date"])

    def test_a_defaulted_panel_says_so_even_with_nothing_to_disagree_with(self):
        """No determination is not a disagreement — it is the ordinary state
        before the genome has been asked. But the number still rests on a panel
        nobody chose, and that is worth a sentence."""
        with profile(stored_panel="EUR"):
            report = engine.prs_findings()
        self.assertEqual(["panel_defaulted"], panel_caveats(report))
        self.assertFalse(report["stats"]["panel_out_of_date"])
        self.assertIsNone(report["stats"]["ancestry_determined"])

    def test_a_file_written_before_the_source_existed_cannot_claim_one(self):
        """«Cannot say» is not «yes». An older results file carries no source,
        and reading its silence as a deliberate choice is the same defect in a
        smaller place."""
        with profile(stored_panel="EUR", genome_verdict="EUR"):
            stats = engine.prs_findings()["stats"]
        self.assertFalse(stats["ancestry_stated"])
        self.assertFalse(stats["panel_out_of_date"],
                         "the same letters are not a disagreement")


class TestTheFactsAreOneFunction(unittest.TestCase):

    def test_the_report_and_the_caveat_read_the_same_place(self):
        """Two readers of one fact drift. The caveat is built from the facts, so
        a panel that is out of date cannot be reported in one and not the
        other."""
        with profile(stored_panel="EUR", genome_verdict="SAS"):
            data = core.read_profile_json(Path(os.environ["SCHOLION_PROFILE_DIR"])
                                          / "prs_results.json")
            facts = genomics._panel_facts(data)
            caveat = genomics._panel_caveat(data)
        self.assertTrue(facts["panel_out_of_date"])
        self.assertEqual(["panel_out_of_date"], [c["key"] for c in caveat])


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
