"""Two inherited facts about lipids, and what each of them is worth.

Task 63. Carrying a loss-of-function variant of PCSK9 and the value of Lp(a)
belong beside each other and were living in three different places: a coordinate
file that did not know PCSK9 at all, a directions catalogue that had no entry for
it, and an Lp(a) polygenic score sitting on a different tab from the Lp(a)
laboratory marker, with nothing saying they are not the same kind of claim.

The tests are named after the ways this goes wrong rather than after the
functions, because the two failures here are both silent:

  · «not a carrier» printed for a position that was never read — the exact shape
    the answerability layer was built after, where connecting a genome made the
    answer LESS cautious;
  · a polygenic estimate of Lp(a) read as a measurement of it. The level is
    driven mostly by a copy-number variant inside LPA that short reads see
    poorly, so the estimate cannot stand in for the assay, and the screen has to
    say so where the reader is rather than in a catalogue nobody opens.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support

KN = support.ROOT / "src" / "scholion" / "knowledge"
PCSK9_RESOLVED = ["rs11591147", "rs28362286"]
PCSK9_WAITING = ["rs28362263", "rs72646508"]


def _profile(genotypes=None, markers=None):
    d = Path(tempfile.mkdtemp(prefix="lipidgen_"))
    meta = {"purpose": "SYNTHETIC — a test fixture", "synthetic": True}
    (d / "pharmacogenomics.json").write_text(json.dumps(
        {"_meta": meta, "genotypes": genotypes or []}, ensure_ascii=False), encoding="utf-8")
    (d / "labs.json").write_text(json.dumps(
        {"_meta": meta, "markers": markers or {}}, ensure_ascii=False), encoding="utf-8")
    (d / "medications.json").write_text(json.dumps(
        {"_meta": meta, "medications": []}, ensure_ascii=False), encoding="utf-8")
    return d


class TestTheCatalogueEarnsEveryEntry(unittest.TestCase):
    """A position may be asserted in one place, and a direction only with a source."""

    def test_every_pcsk9_position_is_in_the_coordinate_file(self):
        loci = json.loads((KN / "loci.json").read_text(encoding="utf-8"))["loci"]
        for rsid in PCSK9_RESOLVED + PCSK9_WAITING:
            with self.subTest(rsid=rsid):
                e = loci.get(rsid)
                self.assertIsNotNone(e, f"{rsid} cannot resolve from a VCF at all")
                self.assertEqual(e["gene"], "PCSK9")
                self.assertEqual(str(e["chrom"]), "1")
                self.assertIsInstance(e["pos"], int)
                # PCSK9 sits at roughly 1:55.03–55.07 Mb on GRCh38. This is not a
                # check of the exact coordinate — that came from Ensembl — but it
                # does catch a position pasted from the wrong assembly or the
                # wrong gene, which is how the one lost variant in this project's
                # history was lost.
                self.assertTrue(55_000_000 < e["pos"] < 55_100_000,
                                f"{rsid} at {e['pos']} is not inside PCSK9 on GRCh38")

    def test_a_direction_is_never_asserted_without_a_primary_source(self):
        d = json.loads((KN / "longevity_directions.json").read_text(encoding="utf-8"))
        for rsid in PCSK9_RESOLVED:
            with self.subTest(rsid=rsid):
                e = d["directions"][rsid]
                self.assertTrue(e.get("favorable"), "no favourable allele named")
                self.assertTrue(e.get("pmids"), "a direction with no PMID behind it")
                self.assertTrue(all(p.isdigit() for p in e["pmids"]))

    def test_a_variant_whose_direction_is_unresolved_says_so_instead_of_guessing(self):
        d = json.loads((KN / "longevity_directions.json").read_text(encoding="utf-8"))
        waiting = (d.get("unresolved") or {}).get("variants") or {}
        for rsid in PCSK9_WAITING:
            with self.subTest(rsid=rsid):
                self.assertNotIn(rsid, d["directions"],
                                 "a direction taken from reviews was written into the "
                                 "catalogue whose own rule asks for a primary source")
                self.assertIn(rsid, waiting, "the variant vanished instead of waiting")
                self.assertTrue((waiting[rsid].get("why") or {}).get("en"))


class TestNotACarrierIsNotSaidAboutAPositionNobodyRead(unittest.TestCase):

    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _run(self, **kw):
        d = _profile(**kw)
        self.dirs.append(d)
        return support.run_json(["lipid-genetics"], profile_dir=d)

    def test_an_empty_profile_reports_unread_rather_than_absent(self):
        r = self._run()
        for x in r["pcsk9"]:
            with self.subTest(rsid=x["rsid"]):
                self.assertIn(x["status"], ("unread", "no_data"))
                self.assertIsNone(x["carrier"],
                                  "carriage was decided for a position nobody read")
        self.assertIn("not been read", r["headline"])

    def test_a_read_genotype_is_counted_by_copies(self):
        r = self._run(genotypes=[{"gene": "PCSK9", "rsid": "rs11591147", "genotype": "GT"}])
        x = next(y for y in r["pcsk9"] if y["rsid"] == "rs11591147")
        self.assertEqual(x["status"], "read")
        self.assertEqual(x["copies"], 1)
        self.assertTrue(x["carrier"])
        self.assertTrue(x["verdict"], "one copy was counted and then not explained")

    def test_a_non_carrier_is_reported_as_the_ordinary_answer_it_is(self):
        r = self._run(genotypes=[{"gene": "PCSK9", "rsid": "rs11591147", "genotype": "GG"}])
        x = next(y for y in r["pcsk9"] if y["rsid"] == "rs11591147")
        self.assertFalse(x["carrier"])
        self.assertIn("common answer", r["headline"],
                      "an ordinary result is being presented as a finding")

    def test_the_population_caveat_travels_with_the_african_descent_variant(self):
        """«Not a carrier» of C679X says almost nothing outside one population.

        Without the caveat, a European reader gets a reassuring-looking negative
        from a variant that is close to absent in their population — an answer
        made from where the variant is common, not from them.
        """
        r = self._run(genotypes=[{"gene": "PCSK9", "rsid": "rs28362286", "genotype": "CC"}])
        x = next(y for y in r["pcsk9"] if y["rsid"] == "rs28362286")
        self.assertTrue(x["population_note"])
        self.assertIn("African", x["population_note"])


class TestAnEstimateOfLpaIsNotAMeasurementOfIt(unittest.TestCase):

    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _run(self, **kw):
        d = _profile(**kw)
        self.dirs.append(d)
        return support.run_json(["lipid-genetics"], profile_dir=d)

    def test_with_no_measurement_the_card_asks_for_the_test_rather_than_going_quiet(self):
        r = self._run()
        todo = (r["lpa"] or {}).get("what_to_do") or ""
        self.assertTrue(todo, "nothing measured and nothing said — the reader concludes "
                              "there was nothing to find")
        self.assertIn("nmol/L", todo, "the unit to ask for is not named, and the mg/dL "
                                      "conversion is not exact")
        self.assertIn("ONCE", todo.upper(), "the once-in-a-lifetime nature of the test — "
                                            "the thing that makes it worth ordering — is lost")

    def test_a_measured_value_is_read_against_its_bound(self):
        r = self._run(markers={"lpa": {"name": "Lp(a)", "unit": "nmol/L", "ref_high": 75,
                                       "series": [{"date": "2026-01", "value": 130}]}})
        m = (r["lpa"] or {}).get("measured")
        self.assertIsNotNone(m)
        self.assertTrue(m["above"])
        self.assertIsNone((r["lpa"] or {}).get("what_to_do"),
                          "a test was proposed that has already been done")

    def test_the_limit_of_the_genetic_estimate_is_always_carried(self):
        """The sentence exists whether or not a score happens to be on file.

        It is needed most in the case where a score IS present and a measurement
        is not — which is exactly the case where nobody would think to look it up.
        """
        r = self._run()
        limit = (r["lpa"] or {}).get("estimate_is_not_a_measurement") or ""
        self.assertTrue(limit)
        self.assertIn("KIV-2", limit, "the reason the estimate is limited is not given, "
                                      "so it reads as a hedge rather than as a fact")


if __name__ == "__main__":
    unittest.main()
