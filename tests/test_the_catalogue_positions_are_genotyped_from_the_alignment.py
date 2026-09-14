"""The catalogue positions are genotyped from the alignment, and the file says which catalogue it answers for.

A position missing from a VCF called with `-v` is «reference OR not covered»;
only a file genotyped from the alignment without `-v` turns it into a confirmed
reference. The file is only as complete as the catalogue it was made from: after
the catalogue grew from 61 to 113 positions, a file genotyped in August left 21
of 92 radar panel positions not read. Until 13.09.2026 the step lived in two
shell scripts of the source tree, which a pip install does not carry.

Held here, with a stand-in for bcftools so that no alignment is needed: the
refusals name what is missing, in order; one BED per chromosome in the build of
the alignment, 0-based, never converted between builds, and no `-v` anywhere;
the file is replaced only when every chromosome succeeded; a stop between
chromosomes leaves the previous file; the record beside the file carries the
catalogue's size and date, and `state()` reads it.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import struct
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import support
from scholion import format as fmt
from scholion import sites

GRCH38 = {"assembly": "GRCh38", "prefix": "chr",
          "contigs": {f"chr{c}" for c in [*map(str, range(1, 23)), "X", "Y"]}}
GRCH37 = {"assembly": "GRCh37", "prefix": "",
          "contigs": {c for c in [*map(str, range(1, 23)), "X", "Y"]}}


class _Genome(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sites_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.genome = self.root / "genome"
        self.genome.mkdir()
        self.vcf = self.genome / "sample.full.vcf.gz"
        self.vcf.write_bytes(gzip.compress(b"##fileformat=VCFv4.2\n"))
        self.bam = self.root / "sample.bam"
        self.bam.write_bytes(b"")
        Path(str(self.bam) + ".bai").write_bytes(b"")
        self.ref = self.root / "ref.fa"
        self.ref.write_text(">chr1\nN\n", encoding="utf-8")
        Path(str(self.ref) + ".fai").write_text("chr1\t1\t6\t1\t2\n", encoding="utf-8")
        env = mock.patch.dict(os.environ, {
            "HOME": str(self.root), "SCHOLION_GENOME_DIR": str(self.genome),
            "SCHOLION_GENOME_VCF": str(self.vcf), "SCHOLION_GENOME_BAM": str(self.bam),
            "SCHOLION_GENOME_REFERENCE": str(self.ref)})
        env.start()
        self.addCleanup(env.stop)
        which = mock.patch.object(sites.shutil, "which", return_value="/usr/bin/bcftools")
        self.which = which.start()
        self.addCleanup(which.stop)
        from scholion import core
        core.reset_cache()
        self.addCleanup(core.reset_cache)
        self.calls = []

    def fake_run(self, fail_on=None):
        def run(cmds):
            self.calls.append(cmds)
            argv = cmds[-1]
            beds = [a for c in cmds for i, a in enumerate(c) if i and c[i - 1] == "-R"]
            if fail_on and beds and Path(beds[0]).stem == fail_on:
                return {"rc": 1, "stderr": "[mpileup] failed to open the alignment"}
            if "-o" in argv:
                Path(argv[argv.index("-o") + 1]).write_text("vcf", encoding="utf-8")
            if argv[:2] == ["bcftools", "index"]:
                Path(argv[-1] + ".tbi").write_text("tbi", encoding="utf-8")
            return {"rc": 0, "stderr": ""}
        return run

    def genotype(self, build=GRCH38, **kw):
        with mock.patch.object(sites, "alignment_build", return_value=build):
            return sites.genotype(run=kw.pop("run", self.fake_run()), **kw)


class TestTheRefusals(_Genome):

    def test_each_missing_piece_is_named_in_order(self):
        Path(str(self.bam) + ".bai").unlink()
        self.assertEqual("no_index", sites.genotype()["reason"])
        Path(str(self.bam) + ".bai").write_bytes(b"")
        with mock.patch.dict(os.environ, {"SCHOLION_GENOME_REFERENCE": str(self.root / "none.fa")}):
            self.assertEqual("no_reference", sites.genotype()["reason"])
        self.which.return_value = None
        self.assertEqual("no_bcftools", sites.genotype()["reason"])
        with mock.patch.dict(os.environ, {"SCHOLION_GENOME_BAM": str(self.root / "none.bam")}):
            r = sites.genotype()
        self.assertEqual("no_bam", r["reason"])
        self.assertIn("SCHOLION_GENOME_BAM", fmt.genotype_sites_report(r))

    def test_the_command_line_refuses_in_words_and_fails(self):
        code, out, err = support.run(["genotype-sites"])
        self.assertEqual(1, code, err[-600:])
        self.assertIn("no genome is connected", out)


class TestTheWork(_Genome):

    def bed_lines(self):
        lines = []
        for cmds in self.calls:
            for c in cmds:
                if "-R" in c:
                    lines += Path(c[c.index("-R") + 1]).read_text(encoding="utf-8").splitlines() \
                        if Path(c[c.index("-R") + 1]).exists() else []
        return lines

    def test_one_bed_per_chromosome_in_the_alignment_build_and_no_variant_only_call(self):
        seen = {}

        def run(cmds):
            for c in cmds:
                if "-R" in c:
                    seen[Path(c[c.index("-R") + 1]).stem] = Path(c[c.index("-R") + 1]).read_text(encoding="utf-8")
            return self.fake_run()(cmds)

        ticks = []
        r = self.genotype(run=run, progress=lambda d, t, item=None: ticks.append((d, t, item)))
        self.assertTrue(r["ok"], r)
        self.assertIn("chr19\t44908683\t44908684\trs429358|APOE\n", seen["19"])
        for cmds in self.calls:
            for c in cmds:
                self.assertNotIn("-v", c, "a variant-only call is exactly what this file exists to avoid")
        self.assertEqual((0, r["chromosomes"], "chr1"), ticks[0])
        self.assertEqual((r["chromosomes"], r["chromosomes"], None), ticks[-1])
        cat = sites.catalogue()
        record = json.loads((self.genome / sites.RECORD_NAME).read_text(encoding="utf-8"))
        self.assertEqual((cat["positions"], cat["updated"], "GRCh38"),
                         (record["catalogue_positions"], record["catalogue_updated"], record["assembly"]))
        self.assertEqual("vcf", (self.genome / sites.OUT_NAME).read_text(encoding="utf-8"))
        self.assertEqual([], [p.name for p in self.genome.iterdir() if p.name.startswith(".loci_sites-")])
        self.assertIn("✓", fmt.genotype_sites_report(r))

    def test_a_grch37_alignment_reads_the_grch37_coordinates_and_nothing_converted(self):
        seen = {}

        def run(cmds):
            for c in cmds:
                if "-R" in c:
                    seen[Path(c[c.index("-R") + 1]).stem] = Path(c[c.index("-R") + 1]).read_text(encoding="utf-8")
            return self.fake_run()(cmds)

        r = self.genotype(build=GRCH37, run=run)
        self.assertTrue(r["ok"], r)
        self.assertIn("19\t45411940\t45411941\trs429358|APOE\n", seen["19"])
        cat = sites.catalogue()
        without = sum(1 for l in cat["loci"].values() if not l.get("pos_grch37"))
        self.assertGreater(without, 0)
        self.assertEqual(r["positions"], sum(len(v.splitlines()) for v in seen.values()))
        self.assertLess(r["positions"], cat["positions"])

    def test_a_failed_chromosome_leaves_the_previous_file_as_it_was(self):
        (self.genome / sites.OUT_NAME).write_text("old", encoding="utf-8")
        r = self.genotype(run=self.fake_run(fail_on="2"))
        self.assertEqual(("failed", "chr2"), (r["status"], r["step"]))
        self.assertEqual("old", (self.genome / sites.OUT_NAME).read_text(encoding="utf-8"))
        self.assertEqual([], [p.name for p in self.genome.iterdir() if p.name.startswith(".loci_sites-")])
        self.assertIn("mpileup", fmt.genotype_sites_report(r))

    def test_a_stop_between_chromosomes_leaves_the_previous_file(self):
        (self.genome / sites.OUT_NAME).write_text("old", encoding="utf-8")
        asked = []
        r = self.genotype(stop=lambda: asked.append(1) or len(asked) > 2)
        self.assertEqual("stopped", r["status"])
        self.assertEqual("old", (self.genome / sites.OUT_NAME).read_text(encoding="utf-8"))


class TestTheState(_Genome):

    def test_the_record_and_the_date_decide_whether_the_file_is_current(self):
        cat = sites.catalogue()
        self.assertEqual("missing", sites.state()["status"])
        out = self.genome / sites.OUT_NAME
        out.write_text("vcf", encoding="utf-8")
        old = date(2020, 1, 1).toordinal()
        stamp = (date.fromordinal(old) - date(1970, 1, 1)).days * 86400
        os.utime(out, (stamp, stamp))
        self.assertEqual("older_than_catalogue", sites.state()["status"])
        os.utime(out, None)
        self.assertEqual("unrecorded", sites.state()["status"])
        record = self.genome / sites.RECORD_NAME
        record.write_text(json.dumps({"catalogue_positions": 61, "catalogue_updated": "2026-08-01"}),
                          encoding="utf-8")
        self.assertEqual("older_than_catalogue", sites.state()["status"])
        record.write_text(json.dumps({"catalogue_positions": cat["positions"],
                                      "catalogue_updated": cat["updated"]}), encoding="utf-8")
        self.assertEqual("current", sites.state()["status"])

    def test_the_build_is_read_from_the_header_of_a_real_bam(self):
        header = b"BAM\x01" + struct.pack("<i", 0) + struct.pack("<i", 2)
        for name, length in ((b"chr1\x00", 248956422), (b"chr2\x00", 242193529)):
            header += struct.pack("<i", len(name)) + name + struct.pack("<i", length)
        self.bam.write_bytes(gzip.compress(header))
        build = sites.alignment_build(str(self.bam))
        self.assertEqual(("GRCh38", "chr"), (build["assembly"], build["prefix"]))


if __name__ == "__main__":
    unittest.main()
