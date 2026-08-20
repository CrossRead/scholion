"""The index of a body system says how much of that system it was computed from.

The radar announces each domain by a fixed panel — carbohydrate metabolism is
glucose, HbA1c, HOMA-IR and insulin — and then scores the domain as the mean over
whichever of those four the person happens to have drawn. The score is a fair
mean; the sentence around it was not. `total` was `len(present)`, so a single
glucose result printed «🟢 100/100, 0 out of range of 1» — read by anyone as a
statement about carbohydrate metabolism, made from a quarter of the panel with
nothing on the line to say so.

The second half is the same defect in the time axis. `prev_score` was
`score - delta`: the current score over every measured marker, minus a delta
computed over the smaller subset that has an earlier point. Two different
denominators subtracted from one another produce a number that was never
measured, and it was printed with a date attached — «in January the index was
100/100» out of the movement of one marker.

Both are checked here on a profile built for the purpose: one domain with a
single marker of four, one with an earlier point on part of its panel.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support


def _labs(markers):
    d = Path(tempfile.mkdtemp(prefix="radar_"))
    (d / "labs.json").write_text(json.dumps(
        {"_meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
         "markers": markers}, ensure_ascii=False), encoding="utf-8")
    for name, key in (("pharmacogenomics.json", "genotypes"),
                      ("medications.json", "medications")):
        (d / name).write_text(json.dumps(
            {"meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True}, key: []},
            ensure_ascii=False), encoding="utf-8")
    return d


#: One marker of the four the «glucose» domain declares, comfortably in range.
ONE_OF_FOUR = {"glucose": {"name": "Glucose", "unit": "mmol/L", "ref_low": 3.9, "ref_high": 5.9,
                           "series": [{"date": "2026-06", "value": 4.8}]}}

#: Two markers of four, one of them with an earlier point — so a delta exists over
#: a subset while the score is a mean over both.
WITH_A_PAST = {
    "glucose": {"name": "Glucose", "unit": "mmol/L", "ref_low": 3.9, "ref_high": 5.9,
                "series": [{"date": "2026-01", "value": 6.8}, {"date": "2026-06", "value": 4.8}]},
    # Out of range and with no earlier point: it pulls the domain score down while
    # contributing nothing to the delta — which is exactly the pair of denominators
    # the old formula subtracted from one another.
    "hba1c": {"name": "HbA1c", "unit": "%", "ref_low": 4.0, "ref_high": 5.7,
              "series": [{"date": "2026-06", "value": 6.4}]},
}


class _Base(unittest.TestCase):

    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def radar(self, markers):
        d = _labs(markers)
        self._dirs.append(d)
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT),
                   SCHOLION_PROFILE_DIR=str(d),
                   SCHOLION_GENOME_VCF=str(support.ROOT / "tests/fixtures/no-such-file.vcf.gz"),
                   SCHOLION_GENOME_DIR=str(support.ROOT / "tests/fixtures/no-genome"))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import engine, format as fmt;"
                "r = engine.health_radar();"
                "print(json.dumps({'r': r, 'text': fmt.radar_report(r)}, default=str))"
                % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr[-800:])
        got = json.loads(p.stdout.strip().splitlines()[-1])
        got["by_key"] = {d_["key"]: d_ for d_ in got["r"]["domains"]}
        return got


class TestTheDenominatorIsTheDeclaredPanel(_Base):

    def test_the_domain_reports_the_panel_it_declares(self):
        dom = self.radar(ONE_OF_FOUR)["by_key"]["glucose"]
        self.assertEqual(dom["total"], 4, "the denominator is the number of markers drawn, "
                                          "so the domain looks fully assessed whatever the coverage")
        self.assertEqual(dom["measured"], 1)
        self.assertEqual(sorted(dom["missing"]), ["hba1c", "homa_ir", "insulin"])

    def test_the_line_a_person_reads_names_the_coverage(self):
        got = self.radar(ONE_OF_FOUR)
        line = [l for l in got["text"].splitlines() if "Carbohydrate" in l or "glucose" in l.lower()]
        self.assertTrue(line, "the domain is not printed at all")
        self.assertIn("declares 4", line[0],
                      "the score is printed without the size of the panel it was computed from")

    def test_a_fully_measured_domain_says_nothing_extra(self):
        """The remedy must not turn into a caveat on every line."""
        full = dict(ONE_OF_FOUR)
        for k, name in (("hba1c", "HbA1c"), ("homa_ir", "HOMA-IR"), ("insulin", "Insulin")):
            full[k] = {"name": name, "unit": "", "ref_low": 0, "ref_high": 100,
                       "series": [{"date": "2026-06", "value": 1}]}
        got = self.radar(full)
        self.assertEqual(got["by_key"]["glucose"]["measured"], 4)
        line = [l for l in got["text"].splitlines() if "Carbohydrate" in l][0]
        self.assertNotIn("declares", line)


class TestTheEarlierIndexWasMeasured(_Base):

    def test_the_previous_score_is_a_mean_of_previous_values(self):
        """Not `score - delta`, which mixes two denominators.

        Here glucose fell 6.8 → 4.8 (out of range → in range) and HbA1c has no
        earlier point. The comparison rests on glucose alone, and both ends of it
        have to be glucose alone.
        """
        dom = self.radar(WITH_A_PAST)["by_key"]["glucose"]
        self.assertEqual(dom["compared"], 1)
        self.assertIsNotNone(dom["prev_score"])
        self.assertEqual(dom["delta"], dom["compared_score"] - dom["prev_score"],
                         "the delta and the pair of scores it is derived from disagree, which "
                         "means at least one of them was computed over a different set")

    def test_the_previous_score_is_not_derived_from_the_current_one(self):
        """The old formula is reproduced and required NOT to match.

        `score` is the mean over both markers, `delta` is measured on one. Their
        difference is a plausible number with nothing behind it; if it ever equals
        what is printed, the fabricated value is back.
        """
        dom = self.radar(WITH_A_PAST)["by_key"]["glucose"]
        fabricated = max(0, min(100, dom["score"] - dom["delta"]))
        self.assertNotEqual(dom["score"], dom["compared_score"],
                            "the fixture no longer separates the two denominators")
        self.assertNotEqual(dom["prev_score"], fabricated,
                            "the previous index is still `score - delta` — a value nobody measured")

    def test_the_movement_is_not_invented_where_there_is_no_past(self):
        dom = self.radar(ONE_OF_FOUR)["by_key"]["glucose"]
        self.assertIsNone(dom["prev_score"])
        self.assertIsNone(dom["delta"])


if __name__ == "__main__":
    unittest.main()
