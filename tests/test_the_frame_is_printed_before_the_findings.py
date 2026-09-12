"""Which questions this input opens, said before anything is answered.

Observed from outside, and it is the subtlest of the three things that review
found. The package was handed three panel-class VCFs and answered what those
files could support — a statin-transport genotype and a couple of catalogue loci
— while refusing, correctly, everything else. The reviewer's summary was that the
tool «pointed at statins and other things irrelevant to the patients».

Both halves of that are true and they are not in conflict. The answer was the
only answer the file could carry; nothing said so first. A reader who is handed
an answer without the question set it belongs to fills the set in themselves, and
fills it in wrong.

So the status carries the frame: five paths, each open or closed for THIS file,
and a closed one says what closed it. Two causes are kept apart there, because
they send a reader to opposite places: the input cannot carry the answer, and the
annotation this path reads has never been produced for this file. The second was
invisible — the narrow gate fired first and blamed the file for a table that was
simply missing.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome
from scholion.i18n import t as _t


def paths_of(profile, ready=True):
    return {p["path"]: p for p in genome.answerable_paths(profile, ready)}


class TestTheFrameExists(unittest.TestCase):

    def test_every_path_is_named(self):
        got = paths_of("whole_genome")
        self.assertEqual(set(got), set(genome.ANSWERABLE_PATHS))

    def test_with_no_genome_everything_is_closed_for_the_same_reason(self):
        for p in paths_of(None, ready=False).values():
            self.assertFalse(p["open"])
            self.assertEqual(p["why"], "no_genome")


class TestWhatANarrowInputCloses(unittest.TestCase):

    def test_a_panel_closes_the_screens_and_keeps_the_catalogue(self):
        got = paths_of("panel")
        self.assertTrue(got["loci"]["open"], "the catalogue is where a panel works as designed")
        self.assertTrue(got["pgx"]["open"])
        self.assertFalse(got["clinvar"]["open"])
        self.assertEqual(got["clinvar"]["why"], "input_too_narrow")
        self.assertFalse(got["pgs"]["open"])

    def test_an_exome_opens_the_two_that_look_for_a_known_pathogenic_variant(self):
        got = paths_of("exome")
        self.assertFalse(got["pgs"]["open"], "a score has no distribution behind it here")
        self.assertEqual(got["pgs"]["why"], "input_too_narrow")
        # ClinVar and ACMG are open as far as the INPUT is concerned; whether the
        # annotation exists is the other question, and it is asked separately.
        self.assertIn(got["acmg"].get("why"), (None, "scan_not_run"))

    def test_a_missing_annotation_is_not_blamed_on_the_file(self):
        """`input_too_narrow` and `scan_not_run` send a reader to opposite places:
        one says «this file cannot answer», the other «nobody has run the step
        that produces the answer». On a whole genome with no tables, it is the
        second."""
        got = paths_of("whole_genome")
        for path in ("clinvar", "acmg"):
            with self.subTest(path=path):
                if not got[path]["open"]:
                    self.assertEqual(got[path]["why"], "scan_not_run")


class TestTheFrameHasSentences(unittest.TestCase):

    def test_every_name_and_every_reason_prints(self):
        keys = ["genome_status.paths_head"]
        keys += ["paths." + p for p in genome.ANSWERABLE_PATHS]
        keys += ["paths.why.no_genome", "paths.why.input_too_narrow", "paths.why.scan_not_run"]
        import os
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for k in keys:
                    with self.subTest(lang=lang, key=k):
                        self.assertNotIn("⟦", _t(k))
            finally:
                os.environ.pop("SCHOLION_LANG", None)

    def test_the_status_carries_the_frame(self):
        self.assertIn("paths", genome.available())


class TestTheFrameReachesThePage(unittest.TestCase):
    """The command line said it, the browser did not.

    `/api/genome-status` has carried `paths` from the day it was written, and the
    page read three fields out of the answer and dropped that one. So the tab
    showed a green badge and a file name, and a reader who then asked it about a
    gene beyond the catalogue met a refusal with nothing around it to say the
    refusal was about the FILE. `test_the_page_asks_for_everything_the_server
    _offers` cannot catch this shape: the route was called: it is the field that
    was thrown away.
    """

    def setUp(self):
        from scholion import engine
        import pathlib
        self.page_path = (pathlib.Path(engine.__file__).resolve().parent.parent
                          / "web" / "index.html")
        if not self.page_path.exists():
            self.skipTest("this build carries no web page")
        self.page = self.page_path.read_text(encoding="utf-8")

    def test_the_page_reads_the_field(self):
        self.assertIn("st.paths", self.page,
                      "the status carries the frame and the page ignores it")

    def test_the_page_names_the_paths_from_the_catalogue(self):
        self.assertIn("'paths.'+p.path", self.page)
        self.assertIn("'paths.why.'+", self.page)

    def test_the_page_does_not_type_the_size_of_the_catalogue(self):
        """The count is passed from the answer, never written into the page: it
        was 54 in six sentences while the catalogue held 60."""
        self.assertIn("catalogue_by_assembly", self.page)

    def test_every_reason_the_engine_can_give_has_a_phrase(self):
        """The page composes this key at run time, so the static guard in
        `contract.check_i18n_keys` skips the family by design — «those families
        are covered by the tests that own the value sets instead». This is that
        test: the page would print ⟦paths.why.needs_index⟧ to the reader and
        nowhere else."""
        import os
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for why in ("no_genome", "input_too_narrow", "scan_not_run",
                            "needs_index", "not_sequenced"):
                    with self.subTest(lang=lang, why=why):
                        self.assertNotIn("\u27e6", _t("paths.why." + why))
            finally:
                os.environ.pop("SCHOLION_LANG", None)

    def test_the_two_row_phrases_exist_in_both_languages(self):
        import os
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for k in ("web.genome.path_open", "web.genome.path_closed"):
                    with self.subTest(lang=lang, key=k):
                        self.assertNotIn("\u27e6", _t(k))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


if __name__ == "__main__":
    unittest.main()
