"""The status page, rendered over the three things that changed under it.

A field added to a structure and never printed is a field nobody reads. All
three of these were added on 09.09.2026 and all three are for a person rather
than for a consumer of JSON: the class of an exome, the reader that needs no
index, and the frame of open and closed paths.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import format as fmt


def status(**kw):
    base = {"ready": True, "vcf": "/tmp/x.vcf.gz", "sample": "ME",
            "callset": {"class": "exome", "observed_per_mb": 2, "coding_per_mb": 140},
            "engine": "linear",
            "paths": [{"path": "loci", "open": True},
                      {"path": "clinvar", "open": False, "why": "scan_not_run"},
                      {"path": "pgs", "open": False, "why": "input_too_narrow"}]}
    base.update(kw)
    return base


class TestEverythingMeasuredIsPrinted(unittest.TestCase):

    def test_the_exome_line_reaches_the_page(self):
        out = fmt.genome_status_report(status())
        self.assertIn("140", out, "the gene-dense number is half of the evidence")
        self.assertNotIn("⟦", out)

    def test_the_reader_that_needs_no_index_explains_the_wait(self):
        out = fmt.genome_status_report(status())
        self.assertIn("index", out.lower())

    def test_the_frame_is_printed_and_says_why_each_closed_path_is_closed(self):
        out = fmt.genome_status_report(status())
        for fragment in ("ClinVar", "polygenic"):
            self.assertIn(fragment, out)
        self.assertNotIn("⟦", out)

    def test_a_status_without_the_frame_still_renders(self):
        """Older callers hand this function a structure with no `paths` at all."""
        s = status()
        s.pop("paths")
        self.assertNotIn("⟦", fmt.genome_status_report(s))


if __name__ == "__main__":
    unittest.main()
