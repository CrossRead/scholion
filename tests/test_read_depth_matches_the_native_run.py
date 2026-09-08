"""`bamlite` against the native callability run, on the owner's own alignment.

Why an exact comparison and not a tolerance. The first version of this reader
counted deletions as depth and — the real defect — let a non-counted CIGAR
operation fail to advance the reference position, so everything downstream of a
deletion was placed at the wrong coordinate. It still agreed with the native run
to within 0.04 %, which is exactly the size of agreement that gets called
agreement. The bug was found by demanding equality; the tolerance would have
shipped it. So equality is what is asserted, and the numbers below are the ones
`genomic_work/callability/per_gene.tsv` holds, produced by mosdepth at --mapq 20.

This test skips itself where the BAM is not present, which is everywhere except
the owner's machine. A skip is honest here: the alternative — a synthetic BAM
written by the same code that reads it — would agree with itself and prove
nothing about the format.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import support

sys.path.insert(0, str(support.SRC))

WORK = Path(os.environ.get("SCHOLION_CALLABILITY_DIR",
                           str(Path.home() / "genomic_work" / "callability")))
BED = WORK / "genes.bed"
PER_GENE = WORK / "per_gene.tsv"


def _bam() -> Path | None:
    env = os.environ.get("SCHOLION_GENOME_BAM")
    if env and Path(env).exists():
        return Path(env)
    root = Path.home() / "genomic_work"
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir()):
        for cand in (d / f"{d.name}.merged.bam", d / f"{d.name}.markdup.bam"):
            if cand.exists() and Path(str(cand) + ".bai").exists():
                return cand
    return None


def _rows():
    """gene → (chrom, start1, end, mean, b1, b10, b20, b30) for the genes in both files."""
    if not (BED.exists() and PER_GENE.exists()):
        return {}
    where = {}
    for line in BED.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) >= 4:
            where[f[3]] = (f[0], int(f[1]) + 1, int(f[2]))
    out = {}
    for line in PER_GENE.read_text(encoding="utf-8").splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 7 or f[0] not in where:
            continue
        chrom, start, end = where[f[0]]
        out[f[0]] = (chrom, start, end, float(f[2].replace(",", ".")),
                     int(f[3]), int(f[4]), int(f[5]), int(f[6]))
    return out


BAM = _bam()
ROWS = _rows()
#: Four genes, not all ninety: three chromosomes including X, a well-covered gene
#: and a poorly covered one. The point is the format and the filters, and those
#: are the same for the ninety-first.
SAMPLE = ("MTHFR|CPIC", "SDHB|ACMG", "APOE|CPIC", "GLA|ACMG")


@unittest.skipUnless(BAM and ROWS, "no personal alignment / callability table here")
class DepthMatchesTheNativeRun(unittest.TestCase):
    def test_mean_and_every_threshold_are_identical(self):
        from scholion import bamlite
        checked = 0
        for name in SAMPLE:
            if name not in ROWS:
                continue
            chrom, start, end, mean, b1, b10, b20, b30 = ROWS[name]
            cov = bamlite.depth(BAM, chrom, start, end)
            self.assertEqual(len(cov), end - start + 1, name)
            self.assertAlmostEqual(sum(cov) / len(cov), mean, places=4, msg=name)
            for threshold, expected in ((1, b1), (10, b10), (20, b20), (30, b30)):
                self.assertEqual(sum(1 for c in cov if c >= threshold), expected,
                                 f"{name} at ≥{threshold}×")
            checked += 1
        self.assertTrue(checked, "the sample genes are not in the callability table")

    def test_a_position_outside_every_read_is_reported_as_zero_not_dropped(self):
        """A gap has to be visible; a shortened list would hide it silently."""
        from scholion import bamlite
        chrom, start, end, *_ = ROWS[SAMPLE[0]]
        cov = bamlite.depth(BAM, chrom, start, start + 9)
        self.assertEqual(len(cov), 10)


if __name__ == "__main__":
    unittest.main()
