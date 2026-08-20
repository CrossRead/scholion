"""A laboratory's summary sheet does not overrule the person's own reads.

Task 64. `core.genotype_status` returned the profile entry the moment it found
one and never reached the VCF. So `rs4988235`, `rs1801133` and `rs429358` came
back as `reported / profile / depth=None` — copied off an Evogen summary — while
the person's own aligned reads sat unread in a file on the same disk. Meanwhile
`scholion genome rs4988235` DID read the VCF and answered «reference confirmed
by a call (0/0), coverage 32». Two routes to one fact, disagreeing, and nothing
in either saying so.

The rule this pins down has two halves and both matter:

  · a genuine read outranks a report — it carries a depth, it can be re-examined,
    and it is the thing the report was made from;
  · `assumed_ref` is NOT a read. A missing row in a -mv VCF means «the reference,
    OR nothing was looked at there». Letting that overrule a laboratory's
    positive finding would be this project's oldest defect wearing new clothes:
    more data producing a less cautious answer.

Why the seventeen known disagreements between that report and the reads never
tripped it: `genotype_status` answered `None` for every one of them, because
those rsIDs are not in the coordinate catalogue. The priority was never exercised
where it is dangerous, and the absence of an error there proved nothing. So the
collisions below are built by hand.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support


class TestWhichSourceWins(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="rank_"))
        (self.dir / "pharmacogenomics.json").write_text(json.dumps({
            "_meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
            "genotypes": [{"gene": "MTHFR", "rsid": "rs1801133", "genotype": "CT"}]},
            ensure_ascii=False), encoding="utf-8")
        import os
        self.env = dict(os.environ, SCHOLION_PROFILE_DIR=str(self.dir),
                        PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                        SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _status(self, rsid, vcf_answer):
        """`genotype_status` with the VCF layer replaced by a fixed answer.

        The genome layer is stubbed rather than built: what is under test is the
        RANKING, and a test that needed a real VCF would only run where one
        exists — which is the owner's machine, the single environment where this
        defect was invisible.
        """
        import subprocess, sys
        code = (
            "import sys, json; sys.path.insert(0, %r);\n"
            "from scholion import core, genome;\n"
            "genome.genotype_from_vcf = lambda r: %r;\n"
            "print(json.dumps(core.genotype_status(%r)))"
            % (str(support.SRC), vcf_answer, rsid)
        )
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_a_genuine_read_outranks_the_report_and_says_they_disagree(self):
        st = self._status("rs1801133", {"genotype": "CC", "confidence": "called",
                                        "source": "vcf", "depth": 32})
        self.assertEqual(st["genotype"], "CC", "the report won over a genuine call")
        self.assertEqual(st["source"], "vcf")
        self.assertIn("conflict", st, "two sources disagreed and nothing said so")
        self.assertEqual(st["conflict"]["reported"], "CT")
        self.assertEqual(st["conflict"]["called"], "CC")

    def test_an_unread_position_never_overrules_a_laboratory(self):
        """`assumed_ref` means «reference OR nothing looked at». It cannot win.

        This is the half of the rule that keeps the fix from becoming the defect
        it replaces: a VCF with no row at a position would otherwise silently
        erase a positive finding the laboratory actually made.
        """
        st = self._status("rs1801133", {"genotype": "CC", "confidence": "assumed_ref",
                                        "source": "vcf"})
        self.assertEqual(st["genotype"], "CT", "an unread position erased a report")
        self.assertEqual(st["source"], "profile")
        self.assertNotIn("conflict", st)

    def test_agreement_between_the_two_is_reported_as_agreement(self):
        st = self._status("rs1801133", {"genotype": "C/T", "confidence": "called",
                                        "source": "vcf", "depth": 41})
        self.assertEqual(st["source"], "vcf")
        self.assertNotIn("conflict", st,
                         "«C/T» and «CT» were read as two different genotypes")
        self.assertEqual(st.get("confirmed_by"), "profile")

    def test_phase_and_order_do_not_manufacture_a_disagreement(self):
        for written in ("T|C", "TC", "T/C"):
            with self.subTest(vcf=written):
                st = self._status("rs1801133", {"genotype": written, "confidence": "called",
                                                "source": "vcf", "depth": 20})
                self.assertNotIn("conflict", st)

    def test_with_no_vcf_at_all_the_report_still_answers(self):
        st = self._status("rs1801133", None)
        self.assertEqual(st["genotype"], "CT")
        self.assertEqual(st["source"], "profile")

    def test_a_position_in_neither_source_stays_unknown(self):
        st = self._status("rs4988235", None)
        self.assertIsNone(st, "a genotype was invented for a position nobody has")


if __name__ == "__main__":
    unittest.main()
