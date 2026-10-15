"""Synthetic interleaved PDF rows must keep formula, assay and specimen identity."""
import unittest

import support  # noqa: F401
from scholion import core, ingest_labs

HEADER = 'Дата взятия биоматериала: 02.06.2026 08:10\n'


def parse(text):
    return ingest_labs.parse_report(HEADER + text, core.lab_markers()['markers'])[1]


class WrappedAssayIdentity(unittest.TestCase):
    def test_three_renal_formulae_do_not_become_creatinine(self):
        found = parse('''Скорость клубочковой фильтрации (формула мл/мин/1.73
115,2 > 60
Кокрофта-Голта) кв.м.
Клубочковая фильтрация, расчет по формуле мл/мин/1.73
104,1 > 60
CKD-EPI – креатинин кв.м.
мл/мин/1.73
Скорость клубочковой фильтрации (MDRD) 93,4 >60
кв.м.
Креатинин 82 44 - 110 мкмоль/л''')
        self.assertEqual(82, found['creatinine']['value'])
        self.assertEqual(104.1, found['egfr_ckdepi']['value'])
        self.assertEqual(115.2, found['creatinine_clearance_cg']['value'])
        self.assertEqual(93.4, found['egfr_mdrd']['value'])
        for key in ['creatinine_clearance_cg', 'egfr_mdrd']:
            self.assertEqual('mL/min/{1.73_m2}', found[key]['unit'])

    def test_standard_and_high_sensitivity_crp_are_distinct_in_both_orders(self):
        hs = 'С-реактивный белок (СРБ)\n0,62 <1 Низкий риск мг/л\nультрачувствительный\n'
        ordinary = 'С-реактивный белок (СРБ) 0,59 0,00 - 5,00 мг/л\n'
        for text in [hs + ordinary, ordinary + hs]:
            with self.subTest(text=text):
                f = parse(text)
                self.assertEqual(.62, f['crp_hs']['value'])
                self.assertEqual(.59, f['crp']['value'])
        self.assertNotIn('crp_hs', parse(ordinary))
        self.assertNotIn('crp', parse(hs))

    def test_wrapped_non_hdl_is_not_hdl(self):
        f = parse('Холестерин не липопротеинов высокой\n4,7 повышено <3.8 ммоль/л\nплотности (Х-не-ЛПВП)\nХолестерин ЛПВП 1,3 ммоль/л >1,0')
        self.assertEqual(4.7, f['non_hdl']['value'])
        self.assertEqual('mmol/L', f['non_hdl']['unit'])
        self.assertEqual(1.3, f['hdl']['value'])

    def test_recognition_proposals_have_no_authored_reference(self):
        m = core.lab_markers()['markers']
        for key in ['crp', 'non_hdl', 'egfr_mdrd', 'creatinine_clearance_cg']:
            self.assertEqual('proposed', m[key]['status'])
            self.assertNotIn('ref_low', m[key])
            self.assertNotIn('ref_high', m[key])
            self.assertNotIn('loinc', m[key])

    def test_unknown_urinalysis_rows_are_disclosed_without_values(self):
        rows = ingest_labs._unrecognised_labels(HEADER + '''Биоматериал: Моча разовая
Белок отсутствует г/л <0,1
Лейкоциты 0-2 в п/зр. 0-3
Оксалаты отсутствуют в п/зр. отсутствуют
Заявка №: 123 Биоматериал: Моча
Стр. 1 из 2''', limit=100)
        labels = [r['label'] for r in rows]
        for label in ['Белок', 'Лейкоциты', 'Оксалаты']:
            self.assertIn(label, labels)
        self.assertFalse(any('Заявка' in x or 'Стр.' in x for x in labels))
        self.assertTrue(all(set(r) == {'label', 'unit'} for r in rows))

    def test_a_malformed_scale_does_not_supply_a_false_grade(self):
        f = parse('Холестерин ЛПВП 1,1 ммоль/л\n>1.45-риск отсутствует\n<0.9-высокий риск\n<2.59-3.34- оптимальный\nХолестерин ЛПНП 4,2 ммоль/л')
        self.assertIsNone(f['hdl'].get('reference_grade'))


if __name__ == '__main__':
    unittest.main()
