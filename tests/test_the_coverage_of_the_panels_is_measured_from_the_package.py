"""The step that closes «not read» is a command of the package, not of a checkout.

A gene whose coverage nobody measured cannot be called clear, and the product
says so on every row. Until 13.09.2026 the measurement that closes it lived in a
shell script of the source tree and covered the 93 genes of the ACMG and CPIC
panels, while a body system's genetic half has been composed from GenCC — 1203
genes — since 0.5.0. On a real profile 1120 rows were honestly reported as not
read, and the person could do nothing about it without cloning the repository.

Held here:

  * the gene list is the union of what the panels actually read;
  * a coordinate comes from ClinVar or the gene gets no row — and «the table
    does not hold this gene» is then the true answer, not «read poorly»;
  * the fractions are measured against the INTERVAL, so an unread stretch lowers
    them instead of vanishing from the denominator;
  * the run is resumable per gene and a stop keeps what was measured;
  * the table is replaced only when every gene has been measured;
  * the plan of `recompute` offers the step when the table is behind the panels,
    and stops offering it when it is not;
  * every refusal this step can give is a sentence.
"""
from __future__ import annotations

import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import coverage
from scholion.i18n import en, ru

CLINVAR_ROWS = [
    ("1", 1000, "AAA:1"), ("1", 5000, "AAA:1"),          # a gene with a span
    ("1", 90000, "BBB:2"),                                # a gene with one variant
    ("MT", 300, "MT-TX:3"),                               # the mitochondrion
]


def _clinvar(dirpath: Path) -> str:
    p = dirpath / "clinvar.vcf.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for chrom, pos, gi in CLINVAR_ROWS:
            fh.write(f"{chrom}\t{pos}\t.\tA\tG\t.\t.\tGENEINFO={gi};CLNSIG=x\n")
    return str(p)


class TestTheGeneList(unittest.TestCase):

    def test_it_is_the_union_of_what_the_panels_read(self):
        from scholion import core
        g = coverage.genes()
        base = {n.upper() for spec in
                (core._read_knowledge("gencc_gene_disease.json").get("systems") or {}).values()
                for n in (spec.get("genes") or {})}
        acmg = {n.upper() for n in core._read_knowledge("acmg_sf.json").get("genes") or {}}
        self.assertTrue(base <= set(g), "the base composition of the systems is not in the list")
        self.assertTrue(acmg <= set(g), "the ACMG secondary findings are not in the list")
        self.assertGreater(len(g), len(acmg) * 5, "the list did not grow past the old panels")
        self.assertEqual({"ACMG", "CPIC", "PANEL"}, set(g.values()) | {"ACMG", "CPIC", "PANEL"})


class TestWhereAGeneIs(unittest.TestCase):

    def test_the_span_is_padded_and_the_mitochondrion_is_renamed(self):
        with tempfile.TemporaryDirectory() as d:
            where, without = coverage.spans({"AAA": "PANEL", "BBB": "PANEL", "MT-TX": "PANEL",
                                             "NOWHERE": "PANEL"}, _clinvar(Path(d)))
        self.assertEqual(("chr1", 1000 - coverage.PAD if 1000 > coverage.PAD else 0,
                          5000 + coverage.PAD), where["AAA"])
        self.assertEqual("chrM", where["MT-TX"][0],
                         "ClinVar says MT and a GRCh38 alignment says chrM")
        self.assertEqual(["NOWHERE"], without,
                         "a gene ClinVar has never heard of gets no invented coordinates")


class TestTheFractionsCountTheInterval(unittest.TestCase):

    def test_a_stretch_no_read_covered_lowers_the_fraction(self):
        # Ten bases of interval, four of them read at 30×: the rest are not
        # missing from the answer, they are zeros.
        lines = [f"chr1\t{i}\t30\n" for i in range(4)]
        d = coverage._depth("bam", "chr1:1-10", 10, run=lambda argv: lines)
        self.assertAlmostEqual(40.0, d["p10"])
        self.assertAlmostEqual(40.0, d["p20"])
        self.assertAlmostEqual(12.0, d["mean"])


class TestTheRun(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name)
        self.clinvar = _clinvar(self.home)
        self.env = mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(self.home)})
        self.env.start(); self.addCleanup(self.env.stop)
        from scholion import core
        core.reset_cache(); self.addCleanup(core.reset_cache)
        self.reqs = {"bam": str(self.home / "x.bam"), "clinvar": self.clinvar,
                     "samtools": "/usr/bin/samtools"}
        self.patches = [
            mock.patch.object(coverage, "requirements", lambda: dict(self.reqs)),
            mock.patch.object(coverage, "refusal", lambda req=None: None),
            mock.patch.object(coverage, "genes",
                              lambda: {"AAA": "PANEL", "BBB": "ACMG", "MT-TX": "PANEL"}),
            mock.patch("scholion.bamlite.reference_lengths",
                       lambda bam: {"chr1": 250_000, "chrM": 16_569}),
            # A genome this profile could have read: without one the step does
            # not apply at all, which is its own rule and has its own test.
            mock.patch("scholion.genome.vcf_path", lambda: Path(self.home / "g.vcf.gz")),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        self.seen = []

    def _run(self, argv):
        self.seen.append(argv)
        return [b"chr1\t1\t25\n"] * 100

    def test_the_table_and_its_record_are_written(self):
        r = coverage.measure(run=self._run)
        self.assertTrue(r["ok"], r)
        rows = (self.home / coverage.OUT_NAME).read_text(encoding="utf-8").splitlines()
        self.assertEqual("\t".join(coverage._HEADER), rows[0])
        self.assertEqual({"AAA", "BBB", "MT-TX"}, {l.split("\t")[0] for l in rows[1:]})
        rec = json.loads((self.home / coverage.RECORD_NAME).read_text(encoding="utf-8"))
        self.assertEqual(3, rec["genes_requested"])
        self.assertEqual(3, rec["genes_measured"])

    def test_a_stop_keeps_what_was_measured_and_writes_no_table(self):
        calls = {"n": 0}
        def stop():
            calls["n"] += 1
            return calls["n"] > 2
        r = coverage.measure(run=self._run, stop=stop)
        self.assertEqual("stopped", r["status"])
        self.assertFalse((self.home / coverage.OUT_NAME).exists(),
                         "a half-measured table must not replace the old one")
        self.assertTrue((self.home / coverage.PART_NAME).exists())
        before = len(self.seen)
        r = coverage.measure(run=self._run)
        self.assertTrue(r["ok"])
        self.assertLess(len(self.seen) - before, 3,
                        "the genes already measured were measured again")

    def test_the_state_moves_from_missing_to_current(self):
        self.assertEqual("missing", coverage.state()["status"])
        coverage.measure(run=self._run)
        self.assertEqual("current", coverage.state()["status"])
        with mock.patch.object(coverage, "genes",
                               lambda: {"AAA": "PANEL", "BBB": "ACMG", "MT-TX": "PANEL",
                                        "CCC": "PANEL"}):
            self.assertEqual("older_than_panels", coverage.state()["status"],
                             "a list that grew leaves the table behind it")

    def test_the_plan_offers_the_step_and_then_stops_offering_it(self):
        from scholion import recompute
        keys = lambda: [s["key"] for s in recompute.plan()["steps"]]
        self.assertIn("scholion coverage", keys())
        coverage.measure(run=self._run)
        step = [s for s in recompute.plan()["steps"] if s["key"] == "scholion coverage"]
        self.assertTrue(not step or step[0]["state"] == "already_current", step)


class TestAProfileWithNoGenome(unittest.TestCase):

    def test_the_step_does_not_apply_and_says_so(self):
        with mock.patch("scholion.genome.vcf_path", lambda: None):
            self.assertEqual("no_vcf", coverage.state()["status"],
                             "the coverage of genes nobody sequenced is not a gap in a"
                             " profile of laboratory results — it is a step that does"
                             " not apply to it")


class TestEveryRefusalIsASentence(unittest.TestCase):

    def test_each_code_has_a_phrase_in_both_languages(self):
        for code in ("no_bam", "no_index", "no_clinvar", "no_samtools"):
            for words in (en.MESSAGES, ru.MESSAGES):
                with self.subTest(code=code):
                    self.assertIn("recompute.why." + code, words)

    def test_the_refusal_names_the_missing_thing_in_order(self):
        import tempfile
        self.assertEqual("no_bam", coverage.refusal({"bam": None, "clinvar": "c", "samtools": "s"}))
        with tempfile.TemporaryDirectory() as d:
            bam = Path(d) / "x.bam"
            bam.write_bytes(b"")
            self.assertEqual("no_index", coverage.refusal(
                {"bam": str(bam), "clinvar": "c", "samtools": "s"}),
                "an alignment without its index is named before anything else is looked for")
            Path(str(bam) + ".bai").write_bytes(b"")
            self.assertEqual("no_clinvar", coverage.refusal(
                {"bam": str(bam), "clinvar": None, "samtools": "s"}))
            self.assertEqual("no_samtools", coverage.refusal(
                {"bam": str(bam), "clinvar": "c", "samtools": None}))
            self.assertIsNone(coverage.refusal(
                {"bam": str(bam), "clinvar": "c", "samtools": "s"}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
