"""A negative statement about pharmacogenetics is only made after asking.

`drugsource` is how a drug that is not in the local database is identified: the
name goes out to RxNorm, the ATC classes come back, and CPIC is asked which genes
matter for it. Nothing about a person goes out — only the name they typed.

The defect this module's own docstring records is the reason most of these tests
exist. `cpic_lookup` used to return a bare list, and it returned `[]` in three
different situations: CPIC said this drug has no meaningful pharmacogenetics; the
network was switched off; the request failed. `net.get_json` turns every
exception into `None`, so from the inside those are indistinguishable — and
downstream an empty list was printed as «no genes affecting the dose or the
effect were found». A statement about a database that had never been reached,
made in the same words as one that had. It was seen on amiodarone, offline, and
the verdict came out green.

The repair was to return `asked` beside the genes. What had no test was whether
`asked` is ever wrong — which is the only thing that matters about it, and the
module sat at 47.9%.

Nothing here goes near the network. `net.get_json` is replaced for the length of
a test, so what is measured is this module's own reasoning about answers it did
and did not get. The suite runs with SCHOLION_OFFLINE=1 anyway, which is itself
one of the cases.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import drugsource


@contextmanager
def isolated_cache():
    """A cache directory of this test's own — `.cache/` in the tree is not it."""
    tmp = Path(tempfile.mkdtemp(prefix="drugsource-"))
    old = os.environ.get("SCHOLION_CACHE_DIR")
    os.environ["SCHOLION_CACHE_DIR"] = str(tmp)
    try:
        yield tmp
    finally:
        if old is None:
            os.environ.pop("SCHOLION_CACHE_DIR", None)
        else:
            os.environ["SCHOLION_CACHE_DIR"] = old
        shutil.rmtree(tmp, ignore_errors=True)


@contextmanager
def answers(mapping=None, default=None, online=True):
    """`net.get_json` replaced by a table: url substring → answer."""
    mapping = mapping or {}

    def fake(url, *a, **k):
        for needle, value in mapping.items():
            if needle in url:
                return value
        return default

    with mock.patch.object(drugsource.net, "get_json", side_effect=fake) as m, \
            mock.patch.object(drugsource.net, "offline", return_value=not online):
        yield m


CPIC_ROWS = [
    {"genesymbol": "CYP2C19", "cpiclevel": "A", "pgxtesting": "Actionable PGx"},
    {"genesymbol": "ABCB1", "cpiclevel": "C", "pgxtesting": None},
    {"genesymbol": None, "cpiclevel": "A", "pgxtesting": None},
]


class TestCpicIsNeverAnsweredForWithoutAsking(unittest.TestCase):

    def test_a_drug_that_was_never_identified_has_no_key_to_ask_by(self):
        got = drugsource.cpic_lookup("", allow_network=True)
        self.assertFalse(got["asked"])
        self.assertEqual([], got["genes"])
        self.assertEqual("not_identified", got["reason"])

    def test_with_the_network_off_it_says_so_rather_than_saying_no_genes(self):
        """The amiodarone case, in one assertion: `genes` is empty and `asked` is
        false, and nothing downstream may read the first without the second."""
        with isolated_cache(), answers(online=False):
            got = drugsource.cpic_lookup("703")
        self.assertEqual([], got["genes"])
        self.assertFalse(got["asked"], "an empty list was passed off as an answer from CPIC")
        self.assertEqual("offline", got["reason"])

    def test_a_request_that_failed_is_not_an_answer_either(self):
        with isolated_cache(), answers(default=None, online=True):
            got = drugsource.cpic_lookup("703")
        self.assertFalse(got["asked"])
        self.assertEqual("unreachable", got["reason"])

    def test_a_database_that_answered_nothing_is_a_real_answer(self):
        """CPIC replying with an empty list means this drug has no meaningful
        pharmacogenetics — the one case where «no genes» may be said out loud."""
        with isolated_cache(), answers({"cpicpgx.org": []}, online=True):
            got = drugsource.cpic_lookup("703")
        self.assertEqual([], got["genes"])
        self.assertTrue(got["asked"], "a real negative answer was reported as a failure")
        self.assertIsNone(got["reason"])

    def test_the_genes_come_back_actionable_first(self):
        with isolated_cache(), answers({"cpicpgx.org": CPIC_ROWS}, online=True):
            got = drugsource.cpic_lookup("703")
        self.assertTrue(got["asked"])
        self.assertEqual(["CYP2C19", "ABCB1"], [g["gene"] for g in got["genes"]],
                         "a row with no gene survived, or the actionable one is not first")
        self.assertTrue(got["genes"][0]["actionable"])
        self.assertFalse(got["genes"][1]["actionable"])

    def test_a_level_b_pair_is_actionable_even_without_the_testing_flag(self):
        with isolated_cache(), answers({"cpicpgx.org": [
                {"genesymbol": "SLCO1B1", "cpiclevel": "B", "pgxtesting": None}]}, online=True):
            got = drugsource.cpic_lookup("703")
        self.assertTrue(got["genes"][0]["actionable"])

    def test_a_cached_answer_still_counts_as_having_been_asked(self):
        with isolated_cache():
            with answers({"cpicpgx.org": CPIC_ROWS}, online=True) as first:
                drugsource.cpic_lookup("703")
                self.assertTrue(first.called)
            # Offline now, and the cache must carry the earlier real answer rather
            # than the module forgetting it had one.
            with answers(online=False) as second:
                got = drugsource.cpic_lookup("703")
            self.assertTrue(got["asked"])
            self.assertEqual(["CYP2C19", "ABCB1"], [g["gene"] for g in got["genes"]])
            self.assertFalse(second.called, "a cached answer went out to the network again")

    def test_the_network_is_not_touched_when_it_was_not_allowed(self):
        with isolated_cache(), answers({"cpicpgx.org": CPIC_ROWS}, online=True) as m:
            got = drugsource.cpic_lookup("703", allow_network=False)
        self.assertFalse(m.called, "allow_network=False still made a request")
        self.assertFalse(got["asked"])


class TestTheAtcTableMapsOntoTheProjectsClasses(unittest.TestCase):

    def test_a_known_prefix_becomes_the_internal_class(self):
        self.assertEqual("statin", drugsource._map_internal_class(
            [{"code": "C10AA05", "name": "HMG CoA reductase inhibitors"}]))
        self.assertEqual("anticoagulant_vka", drugsource._map_internal_class(
            [{"code": "B01AA03", "name": "warfarin"}]))

    def test_a_code_nobody_mapped_is_not_guessed_at(self):
        self.assertIsNone(drugsource._map_internal_class([{"code": "V03AB", "name": "antidote"}]))

    def test_no_classes_at_all_is_not_a_class(self):
        self.assertIsNone(drugsource._map_internal_class([]))

    def test_the_first_code_that_matches_decides(self):
        got = drugsource._map_internal_class(
            [{"code": "V03AB", "name": "x"}, {"code": "C07AB07", "name": "bisoprolol"}])
        self.assertEqual("beta_blocker", got)

    def test_every_class_that_names_a_gene_gives_back_a_reason_in_words(self):
        for cls in drugsource._CLASS_GENE:
            with self.subTest(cls=cls):
                gene, why = drugsource.class_gene(cls)
                self.assertTrue(gene)
                self.assertTrue(why.strip(), f"{cls} has a gene and no reason to show for it")
                self.assertNotIn("gene_why.", why, "the catalogue key was printed instead of the phrase")

    def test_a_class_with_no_pharmacogenetics_answers_nothing(self):
        self.assertIsNone(drugsource.class_gene("thiazide"))
        self.assertIsNone(drugsource.class_gene(None))

    def test_every_mapped_class_is_one_the_project_actually_knows(self):
        """The table maps ATC onto this project's own class names, and a name
        that no longer exists elsewhere maps a drug into nothing at all."""
        from scholion import core
        known = set(core.med_classes().get("classes", {}))
        if not known:
            self.skipTest("this build carries no class catalogue")
        used = {cls for _, cls in drugsource._ATC_TO_CLASS}
        self.assertEqual(set(), used - known,
                         "the ATC table names classes the catalogue does not: "
                         + ", ".join(sorted(used - known)))


class TestARussianNameIsMadeAskable(unittest.TestCase):

    def test_cyrillic_is_transliterated_letter_by_letter(self):
        self.assertEqual("varfarin", drugsource._translit("варфарин"))
        self.assertEqual("metformin", drugsource._translit("метформин"))

    def test_a_soft_sign_disappears_rather_than_becoming_a_letter(self):
        self.assertEqual("kaltsiy", drugsource._translit("кальций"))

    def test_the_two_scripts_are_told_apart(self):
        self.assertTrue(drugsource._has_cyrillic("варфарин"))
        self.assertFalse(drugsource._has_cyrillic("warfarin"))
        self.assertTrue(drugsource._has_latin("warfarin"))
        self.assertFalse(drugsource._has_latin("варфарин"))

    def test_approximate_search_is_not_used_on_cyrillic(self):
        """Named in the module: approximate search on a Cyrillic string returns
        junk — the Cyrillic spelling of «metformin» resolves to «citrate». So the
        original goes out last and exact only."""
        with isolated_cache(), answers({}, default=None, online=True) as m:
            drugsource._rxcui_for("метформин", approx=False)
        urls = [c.args[0] for c in m.call_args_list]
        self.assertTrue(urls, "nothing was asked at all")
        self.assertFalse([u for u in urls if "approximateTerm" in u],
                         "the approximate endpoint was asked about a Cyrillic term")

    def test_an_exact_hit_is_preferred_to_an_approximate_one(self):
        with isolated_cache(), answers({"rxcui.json": {"idGroup": {"rxnormId": ["11289"]}},
                                        "approximateTerm": {"approximateGroup": {
                                            "candidate": [{"rxcui": "999"}]}}}, online=True):
            self.assertEqual("11289", drugsource._rxcui_for("warfarin"))

    def test_an_approximate_hit_is_used_when_there_is_no_exact_one(self):
        with isolated_cache(), answers({"rxcui.json": {"idGroup": {}},
                                        "approximateTerm": {"approximateGroup": {
                                            "candidate": [{"rxcui": "999"}]}}}, online=True):
            self.assertEqual("999", drugsource._rxcui_for("warfarn"))


class TestTheDrugItself(unittest.TestCase):

    RX = {"rxcui.json": {"idGroup": {"rxnormId": ["11289"]}},
          "property.json": {"propConceptGroup": {"propConcept": [{"propValue": "warfarin"}]}},
          "byRxcui.json": {"rxclassDrugInfoList": {"rxclassDrugInfo": [
              {"minConcept": {"tty": "IN", "name": "warfarin"},
               "rxclassMinConceptItem": {"classId": "B01AA03", "className": "vitamin K antagonists"}}]}}}

    def test_an_empty_name_is_not_looked_up(self):
        self.assertIsNone(drugsource.resolve_drug("  "))

    def test_nothing_goes_out_when_the_network_was_not_allowed(self):
        with isolated_cache(), answers(self.RX, online=True) as m:
            self.assertIsNone(drugsource.resolve_drug("warfarin", allow_network=False))
        self.assertFalse(m.called)

    def test_a_drug_that_resolves_carries_its_class_and_a_link(self):
        with isolated_cache(), answers(self.RX, online=True):
            got = drugsource.resolve_drug("warfarin")
        self.assertEqual("11289", got["rxcui"])
        self.assertEqual("warfarin", got["name"])
        self.assertEqual("warfarin", got["ingredient"])
        self.assertEqual("anticoagulant_vka", got["internal_class"])
        self.assertIn("11289", got["url"])
        self.assertEqual("rxnorm", got["source"])

    def test_a_name_that_resolves_to_nothing_is_not_remembered_as_absent(self):
        """A negative result may be a network failure that has already passed.
        Caching it would make one bad minute permanent."""
        with isolated_cache() as cache_dir:
            with answers({}, default=None, online=True):
                self.assertIsNone(drugsource.resolve_drug("no-such-drug"))
            f = cache_dir / "drug_cache.json"
            body = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            self.assertNotIn("no-such-drug", body,
                             "a failure to resolve was cached as an answer")

    def test_a_second_lookup_uses_the_cache(self):
        with isolated_cache():
            with answers(self.RX, online=True):
                drugsource.resolve_drug("warfarin")
            with answers({}, default=None, online=True) as second:
                got = drugsource.resolve_drug("warfarin")
            self.assertEqual("11289", got["rxcui"])
            self.assertFalse(second.called, "a cached drug was looked up again")

    def test_a_cache_file_that_is_rubbish_is_not_a_crash(self):
        with isolated_cache() as cache_dir:
            (cache_dir / "drug_cache.json").write_text("{not json", encoding="utf-8")
            self.assertEqual({}, drugsource._load_cache())


class TestTranslationOfABrandName(unittest.TestCase):
    """A brand written in Cyrillic does not transliterate into anything RxNorm
    knows, so it is translated first."""

    def test_a_usable_translation_is_taken(self):
        with answers({"mymemory": {"responseData": {"translatedText": "Glucophage"}}}, online=True):
            self.assertEqual("Glucophage", drugsource._translate_ru_en("Глюкофаж"))

    def test_a_service_complaint_is_not_a_translation(self):
        """MyMemory answers with its own error text in the field where a
        translation goes, and the words would then be looked up as a drug."""
        with answers({"mymemory": {"responseData": {
                "translatedText": "PLEASE SELECT TWO DISTINCT LANGUAGES"}}}, online=True):
            self.assertIsNone(drugsource._translate_ru_en("Глюкофаж"))

    def test_the_second_translator_is_tried_when_the_first_says_nothing(self):
        with answers({"mymemory": {"responseData": {"translatedText": ""}},
                      "translate.googleapis": [[["Glucophage", "Глюкофаж", None, None]]]},
                     online=True):
            self.assertEqual("Glucophage", drugsource._translate_ru_en("Глюкофаж"))

    def test_a_translation_that_gives_the_word_back_is_no_translation(self):
        with answers({"mymemory": {"responseData": {"translatedText": "Глюкофаж"}}},
                     default=None, online=True):
            self.assertIsNone(drugsource._translate_ru_en("Глюкофаж"))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
