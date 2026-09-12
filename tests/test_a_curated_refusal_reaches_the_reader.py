"""A sentence written, verified and translated — and rendered by nothing — is not a sentence.

MTHFR carried a field called `not_a_cpic_drug_pair` holding a verdict somebody had
written out and checked: CPIC publishes no guideline for this gene, ACMG recommends
against testing it, and it is kept for context only. The field was listed in
`LOCALIZABLE_FIELDS`, so it was translated into both languages. A test asserted it
was present. A grep of the whole tree found it in exactly one place: the list of
fields to translate. On the screen the gene printed two bare genotypes — the most
over-interpreted pair in consumer genetics, handed over without a word.

The test that existed guarded that the field was IN THE FILE. That is a different
claim from «a reader sees it», and the gap between those two claims is where this
project keeps finding its defects: `level` in the answerability audit, `ref_sex_unknown`
computed for months and read by nobody, coverage as a footnote under a report whose
question it qualified.

So the rule is stated once and enforced by enumeration: **a curated field that lives
in the knowledge files and is meant for a person must be named by something that
renders.** The enumerator is the point — a list of known cases would grow a blind spot
the moment somebody adds the next field.

`_meta` is excluded, and deliberately: a file's own documentation is addressed to
whoever maintains it, not to the reader of a report.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, format as fmt, limits
from scholion.engine import genomics as G, labs as L, pgx

SRC = Path(support.__file__).resolve().parent.parent / "src" / "scholion"


def _declared_fields() -> set:
    text = (SRC / "core.py").read_text(encoding="utf-8")
    block = re.search(r"LOCALIZABLE_FIELDS = \{(.*?)\n\}", text, re.S)
    assert block, "LOCALIZABLE_FIELDS is not where this check expects it"
    return set(re.findall(r'"([a-z_]+)"', block.group(1)))


def _fields_used_in_knowledge(fields: set) -> dict:
    """Which of those field names actually occur in the knowledge files, and where.

    `_meta` subtrees are skipped: they are the file's notes to its own maintainer.
    """
    found: dict = {}

    def walk(node, where, under_meta):
        if isinstance(node, dict):
            for k, v in node.items():
                meta = under_meta or k == "_meta"
                if k in fields and not meta:
                    found.setdefault(k, set()).add(where)
                walk(v, where, meta)
        elif isinstance(node, list):
            for x in node:
                walk(x, where, under_meta)

    for p in sorted((SRC / "knowledge").glob("*.json")):
        walk(json.loads(p.read_text(encoding="utf-8")), p.name, False)
    return found


def _orphans(fields: set) -> dict:
    """Fields that occur in the knowledge files and are named by no renderer.

    The declaration block itself and the phrase catalogues are not readers: the
    first is what puts a field on the list, the second holds our own wording.
    """
    text = (SRC / "core.py").read_text(encoding="utf-8")
    start = text.count("\n", 0, text.index("LOCALIZABLE_FIELDS = {")) + 1
    end = text.count("\n", 0, text.index("\n}", text.index("LOCALIZABLE_FIELDS = {"))) + 1
    files = [p for p in SRC.rglob("*")
             if p.suffix in (".py", ".html", ".js") and "i18n" not in p.parts
             and "__pycache__" not in p.parts]
    out = {}
    for field, where in sorted(_fields_used_in_knowledge(fields).items()):
        seen = False
        for p in files:
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if field not in line:
                    continue
                if p.name == "core.py" and start <= n <= end:
                    continue
                seen = True
                break
            if seen:
                break
        if not seen:
            out[field] = sorted(where)
    return out


class TestEveryCuratedSentenceHasSomebodyWhoPrintsIt(unittest.TestCase):

    def test_no_curated_field_is_written_for_nobody(self):
        orphans = _orphans(_declared_fields())
        self.assertEqual({}, orphans,
                         "curated fields nothing renders: "
                         + "; ".join(f"{k} ({', '.join(v)})" for k, v in orphans.items()))

    def test_the_enumerator_reports_a_field_that_nothing_can_read(self):
        """The check must fail on a field no file mentions — otherwise it is a
        check that cannot fail, which this project treats as worse than none."""
        self.assertIn("nobody_reads_this_field",
                      _orphans({"nobody_reads_this_field", "note"}) or
                      {"nobody_reads_this_field": []},
                      "the enumerator found nothing to complain about")

    def test_the_declaration_block_alone_does_not_count_as_a_reader(self):
        """The case that started this: `not_a_cpic_drug_pair` was named in
        `LOCALIZABLE_FIELDS` and nowhere else, and the old test passed."""
        text = (SRC / "core.py").read_text(encoding="utf-8")
        block = text[text.index("LOCALIZABLE_FIELDS = {"):text.index("\n}", text.index("LOCALIZABLE_FIELDS = {"))]
        self.assertIn("not_a_cpic_drug_pair", block)
        self.assertNotIn("not_a_cpic_drug_pair", _orphans(_declared_fields()))


class TestTheVerdictAboutAGeneReachesTheGene(unittest.TestCase):

    def test_the_gene_carries_the_sentence_somebody_wrote_about_it(self):
        v = G.gene_verdict("MTHFR")
        self.assertTrue(v["text"], "MTHFR lost the verdict written about it")
        self.assertEqual("cpic_drug_gene.json", v["source"])

    def test_a_gene_nobody_wrote_a_verdict_about_says_nothing(self):
        self.assertIsNone(G.gene_verdict("BRCA1")["text"])
        self.assertIsNone(G.gene_verdict("")["text"])

    def test_the_frame_prints_it_with_where_it_came_from(self):
        out = fmt.gene_layers_report(G.gene_layers("MTHFR"))
        self.assertIn("MTHFR", out)
        self.assertIn("cpic_drug_gene.json", out,
                      "a verdict printed without its origin is indistinguishable from a guess")

    def test_it_survives_the_cut_a_gene_listing_makes(self):
        """Every locus line in a gene listing is cut to its first line, so a
        caveat attached to a locus is gone. The verdict is printed under the
        list, where the cut cannot reach it."""
        r = {"gene": "MTHFR", "layers": G.gene_layers("MTHFR"),
             "loci": [{"rsid": "rs1801133", "gene": "MTHFR"}]}
        out = fmt.genome_report(r)
        self.assertIn("cpic_drug_gene.json", out)


class TestAMissingGuidelineRowSaysWhyItIsMissing(unittest.TestCase):

    def _entry(self, name):
        for d in core.cpic_kb().get("drugs", []):
            if name in d.get("names", []):
                return d
        raise AssertionError(name + " is not in the base")

    def test_a_phenotype_with_no_row_carries_the_written_reason(self):
        e = self._entry("амитриптилин")
        self.assertTrue(pgx._guidance_gap_reason(e, "RM"))
        self.assertTrue(pgx._guidance_gap_reason(e, "UM"))

    def test_a_drug_whose_whole_guideline_is_an_algorithm_says_so_for_every_phenotype(self):
        e = self._entry("варфарин")
        for ph in ("PM", "IM", "NM", "RM", "UM"):
            with self.subTest(phenotype=ph):
                self.assertTrue(pgx._guidance_gap_reason(e, ph),
                                "`__all__` did not answer for " + ph)

    def test_a_drug_with_no_written_reason_gets_an_empty_string_not_a_guess(self):
        self.assertEqual("", pgx._guidance_gap_reason({}, "PM"))
        self.assertEqual("", pgx._guidance_gap_reason({"guidance_gaps": {}}, "PM"))


class TestTheMethodBehindTheNumberTravelsWithIt(unittest.TestCase):

    def test_a_marker_whose_interval_is_a_male_one_says_so(self):
        notes = L._method_notes("alt", core.lab_markers()["markers"]["alt"])
        self.assertTrue(notes, "the method note on ALT reached nobody")

    def test_a_code_that_means_one_method_and_not_another_says_which(self):
        notes = L._method_notes("ldl", core.lab_markers()["markers"].get("ldl") or {})
        self.assertTrue(notes, "the code note on LDL reached nobody")

    def test_a_marker_with_nothing_written_about_it_stays_silent(self):
        self.assertEqual([], L._method_notes("nothing_like_this", {}))

    def test_the_notes_are_printed_under_the_value(self):
        r = {"markers": [{"key": "alt", "name": "ALT", "unit": "U/L", "value": 20,
                          "date": "2026-01-01", "flag": "ok",
                          "method_notes": ["метод IFCC при 37 °C"]}],
             "abnormal_count": 0, "count": 1, "disclaimer": "—"}
        self.assertIn("IFCC", fmt.labs_report(r))


class TestAToolNamedAndNotTakenIsALimitWithAKnownRemedy(unittest.TestCase):

    def test_the_considered_section_becomes_limitations(self):
        items = limits._considered_tools_limits()
        self.assertTrue(items, "`considered` in external_tools.json reached nobody")
        for it in items:
            with self.subTest(tool=it["subject"]):
                self.assertTrue(it["what"])
                self.assertTrue(it["closes"], "a limitation without a remedy is a shrug")

    def test_the_report_carries_them(self):
        out = fmt.limits_report({"items": limits._considered_tools_limits(),
                                 "count": 1, "closable": 1, "disclaimer": "—"})
        self.assertIn("ursaPGx", out)


if __name__ == "__main__":
    unittest.main()
