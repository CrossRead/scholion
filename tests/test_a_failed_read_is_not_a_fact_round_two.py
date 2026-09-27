"""A failure is never printed as a fact about the person — four more places.

Task 209, round 2. Each of these turned a read that failed into an answer:

* the gene report: bcftools exiting non-zero on a region (or the own tabix
  reader raising) came back as no rows, printed «0 variants in the gene»;
* the call-set composition: a head of the file that could not be read gave
  `sampled: 0`, which left «this file carries SNVs» at its default «yes», so a
  missing row at an SNV was still presumed the reference;
* Ensembl: a failed request for the coding exons was read as «no CDS», cached,
  and every later report on that gene said the annotation knew none;
* the status: a SUBJECT.json that could not be read was reported with the
  reason `another_person`, whose sentence claims the file says the genome is a
  published reference sample — something nobody read.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (puts src/ on the path)
from scholion import callset, core, gene_region, genes, genome
from scholion import linear as lin
from scholion.i18n import messages, t as _t

VCF = "/nonexistent/sample.vcf.gz"

LOC = {"gene": "TESTGENE", "chrom": "1", "start": 1000, "end": 2000, "strand": "+",
       "assembly": genes.ASSEMBLY, "transcript": "ENSTTEST",
       "cds": [["1", 1100, 1200]], "source": "gff3"}


class _RangeOnBcftools(unittest.TestCase):
    """Pin `_query_region_range` onto a seeking reader, whatever this machine has."""

    def setUp(self):
        self._patches = [
            mock.patch.object(genome, "contig_name", return_value="chr1"),
            mock.patch.object(genome, "engine_pin", return_value="auto"),
            mock.patch.object(genome, "_index_usable", return_value=True),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])


class TestARegionReadThatFailedIsNotZeroVariants(_RangeOnBcftools):

    def _failed_run(self):
        return subprocess.CompletedProcess(
            [], 1, stdout="", stderr="[E::hts_idx_load3] Could not load the index")

    def test_a_non_zero_exit_raises(self):
        with mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome.subprocess, "run", return_value=self._failed_run()):
            with self.assertRaises(lin.Unreadable) as cm:
                genome._query_region_range(VCF, "1", 1000, 2000)
        self.assertEqual("reader_failed", cm.exception.why)
        self.assertIn("Could not load the index", cm.exception.detail)

    def test_a_timeout_raises(self):
        with mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome.subprocess, "run",
                                  side_effect=subprocess.TimeoutExpired("bcftools", 60)):
            with self.assertRaises(lin.Unreadable):
                genome._query_region_range(VCF, "1", 1000, 2000)

    def test_the_own_tabix_reader_failing_raises_by_name(self):
        from scholion import tabixlite
        with mock.patch.object(genome, "_have_bcftools", return_value=False), \
                mock.patch.object(genome, "_query_pysam", return_value=None), \
                mock.patch.object(tabixlite, "query", side_effect=OSError("truncated block")):
            with self.assertRaises(lin.Unreadable) as cm:
                genome._query_region_range(VCF, "1", 1000, 2000)
        self.assertEqual("reader_failed", cm.exception.why)

    def test_a_clean_empty_run_is_still_no_rows(self):
        done = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome.subprocess, "run", return_value=done):
            self.assertEqual([], genome._query_region_range(VCF, "1", 1000, 2000))

    def test_the_gene_report_names_the_failure_and_counts_nothing(self):
        ready = {"ready": True, "assembly": genes.ASSEMBLY,
                 "paths": [{"path": "region", "open": True}]}
        with mock.patch.object(genes, "resolve", return_value=dict(LOC)), \
                mock.patch.object(genome, "available", return_value=ready), \
                mock.patch.object(genome, "vcf_path", return_value=Path(VCF)), \
                mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome.subprocess, "run", return_value=self._failed_run()):
            r = gene_region.report("TESTGENE", allow_network=False)
        self.assertEqual("unreadable_file", r["status"])
        self.assertEqual("reader_failed", r["reason"])
        self.assertNotIn("variants", r, "a failed read was counted")
        from scholion.format_genome import _gene_region_report
        text = _gene_region_report(r)
        zero = _t("gene.counts", total=0, coding=0, consequential=0)
        self.assertNotIn(zero, text, "the report printed a variant count over a failed read")
        self.assertIn("Could not load the index", text)

    def test_the_build_probe_claims_nothing_when_the_read_failed(self):
        with mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome.subprocess, "run", return_value=self._failed_run()):
            self.assertIsNone(genome._probe_assembly(VCF))


class TestACompositionThatCouldNotBeReadIsUnmeasured(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vcf = os.path.join(self.tmp.name, "x.vcf.gz")
        with open(self.vcf, "wb") as fh:
            fh.write(b"not read")
        self.cache = Path(self.tmp.name) / "callset2-test.json"

    def _measure(self):
        import gzip
        with mock.patch.object(callset, "_cache_path", return_value=self.cache), \
                mock.patch.object(callset, "_probe", return_value=None), \
                mock.patch.object(callset, "_coding_probes", return_value=[]), \
                mock.patch.object(lin, "probe_counts", return_value=None), \
                mock.patch.object(gzip, "open", side_effect=OSError("CRC check failed")):
            return callset.measure(self.vcf)

    def test_the_failure_is_carried_and_the_class_is_unmeasured(self):
        m = self._measure()
        self.assertIn("CRC check failed", m.get("composition_unread") or "")
        self.assertEqual("unmeasured", m["class"])

    def test_an_snv_is_not_said_to_be_answerable(self):
        m = self._measure()
        self.assertFalse(callset.answers_variant(m, "C", "G"),
                         "a file nobody read was said to carry substitutions")

    def test_a_failed_measurement_is_not_cached(self):
        self._measure()
        self.assertFalse(self.cache.exists(), "a failed read was cached as a measurement")

    def test_even_measured_breadth_does_not_outvote_it(self):
        m = dict(callset.unmeasured(), measured=True, observed_per_mb=1500,
                 composition_unread="OSError: x")
        self.assertEqual("unmeasured", callset._classify(m))

    def test_the_locus_is_refused_by_name_not_presumed_reference(self):
        old = os.environ.get("SCHOLION_GENOME_VCF")
        os.environ["SCHOLION_GENOME_VCF"] = str(
            support.ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz")
        core.reset_cache()

        def restore():
            if old is None:
                os.environ.pop("SCHOLION_GENOME_VCF", None)
            else:
                os.environ["SCHOLION_GENOME_VCF"] = old
            core.reset_cache()
        self.addCleanup(restore)
        loc = dict(genome.loci()["loci"]["rs1800462"], rsid="rs1800462")
        unread = dict(callset.unmeasured(), composition_unread="OSError: CRC check failed")
        with mock.patch.object(genome, "_query_region", lambda vcf, chrom, pos: []), \
                mock.patch.object(genome, "_ref_evidence", return_value=None), \
                mock.patch.object(genome, "assembly_of", return_value=genes.ASSEMBLY), \
                mock.patch.object(callset, "measure", return_value=unread):
            r = genome._gt_at(loc)
        self.assertIsNone(r.get("genotype"), r)
        self.assertEqual("unreadable_file", r["confidence"])
        self.assertEqual("composition_unread", r["reason"])
        self.assertIn("CRC check failed", r["note"])


class TestAFailedEnsemblRequestIsNotNoCds(unittest.TestCase):

    GENE = {"assembly_name": genes.ASSEMBLY, "seq_region_name": "7", "id": "ENSG1",
            "display_name": "TESTGENE", "canonical_transcript": "ENST1.3",
            "start": 100, "end": 900, "strand": 1}

    def test_a_failed_second_request_is_not_resolved(self):
        from scholion import net
        with mock.patch.object(net, "get_json", side_effect=[self.GENE, None]):
            self.assertIsNone(genes.from_ensembl("TESTGENE"))

    def test_an_error_object_is_not_resolved(self):
        from scholion import net
        with mock.patch.object(net, "get_json", side_effect=[self.GENE, {"error": "busy"}]):
            self.assertIsNone(genes.from_ensembl("TESTGENE"))

    def test_nothing_is_cached_from_a_failed_request(self):
        from scholion import net
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"SCHOLION_CACHE_DIR": d,
                                             "SCHOLION_GENE_GFF3": os.path.join(d, "none.gff3")}), \
                mock.patch.object(genes, "gff3_candidates", return_value=[]), \
                mock.patch.object(net, "get_json", side_effect=[self.GENE, None]):
            self.assertIsNone(genes.resolve("TESTGENE", allow_network=True))
            self.assertNotIn("TESTGENE", genes._load_cache())

    def test_a_real_empty_list_is_still_a_gene_without_cds(self):
        from scholion import net
        with mock.patch.object(net, "get_json", side_effect=[self.GENE, []]):
            rec = genes.from_ensembl("TESTGENE")
        self.assertEqual([], rec["cds"])

    def test_the_cds_is_read_when_the_request_succeeds(self):
        from scholion import net
        seg = [{"Parent": "ENST1.3", "start": 200, "end": 260}]
        with mock.patch.object(net, "get_json", side_effect=[self.GENE, seg]):
            rec = genes.from_ensembl("TESTGENE")
        self.assertEqual([["7", 200, 260]], rec["cds"])


class TestAnUnreadableSubjectIsNotAnotherPerson(unittest.TestCase):

    CONFLICT = {"reason": "subject_unreadable", "genome_subject": None,
                "profile_subject": "self", "who": None, "path": VCF,
                "message": "m", "fix": "f"}

    def setUp(self):
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def test_the_status_carries_the_conflicts_own_reason(self):
        with mock.patch.object(genome, "not_ours", return_value=dict(self.CONFLICT)):
            st = genome.available()
        self.assertFalse(st["ready"])
        self.assertEqual("subject_unreadable", st["reason"])

    def test_the_reason_is_enumerated_and_has_sentences(self):
        self.assertIn("subject_unreadable", genome.REFUSAL_REASONS)
        for key in ("genome.refused.subject_unreadable",
                    "genome.refused_head.subject_unreadable"):
            for lang in ("en", "ru"):
                with self.subTest(key=key, lang=lang):
                    self.assertTrue(messages(lang).get(key), "no sentence for this reason")

    def test_the_locus_sentence_does_not_claim_the_file_was_read(self):
        with mock.patch.object(genome, "not_ours", return_value=dict(self.CONFLICT)):
            r = genome.lookup(rsid="rs1800462")
        self.assertEqual("subject_unreadable", r["reason"])
        self.assertNotIn("says the genome is a published reference sample", r["message"])

    def test_another_person_stays_another_person(self):
        other = dict(self.CONFLICT, reason="another_person")
        with mock.patch.object(genome, "not_ours", return_value=other):
            self.assertEqual("another_person", genome.available()["reason"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
