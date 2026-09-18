"""A printed amino acid ratio is read as a ratio, and checked against its components.

Two defects, one line of a form. An amino acid panel prints ratios beside the
single values — «Phe:Tyr», «AABA:Leu», «Glu:Gln» — and none of them had a key,
so the value was lost (task 68). Worse, a ratio printed with full names,
«Фенилаланин (Phe)/Тирозин (Tyr)  1,13», was read as TYROSINE 1.13: a value
forty times below its range, off a line that holds no tyrosine at all.

Now a name that stands against a ratio sign does not take the line; ten ratios
of the adult panel have keys and a formula (task 200, stage C), and the printed
value is compared with the one its components give. A colon that closes a label
(«Глюкоза: 5,4») is not a ratio sign, and the parsing baseline is unchanged.

The forms here are synthetic: no real form of this panel was available.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, ingest_labs, provenance
from scholion.i18n import en, ru

FORM = """СИНТЕТИЧЕСКАЯ ФИКСТУРА — вымышленный бланк.
Дата взятия биоматериала: 14.03.2024 08:20
Фенилаланин (Phe)                        62          25 - 80            мкмоль/л
Фенилаланин (Phe)/Тирозин (Tyr)          1,13
Глутамат (Glu) : Глутамин (Gln)          0,09
Тирозин (Tyr)                            55          35 - 110           мкмоль/л
Глутамин (Gln)                          540         390 - 650           мкмоль/л
Phe:Tyr                                  1,13
AABA:Leu                                 0,17
Glu:Gln                                  0,09
"""

RATIOS = ("aa_ratio_phe_tyr", "aa_ratio_gly_ser", "aa_fischer_ratio", "aa_ratio_gln_glu",
          "aa_ratio_glu_gln", "aa_ratio_met_hcy", "aa_ratio_aaba_leu", "aa_ratio_kyn_trp",
          "urea_creatinine_ratio")


def parse(text):
    return ingest_labs.parse_report(text, core.lab_markers()["markers"], source="synthetic")[1]


class TestTheLineIsARatio(unittest.TestCase):

    def test_the_components_keep_their_own_values(self):
        r = parse(FORM)
        self.assertEqual(55.0, r["aa_tyrosine"]["value"], "a ratio line was read as tyrosine")
        self.assertEqual(540.0, r["aa_glutamine"]["value"], "a ratio line was read as glutamine")
        self.assertEqual(62.0, r["aa_phenylalanine"]["value"])

    def test_the_three_printed_ratios_of_task_68_are_read(self):
        r = parse(FORM)
        self.assertEqual(1.13, r["aa_ratio_phe_tyr"]["value"])
        self.assertEqual(0.17, r["aa_ratio_aaba_leu"]["value"])
        self.assertEqual(0.09, r["aa_ratio_glu_gln"]["value"])

    def test_a_colon_closing_a_label_is_not_a_ratio(self):
        r = parse("Дата взятия биоматериала: 14.03.2024 08:20\nГлюкоза: 5,4   3,9 - 6,1   ммоль/л\n")
        self.assertEqual(5.4, r["glucose"]["value"])

    def test_the_sign_rule_on_its_own(self):
        cases = [("фенилаланин (phe)/тирозин (tyr) 1,13", "тирозин (tyr", True),
                 ("глутамат (glu) : глутамин (gln) 0,09", "глутамин (gln", True),
                 ("aaba:leu 0,17", "leu", True),
                 ("глюкоза: 5,4 ммоль/л", "глюкоза", False),
                 ("glucose: 95 mg/dl", "glucose", False),
                 ("результат: глюкоза 5,4", "глюкоза", False),
                 ("гемоглобин 140 г/л", "гемоглобин", False),
                 ("витамин d (d2/d3) 40", "витамин d", False)]
        for line, name, want in cases:
            with self.subTest(line=line, name=name):
                s = line.index(name)
                self.assertIs(want, ingest_labs._against_ratio_sign(line, s, s + len(name)))


class TestEveryRatioIsDeclaredAndComputed(unittest.TestCase):

    def test_each_has_a_key_a_formula_and_a_note_in_both_languages(self):
        import json
        base = core.lab_markers()["markers"]
        meta = json.loads(core.knowledge_path("lab_test_meta.json").read_text(encoding="utf-8"))["tests"]
        for key in RATIOS:
            with self.subTest(ratio=key):
                self.assertIn(key, base)
                self.assertIn(key, provenance.DERIVED)
                self.assertTrue(meta[key]["computed"])
                self.assertEqual(sorted(provenance.DERIVED[key]["needs"]), sorted(meta[key]["requires"]))
                self.assertTrue(meta[key]["note"]["en"] and meta[key]["note"]["ru"])
                expr = provenance.DERIVED[key]["expr"]
                self.assertIn(expr, en.MESSAGES)
                self.assertIn(expr, ru.MESSAGES)

    def test_a_ratio_without_a_published_range_carries_none(self):
        """No range was written from memory: a ratio is shown as a value until a
        source gives it one."""
        base = core.lab_markers()["markers"]
        for key in RATIOS:
            with self.subTest(ratio=key):
                self.assertNotIn("ref_low", base[key])
                self.assertNotIn("ref_high", base[key])

    def test_the_formulas(self):
        d = provenance.DERIVED
        self.assertAlmostEqual(62 / 55, d["aa_ratio_phe_tyr"]["fn"]({"aa_phenylalanine": 62, "aa_tyrosine": 55}))
        v = {"aa_leucine": 120, "aa_isoleucine": 60, "valine": 220, "aa_phenylalanine": 60, "aa_tyrosine": 60}
        self.assertAlmostEqual(400 / 120, d["aa_fischer_ratio"]["fn"](v))
        self.assertAlmostEqual(5.0 / 0.080, d["urea_creatinine_ratio"]["fn"]({"urea": 5.0, "creatinine": 80}))


if __name__ == "__main__":
    unittest.main()
