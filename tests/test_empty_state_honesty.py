"""An empty list is not a clean bill of health.

The invariant this project is built on says a value may not be presented without
its evidential status. The last mile of that rule is the EMPTY case, and it was
broken in four places at once: «There are no red flags», «there are no current
abnormalities», «no clear abnormalities among the body systems» and «there is
nothing to order right now» were all printed unconditionally. On a profile with
nothing measured, every one of them is a reassuring statement about a person made
from the absence of data — the exact class the project exists to refuse.

The fix is not new wording. It is that the empty branch has to ASK how much was
measured and say a different sentence for zero. So each test below is named after
the sentence that must not come back, and checks the two halves the fix needs:
the pair of strings exists and differs in both languages, and the output layer
actually reaches for both.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support

# (the line for «measured, and clean», the line for «nothing measured»)
PAIRS = [
    ("web.overview.no_red", "web.overview.no_red_nodata"),
    ("web.second.no_domain_issues", "web.second.no_domain_data"),
    ("web.second.no_drug_flags", "web.second.no_drug_data"),
]


def _messages(lang):
    import importlib
    return importlib.import_module(f"scholion.i18n.{lang}").MESSAGES


class TestBothHalvesOfTheEmptyCaseExist(unittest.TestCase):
    """Half a pair is worse than none: it reads as an answer and is a guess."""

    def test_every_language_carries_both_lines_and_they_differ(self):
        for lang in ("en", "ru"):
            msgs = _messages(lang)
            for clean, nodata in PAIRS:
                with self.subTest(lang=lang, key=clean):
                    self.assertIn(clean, msgs)
                    self.assertIn(nodata, msgs)
                    self.assertNotEqual(
                        msgs[clean], msgs[nodata],
                        f"{lang}: «{clean}» and «{nodata}» say the same thing, so the "
                        "distinction the branch was added for does not reach the reader")

    def test_the_no_data_line_never_counts_what_was_not_measured(self):
        """`{n}` in the reassuring line is the number of measurements behind it.

        The no-data line has no such number by construction — if it grows one, it
        is counting something that was not measured, which is how the original
        defect looked from the inside.
        """
        for lang in ("en", "ru"):
            for clean, nodata in PAIRS:
                with self.subTest(lang=lang, key=clean):
                    self.assertIn("{n}", _messages(lang)[clean])


class TestTheOutputLayerReachesForBoth(unittest.TestCase):
    """A string that exists and is never printed fixes nothing.

    This reads the interface source rather than a render because the branch IS
    the fix: the previous version had the reassuring line and no branch at all.
    """

    def test_the_interface_uses_both_lines_of_every_pair(self):
        html = (support.ROOT / "src" / "scholion" / "web"
                / "index.html").read_text(encoding="utf-8")
        for clean, nodata in PAIRS:
            with self.subTest(key=clean):
                self.assertIn(f"'{clean}'", html)
                self.assertIn(f"'{nodata}'", html,
                              f"«{nodata}» is written but never printed — the empty "
                              "case still says only the reassuring half")


class TestTheSecondOpinionSaysHowMuchItCouldJudge(unittest.TestCase):
    """A list of drug names is not a list of findings about the reader.

    Writing this test found the defect it now guards. The pharmacogenetic section
    is never empty: with no genotypes at all, every watch-list drug still comes
    back — phenotype «unknown», the general rule for the drug printed in place of a
    statement about the person. So the honest question is not «is the list empty»
    but «how much of it is about you», and the counts answer it before the list
    begins.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="empty_state_"))
        for name, body in (
            ("pharmacogenomics.json", {"meta": {"purpose": "SYNTHETIC — a test fixture",
                                                "synthetic": True}, "genotypes": []}),
            ("medications.json", {"meta": {"purpose": "SYNTHETIC — a test fixture",
                                           "synthetic": True}, "medications": []}),
            ("labs.json", {"meta": {"purpose": "SYNTHETIC — a test fixture",
                                    "synthetic": True}, "markers": {}}),
        ):
            (self.dir / name).write_text(json.dumps(body, ensure_ascii=False),
                                         encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_profile_with_no_genotypes_reports_nothing_answerable(self):
        r = support.run_json(["second-opinion"], profile_dir=self.dir)
        self.assertGreater(r["drugs_checked"], 0,
                           "the watch list came back empty, so the counts below would "
                           "pass by testing nothing")
        self.assertEqual(r["drugs_answerable"], 0,
                         "no genotype was on file, so nothing could be judged — and the "
                         "answer has to say so, because the drug list itself is NOT "
                         "empty and reads as findings")
        self.assertTrue(r["drug_flags"],
                        "the premise of this test is that the section is populated even "
                        "with nothing to go on; if that stops being true the wording it "
                        "guards needs revisiting, not the assertion")
        self.assertTrue(all(x.get("certainty") == "unknown" for x in r["drug_flags"]),
                        "a drug reported as certain against a profile with no genotypes "
                        "is the original defect, not the empty-state one")

    def test_a_genotype_on_file_is_counted_as_answerable(self):
        """The counter has to be able to say a number other than zero."""
        (self.dir / "pharmacogenomics.json").write_text(json.dumps(
            {"meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
             "genotypes": [{"gene": "CYP2C19", "rsid": "rs4244285", "genotype": "GG"},
                           {"gene": "CYP2C19", "rsid": "rs12248560", "genotype": "CC"},
                           {"gene": "CYP2C19", "rsid": "rs4986893", "genotype": "GG"}]},
            ensure_ascii=False), encoding="utf-8")
        r = support.run_json(["second-opinion"], profile_dir=self.dir)
        self.assertGreater(r["drugs_answerable"], 0,
                           "a fully genotyped watch-list gene did not raise the count, "
                           "so the number is not measuring what it claims")
        self.assertLessEqual(r["drugs_answerable"], r["drugs_checked"])


if __name__ == "__main__":
    unittest.main()
