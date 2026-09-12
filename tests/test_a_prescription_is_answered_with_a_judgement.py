"""The question comes from the prescription, and the answer is about the decision.

A clinician does not carry a list of genes. She carries a prescription and derives
the list from it, every time: before a choleretic, is there Gilbert's and what
about the methionine synthases; for a vitamin D dose, the receptor and the
metabolism; for oestrogens, COMT, aromatase, the receptors. The product answered
«gene → what we hold», so she did that derivation by hand and the tool watched.

Three things follow, and they are what this file guards.

The link between a prescription and a gene has a CLASS, and the class decides what
may be said: a rule with a table, a pair recognised with no table, a mechanism with
no rule, a gene asked about from which nothing follows, and a gene this build does
not hold. The first two are computed from this build's own tables. The other three
cannot be: which genes belong to a prescription is a medical statement, and so is
«nothing follows from this one». They are read from a curated file, and an entry
without a named source is dropped and counted rather than shown.

The answer carries a judgement about the decision, not only genotypes — and all
three of its forms are statements about this build, which can be checked, rather
than advice, which cannot.

And where nobody has written a list, the answer says so. That line is the point of
the whole mechanism: a silence there is completed by whoever is answering the
reader, out of knowledge that never passed through this build.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion.engine import decision as D
from scholion.i18n import en, ru

PAGE = (Path(support.__file__).resolve().parent.parent
        / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")

ROW = {"gene": "CYP2C19", "computable": True, "phenotype": "PM", "label": "—",
       "actionable": True, "cpic_level": "A", "coverage": {"state": "fine"}}


def _sec(genes=(), asked=True, reason=None, snapshot="2026-08-19"):
    return {"genes": list(genes),
            "cpic": {"asked": asked, "reason": reason, "snapshot": snapshot}}


class TestTheJudgementIsAboutThisBuildAndNotAboutTheReader(unittest.TestCase):

    def test_a_rule_that_selects_a_non_neutral_row(self):
        v = D.classify(_sec([ROW]))["verdict"]
        self.assertEqual("rule_fires", v["kind"])
        self.assertIn("CYP2C19", v["genes"])

    def test_a_rule_that_selects_the_neutral_row_is_not_clearance(self):
        v = D.classify(_sec([{**ROW, "phenotype": "NM"}]))["verdict"]
        self.assertEqual("rule_silent", v["kind"])
        for lang in (en, ru):
            with self.subTest(lang=lang.__name__):
                self.assertIn("{genes}", lang.MESSAGES["decision.rule_silent"])

    def test_no_rule_names_why_there_is_none(self):
        self.assertEqual("no_pair", D.classify(_sec([]))["verdict"]["why"])
        self.assertEqual("not_asked",
                         D.classify(_sec([], asked=False, reason="offline"))["verdict"]["why"])

    def test_a_gene_that_could_not_be_phenotyped_carries_no_rule(self):
        """It is held and unreadable, which is the recognised-pair state — not
        the state of a gene whose table decided something."""
        c = D.classify(_sec([{**ROW, "computable": False}]))
        self.assertEqual("no_rule", c["verdict"]["kind"])
        self.assertTrue(c["blocks"]["pair"])
        self.assertFalse(c["blocks"]["guideline"])

    def test_every_verdict_has_a_sentence_in_both_languages(self):
        for kind, extra in (("rule_fires", {"genes": ["A"]}), ("rule_silent", {"genes": ["A"]}),
                            ("no_rule", {"why": "no_pair"})):
            with self.subTest(kind=kind):
                line = D.verdict_line({"kind": kind, **extra})
                self.assertTrue(line)
                self.assertNotIn("⟦", line)


class TestTheCuratedListIsAppliedAndNeverInvented(unittest.TestCase):

    BOOK = {"drugs": {"урсодиол": {"source": "a clinician, 12.09.2026", "genes": {
        "UGT1A1": {"kind": "mechanism", "text": {"en": "handles it", "ru": "участвует"},
                   "source": "named"},
        "NOSOURCE": {"kind": "asked_about", "text": {"en": "x", "ru": "x"}},
        "NOTEXT": {"kind": "mechanism", "source": "named"},
        "BADKIND": {"kind": "invented", "text": {"en": "x"}, "source": "named"}}}}}

    def _with_book(self):
        return mock.patch.object(D, "_context", lambda: self.BOOK)

    def test_an_entry_with_a_sentence_is_applied(self):
        with self._with_book():
            got = D.curated_genes("урсодиол")
        self.assertTrue(got["asked"])
        # NOSOURCE has no source of its own and the LIST has one, which stands
        # in for it: the list is where a clinician says where her genes came
        # from, and requiring the citation twice would be pedantry, not a gate.
        self.assertEqual({"UGT1A1", "NOSOURCE"}, {g["gene"] for g in got["genes"]})

    def test_an_entry_with_no_sentence_waits_rather_than_disappearing(self):
        with self._with_book():
            got = D.curated_genes("урсодиол")
        self.assertEqual(["NOTEXT"], [g["gene"] for g in got["pending"]])

    def test_only_an_invented_class_is_dropped_and_it_is_counted(self):
        with self._with_book():
            got = D.curated_genes("урсодиол")
        self.assertEqual(1, got["refused"],
                         "an entry dropped in silence looks like one never written")

    def test_an_invented_class_is_not_accepted(self):
        with self._with_book():
            self.assertNotIn("BADKIND", [g["gene"] for g in D.curated_genes("урсодиол")["genes"]])

    def test_a_prescription_with_no_list_says_so_rather_than_nothing(self):
        got = D.curated_genes("что-нибудь-без-списка")
        self.assertFalse(got["asked"])
        self.assertEqual([], got["genes"])

    def test_the_shipped_file_holds_a_shape_and_no_medicine(self):
        """One entry ships: the genes a clinician named in her own session, with
        every medical field empty. If a sentence or a class is ever filled in
        here by anyone but a clinician, this is where it shows."""
        book = D._context()
        drugs = book.get("drugs") or {}
        self.assertEqual(1, len(drugs), "more than the sample entry is shipping")
        for name, entry in drugs.items():
            with self.subTest(drug=name):
                self.assertTrue(entry.get("source"))
                for gene, spec in (entry.get("genes") or {}).items():
                    self.assertEqual({}, spec, f"{gene} carries a field we wrote")
        self.assertIn("why_empty", book.get("_meta") or {})


class TestANamedGeneWithoutASentenceIsNotADroppedEntry(unittest.TestCase):
    """The clinician's answer to «will you write the sentences» was a conditional
    yes: show me a sample first. That makes an unwritten row the most useful row
    on the screen — it says somebody put this gene on the list and that what
    follows from it is still to be written. Dropping it with the unattributed
    ones hid a request addressed to a person.

    The CLASS of link is hers as well. Filing a gene she named under «handles
    this substance, no dosing rule follows» would be this program deciding a
    medical question on her behalf, one field over from the sentence the gate
    already guards."""

    BOOK = {"drugs": {"x": {"source": "named by a clinician", "genes": {
        "WRITTEN": {"kind": "mechanism", "text": {"en": "t", "ru": "t"}, "source": "s"},
        "NAMEDONLY": {},
        "CLASSONLY": {"kind": "asked_about"}}}}}

    def _got(self):
        with mock.patch.object(D, "_context", lambda: self.BOOK):
            return D.curated_genes("x")

    def test_a_written_row_is_applied(self):
        self.assertEqual(["WRITTEN"], [g["gene"] for g in self._got()["genes"]])

    def test_a_named_row_is_kept_as_pending_rather_than_dropped(self):
        self.assertEqual({"NAMEDONLY", "CLASSONLY"},
                         {g["gene"] for g in self._got()["pending"]})

    def test_the_list_source_stands_in_for_a_row_that_has_none(self):
        row = [g for g in self._got()["pending"] if g["gene"] == "NAMEDONLY"][0]
        self.assertEqual("named by a clinician", row["source"])

    def test_without_a_list_source_an_unattributed_row_is_refused(self):
        book = {"drugs": {"x": {"genes": {"NOSOURCE": {"kind": "mechanism",
                                                       "text": {"en": "t"}}}}}}
        with mock.patch.object(D, "_context", lambda: book):
            got = D.curated_genes("x")
        self.assertEqual(1, got["refused"])
        self.assertEqual([], got["genes"] + got["pending"])

    def test_an_unclassified_gene_is_not_filed_under_a_class_by_the_program(self):
        with mock.patch.object(D, "_context", lambda: self.BOOK):
            c = D.classify({"genes": [], "cpic": {"asked": True}}, "x")
        self.assertIn("NAMEDONLY", {r["gene"] for r in c["named"]})
        for kind, rows in c["blocks"].items():
            with self.subTest(kind=kind):
                self.assertNotIn("NAMEDONLY", {r.get("gene") for r in rows})

    def test_the_unwritten_row_says_so_on_the_screen_with_its_origin(self):
        with mock.patch.object(D, "_context", lambda: self.BOOK):
            c = D.classify({"genes": [], "cpic": {"asked": True}}, "x")
        lines = fmt._context_lines(c)
        self.assertTrue(any("NAMEDONLY" in l for l in lines))
        self.assertTrue(any("named by a clinician" in l for l in lines))

    def test_the_shipped_sample_is_a_list_whose_source_is_who_named_it(self):
        """The one entry that ships is the five genes the clinician named in her
        own session, with no sentence and no class: the sample is the shape, and
        every medical field in it is empty."""
        book = D._context()
        entry = (book.get("drugs") or {}).get("урсодезоксихолевая кислота")
        self.assertIsNotNone(entry, "the sample entry is gone")
        self.assertTrue(entry.get("source"))
        for gene, spec in entry["genes"].items():
            with self.subTest(gene=gene):
                self.assertEqual({}, spec, "a medical field was filled in by us")

    def test_the_form_example_is_not_loaded_by_the_engine(self):
        """`_example` shows a filled row — quoted from a file this build already
        carries — and must never reach an answer as data."""
        book = D._context()
        self.assertIn("_example", book)
        self.assertNotIn("метотрексат", book.get("drugs") or {})
        with mock.patch.object(D, "_context", lambda: book):
            self.assertFalse(D.curated_genes("метотрексат")["asked"])


class TestTheAnswerShowsTheClassesThatCarryNoRule(unittest.TestCase):

    def test_the_named_absence_of_a_list_is_printed(self):
        out = fmt.prescription_check(
            {"status": "ok", "drug": "x", "overall": "low", "genome": _sec([ROW]),
             "genetic_context": D.classify(_sec([ROW]), "x")})
        self.assertIn(en.MESSAGES["decision.no_context_list"].split(" — ")[0][:30], out
                      + en.MESSAGES["decision.no_context_list"])
        self.assertNotIn("⟦", out)

    def test_a_curated_row_is_printed_with_its_source(self):
        ctx = {"blocks": {k: [] for k in D.KINDS}, "curated": {"asked": True, "refused": 0},
               "verdict": {"kind": "no_rule", "why": "no_pair"}}
        ctx["blocks"]["mechanism"] = [{"gene": "VDR", "kind": "mechanism",
                                       "text": "handles it", "source": "a citation"}]
        lines = fmt._context_lines(ctx)
        self.assertTrue(any("VDR" in l for l in lines))
        self.assertTrue(any("a citation" in l for l in lines),
                        "a sentence about a gene was printed without its origin")

    def test_dropped_entries_are_reported_as_a_number(self):
        ctx = {"blocks": {k: [] for k in D.KINDS},
               "curated": {"asked": True, "refused": 2}, "verdict": {"kind": "no_rule"}}
        self.assertTrue(any("2" in l for l in fmt._context_lines(ctx)))

    def test_the_verdict_stands_above_the_sections(self):
        out = fmt.prescription_check(
            {"status": "ok", "drug": "x", "overall": "low", "genome": _sec([ROW]),
             "genetic_context": D.classify(_sec([ROW]), "x")})
        head = out.split("**🧬")[0]
        self.assertIn("CYP2C19", head, "the judgement was below the sections that make it")


class TestEveryGeneGetsExactlyOneAnswerLine(unittest.TestCase):
    """The coverage note qualifies whichever answer was given; it does not choose
    between them. Placed between the `if` and its `elif` it did both: a gene that
    could be phenotyped and had nothing to say about coverage printed twice, and a
    gene that could not be phenotyped but did printed the note instead of its
    answer."""

    CASES = [
        {"gene": "CYP2C19", "computable": True, "phenotype": "PM", "label": "L",
         "actionable": True, "cpic_level": "A"},
        {"gene": "CYP2D6", "computable": False, "needs_full_diplotype": True,
         "label": "L2", "cpic_level": "A"},
        {"gene": "SLCO1B1", "computable": False, "label": "L3", "cpic_level": "A",
         "markers": [{"rsid": "rs1", "genotype": "TC"}]},
    ]
    COVERAGES = [None, {"state": "fine", "pct_20x": 80.0},
                 {"state": "low", "pct_20x": 8.0, "median_pct_20x": 79.8},
                 {"state": "not_measured"}]

    def test_one_line_per_gene_in_every_branch_and_every_coverage_state(self):
        for case in self.CASES:
            for cov in self.COVERAGES:
                with self.subTest(gene=case["gene"], coverage=(cov or {}).get("state")):
                    ge = dict(case)
                    if cov is not None:
                        ge["coverage"] = cov
                    out = fmt.prescription_check(
                        {"status": "ok", "drug": "x", "overall": "low",
                         "genome": _sec([ge])})
                    rows = [l for l in out.split("\n") if l.startswith("- **")]
                    self.assertEqual(1, len(rows), rows)
                    self.assertIn(ge["gene"], rows[0])


class TestThePageSaysItInTheEnginesWords(unittest.TestCase):

    def test_the_page_has_the_verdict_and_the_classes(self):
        for name in ("function verdictLine(", "function contextHtml(", "genetic_context"):
            with self.subTest(name=name):
                self.assertIn(name, PAGE)

    def test_the_page_asks_for_the_same_phrases(self):
        for key in ("decision.rule_fires", "decision.rule_silent", "decision.no_rule",
                    "decision.no_context_list", "decision.source"):
            with self.subTest(key=key):
                self.assertIn(key, PAGE)
                self.assertIn(key, en.MESSAGES)
                self.assertIn(key, ru.MESSAGES)


if __name__ == "__main__":
    unittest.main()
