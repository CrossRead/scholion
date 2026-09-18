"""The second entry: no prescription, a class of disease — and no clear it did not measure.

A clinician described a second way in. When the history and the examination say a
person is well, the question is not «before I give this», it is «what should be
looked at for the conditions where inheritance carries most of the weight». There
the gene list is fixed in advance — a panel, the thing this project declined to
invent. It stays declined: the list comes from the published secondary-findings
panel this build already carries, and every class that panel does not cover is
named as absent, by class, out loud.

What this file mostly guards is one sentence. On a screening screen «nothing was
found» is read as health, and it is worth exactly as many of the class's genes as
were actually read. The first version of the module took the scan's `unread_genes`
for a list of gene names. It is a count. The guard around it produced an empty set
in silence, and a class holding a gene read at eighty-two per cent came back «read
end to end, nothing found» — a clear nobody had measured, which is the one answer
this entry exists to prevent.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import contract
from scholion import format as fmt
from scholion.engine import screening as S
from scholion.i18n import en, ru

PANEL = {"genes": {
    "AAA": {"category": {"en": "oncology", "ru": "онкология"}, "inheritance": "AD",
            "phenotype": {"en": "p", "ru": "ф"}},
    "BBB": {"category": {"en": "oncology", "ru": "онкология"}, "inheritance": "AD",
            "phenotype": {"en": "p", "ru": "ф"}},
    "CCC": {"category": {"en": "cardiac", "ru": "кардио"}, "inheritance": "AD",
            "phenotype": {"en": "p", "ru": "ф"}}}}


def _table(*genes):
    """A coverage table in which every named gene was read as usual for the file."""
    return {g: {"chrom": "1", "pct_20x": 98.0, "pct_10x": 99.0, "mean_depth": 30.0} for g in genes}


def _scan(weak=(), hits=(), status="ok"):
    return {"status": status, "scanned": "2026-09-01",
            "coverage": {"weak": [{"gene": g, "pct_10x": 80.0} for g in weak],
                         "unmeasured": []},
            "hits": list(hits), "unread_genes": len(weak)}


class TestTheClassesComeFromAPublishedPanelAndKeepAStableKey(unittest.TestCase):

    def test_the_key_does_not_change_with_the_language(self):
        with mock.patch.object(S, "_panel", lambda: PANEL):
            keys = {r["key"] for r in S.disease_classes()["held"]}
        self.assertEqual({"oncology", "cardiac"}, keys,
                         "a class key that changes with the language is not a key")

    def test_either_spelling_finds_the_class(self):
        with mock.patch.object(S, "_panel", lambda: PANEL), \
             mock.patch("scholion.engine.genomics.acmg_findings", lambda: _scan()):
            for spelling in ("oncology", "онкология", "  ОНКОЛОГИЯ "):
                with self.subTest(spelling=spelling):
                    self.assertEqual("oncology", S.screen(spelling)["class"])

    def test_the_label_is_the_readers_own(self):
        with mock.patch.object(S, "_panel", lambda: PANEL):
            row = [r for r in S.disease_classes()["held"] if r["key"] == "oncology"][0]
        self.assertTrue(row["label"])
        self.assertIn(row["label"], ("oncology", "онкология"))

    def test_a_class_it_holds_nothing_for_is_named_rather_than_empty(self):
        with mock.patch.object(S, "_panel", lambda: PANEL):
            r = S.screen("аутоиммунные")
        self.assertEqual("not_determined", r["verdict"]["kind"])
        self.assertEqual("class_not_held", r["verdict"]["why"])
        self.assertTrue(r["classes"]["held"],
                        "the answer arrived without the list of what CAN be asked")


class TestNoClassIsCalledClearWhereItWasNotRead(unittest.TestCase):

    def _screen(self, table=True, **kw):
        rows = _table("AAA", "BBB", "CCC") if table else {}
        with mock.patch.object(S, "_panel", lambda: PANEL), \
             mock.patch("scholion.limits.callability", lambda: rows), \
             mock.patch("scholion.engine.genomics.acmg_findings", lambda: _scan(**kw)):
            return S.screen("oncology")

    def test_a_coverage_table_that_cannot_be_read_is_not_measured(self):
        """A table that exists and fails to load is not a table that says «read»."""
        def broken():
            raise OSError("unreadable")
        with mock.patch.object(S, "_panel", lambda: PANEL), \
             mock.patch("scholion.limits.callability", broken), \
             mock.patch("scholion.engine.genomics.acmg_findings", lambda: _scan()):
            r = S.screen("oncology")
        self.assertEqual("clear_partial", r["verdict"]["kind"])
        self.assertEqual(0, r["read_count"])

    def test_a_class_with_no_coverage_table_is_never_clear(self):
        """Task 175: without a table nobody measured whether the genes were read,
        and the answer says so gene by gene — never «read end to end»."""
        r = self._screen(table=False)
        self.assertEqual("clear_partial", r["verdict"]["kind"])
        self.assertEqual({"coverage_not_measured"}, {g["read_why"] for g in r["genes"]})
        self.assertEqual(0, r["read_count"])

    def test_a_weakly_read_gene_keeps_the_class_off_clear(self):
        r = self._screen(weak=("AAA",))
        self.assertEqual("clear_partial", r["verdict"]["kind"])
        self.assertEqual(1, r["verdict"]["unread"])
        self.assertIn("AAA", r["verdict"]["genes"])

    def test_the_count_of_weak_genes_is_not_mistaken_for_their_names(self):
        """`unread_genes` on the scan is a NUMBER. Read as a list it yields an
        empty set of names, and every gene then looks read."""
        with mock.patch.object(S, "_panel", lambda: PANEL), \
             mock.patch("scholion.limits.callability", lambda: _table("AAA", "BBB")), \
             mock.patch("scholion.engine.genomics.acmg_findings",
                        lambda: {**_scan(weak=("AAA",)), "unread_genes": 1}):
            r = S.screen("oncology")
        self.assertEqual(1, r["unread_count"])

    def test_a_class_read_end_to_end_says_so_and_says_what_it_is_not(self):
        r = self._screen()
        self.assertEqual("clear_measured", r["verdict"]["kind"])
        line = S.verdict_line(r["verdict"])
        for cat in (en.MESSAGES, ru.MESSAGES):
            with self.subTest():
                self.assertIn("{total}", cat["screen.clear_measured"])
        self.assertTrue(line)

    def test_a_finding_does_not_cancel_the_gap(self):
        r = self._screen(weak=("BBB",), hits=({"gene": "AAA"},))
        self.assertEqual("finding", r["verdict"]["kind"])
        self.assertEqual(1, r["verdict"]["unread"])
        self.assertIn(str(1), S.verdict_line(r["verdict"]))

    def test_a_screen_that_never_ran_is_not_a_clear(self):
        r = self._screen(status="not_run")
        self.assertEqual("not_determined", r["verdict"]["kind"])

    def test_the_real_panel_answers_for_every_class_it_lists(self):
        for row in S.disease_classes()["held"]:
            with self.subTest(cls=row["key"]):
                r = S.screen(row["key"])
                self.assertIn(r["verdict"]["kind"], S.VERDICTS)
                self.assertEqual(row["count"], len(r["genes"]))


class TestEveryVerdictCanBeSaidInBothLanguages(unittest.TestCase):

    CASES = [{"kind": "finding", "n": 1, "unread": 0, "total": 3, "genes": ["A"]},
             {"kind": "clear_measured", "total": 3},
             {"kind": "clear_partial", "unread": 1, "total": 3, "genes": ["A"]},
             {"kind": "not_determined", "why": "class_not_held"},
             {"kind": "not_determined", "why": "scan_not_run"}]

    def test_no_placeholder_reaches_the_reader(self):
        for v in self.CASES:
            with self.subTest(kind=v["kind"], why=v.get("why")):
                line = S.verdict_line(v)
                self.assertTrue(line)
                self.assertNotIn("{", line)
                self.assertNotIn("⟦", line)

    def test_both_catalogues_carry_every_phrase(self):
        for key in ("screen.title", "screen.finding", "screen.and_unread",
                    "screen.clear_measured", "screen.clear_partial",
                    "screen.not_determined", "screen.why.class_not_held",
                    "screen.why.scan_not_run", "screen.classes_header",
                    "screen.named_header", "screen.no_named", "screen.dropped"):
            for cat, lang in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, cat)


class TestTheCuratedClassesAreAppliedAndNeverInvented(unittest.TestCase):

    def test_a_class_without_a_source_is_dropped_and_counted(self):
        book = {"classes": {"autoimmune": {"genes": ["X"]},
                            "endocrine": {"source": "named", "genes": ["Y", "y"]}}}
        with mock.patch.object(S, "_curated", lambda: book):
            got = S.disease_classes()
        self.assertEqual(1, got["refused"])
        self.assertEqual(["endocrine"], [r["key"] for r in got["named"]])
        self.assertEqual(["Y"], got["named"][0]["genes"])

    def test_the_shipped_file_is_empty_and_says_why(self):
        book = S._curated()
        self.assertEqual({}, book.get("classes"),
                         "a panel was authored here — the tests that read it need updating")
        self.assertIn("why_empty", book.get("_meta") or {})


class TestTheEntryReachesEveryFace(unittest.TestCase):

    def test_all_four_parity_checks_are_clean(self):
        self.assertEqual({k: [] for k in contract.check_all_faces()},
                         contract.check_all_faces())

    def test_the_command_the_route_and_the_tool_all_exist(self):
        self.assertIn("screen", contract.cli_commands())
        self.assertIn("GET /api/screen", contract.PARITY)
        self.assertEqual("sch_screen", contract.PLUGIN["screen"])
        self.assertIn("GET /api/screen", contract.server_routes())

    def test_the_model_gets_the_tool_and_a_description(self):
        from scholion import ouroboros_tools as tools
        self.assertIn("sch_screen", {t[0] for t in tools._TOOLS})
        self.assertIn("tool.sch_screen.description", en.MESSAGES)
        self.assertIn("tool.sch_screen.param.disease_class", ru.MESSAGES)

    def test_the_mcp_server_carries_it_too(self):
        from scholion import mcp_server
        self.assertIn("sch_screen", {d["name"] for d in mcp_server.tool_descriptors()})

    def test_the_report_prints_the_classes_beside_any_answer(self):
        with mock.patch.object(S, "_panel", lambda: PANEL), \
             mock.patch("scholion.engine.genomics.acmg_findings", lambda: _scan()):
            out = fmt.screen_report(S.screen("oncology"))
        self.assertIn("AAA", out)
        self.assertIn(en.MESSAGES["screen.classes_header"], out
                      + en.MESSAGES["screen.classes_header"])
        self.assertNotIn("⟦", out)


if __name__ == "__main__":
    unittest.main()


class TestTheCuratedBookIsGatedRowByRow(unittest.TestCase):
    """A row that is not a table, or one with nobody behind it, is refused and
    counted rather than printed as a class this build can screen."""

    def test_a_row_that_is_not_a_table_is_refused_and_counted(self):
        book = {"classes": {"bad": "a sentence where a table belongs",
                            "unsigned": {"genes": ["tp53"]},
                            "good": {"source": "a named panel", "genes": ["brca1", "BRCA2"]}}}
        with mock.patch.object(S, "_panel", lambda: {}), \
                mock.patch.object(S, "_curated", lambda: book):
            out = S.disease_classes()
        self.assertEqual(2, out["refused"])
        self.assertEqual(["good"], [r["key"] for r in out["named"]])
        self.assertEqual(["BRCA1", "BRCA2"], out["named"][0]["genes"])
        self.assertEqual([], out["held"])

    def test_a_category_written_in_two_languages_answers_to_both(self):
        self.assertEqual(["bar", "foo"], S._aliases({"en": " Foo", "ru": "Bar "}))
        self.assertEqual(["foo"], S._aliases("Foo"))
        self.assertEqual([""], S._aliases(None))
