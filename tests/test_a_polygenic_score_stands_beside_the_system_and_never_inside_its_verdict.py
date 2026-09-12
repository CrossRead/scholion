"""A polygenic score stands beside the system and never inside its verdict.

Task 178. The owner's decision was one sentence — polygenic scores go into
every panel of the radar — and the rules that make it safe are held here:

  * the map `prs_system_map.json` is consistent with both registries: every
    trait it names is a pinned model, every system key is a radar domain, a
    trait sits on ONE system, and every pinned trait it does not place is
    named in `_meta.why_partial` with a reason — a trait that dropped out of
    the map in silence would be indistinguishable from one never pinned;
  * the rows come from `prs_findings` filtered through the map, so a
    percentile is computed once and the card cannot disagree with the
    polygenic report; an unmapped trait appears on no card;
  * a reliable score at or above the 80th percentile is ONE question in
    layer 7, phrased as a question with both caveats inside it; an
    unreliable one keeps its note and raises none;
  * the verdict and the 0–100 score are byte-identical with and without the
    scores — a percentile inside a reference panel is neither a finding
    about a gene nor a measurement the next draw could refute;
  * the patient's register shows the trait, the percentile and the trust
    flag; the clinician's adds the model id, the evidence tier and the notes;
  * with no scores on the profile the block says so and says where scores
    come from — a full genome, never an array's positions;
  * the genome basket says in words what a full genome would close for THIS
    system when the input is no genome, an array or an exome, and says
    nothing of the kind when the input is a full genome.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion import format as fmt
from scholion.engine import genomics, system_panels as SP
from scholion import i18n
from scholion.i18n import en, ru


def _load(name):
    return json.loads(core.knowledge_path(name).read_text(encoding="utf-8"))


def _trait(term, percentile, reliable=True, **over):
    row = {"term": term, "label": term.capitalize(), "percentile": percentile,
           "reliable": reliable, "pgs_id": "PGS000001", "evidence": "clinical",
           "evidence_label": "clinical", "quality_label": "reliable"}
    row.update(over)
    return row


#: A reliable score at P99 on a thyroid trait, an unreliable one beside it
#: with the note that withdrew trust, and a trait no system holds.
FINDINGS = {"available": True,
            "categories": [{"category": "endocrine", "traits": [
                _trait("hypothyroidism", 99.0),
                _trait("Graves disease", 97.0, reliable=False,
                       validity_note="coverage below the line")]},
                {"category": "nervous", "traits": [_trait("migraine", 99.0)]}],
            "high": [], "stats": {}, "disclaimer": "d"}
NO_SCORES = {"available": False, "message": "not computed"}


def _with(findings):
    return mock.patch.object(genomics, "prs_findings", lambda: dict(findings))


class TestTheMapIsConsistentWithBothRegistries(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.book = _load("prs_system_map.json")
        cls.pinned = set(_load("prs_models.json")["models"])
        cls.domains = {d["key"]: d for d in SP.domains()}

    def test_every_trait_named_is_a_pinned_model(self):
        for key, spec in self.book["systems"].items():
            for trait in spec["traits"]:
                with self.subTest(system=key, trait=trait):
                    self.assertIn(trait, self.pinned)

    def test_every_system_key_is_a_radar_domain_with_a_genetic_half(self):
        for key in self.book["systems"]:
            with self.subTest(system=key):
                self.assertIn(key, self.domains)
                self.assertTrue(self.domains[key]["genetic_half"],
                                "a score placed on a system with no genetic half by design")

    def test_a_trait_sits_on_one_system_only(self):
        seen = {}
        for key, spec in self.book["systems"].items():
            for trait in spec["traits"]:
                self.assertNotIn(trait, seen, f"{trait} on {key} and on {seen.get(trait)}")
                seen[trait] = key

    def test_every_pinned_trait_is_placed_or_named_with_a_reason(self):
        mapped = {t for s in self.book["systems"].values() for t in s["traits"]}
        partial = self.book["_meta"]["why_partial"]
        self.assertEqual(set(), mapped & set(partial), "placed AND explained away")
        self.assertEqual(self.pinned, mapped | set(partial),
                         "a pinned trait neither placed nor explained: "
                         + ", ".join(sorted(self.pinned - mapped - set(partial)))
                         + " — or a name the registry does not pin: "
                         + ", ".join(sorted((mapped | set(partial)) - self.pinned)))
        for trait, why in partial.items():
            self.assertTrue(isinstance(why, str) and why.strip(), trait)

    def test_a_system_with_no_model_says_why_in_both_languages(self):
        for key, spec in self.book["systems"].items():
            if not spec["traits"]:
                with self.subTest(system=key):
                    self.assertEqual({"en", "ru"}, set(spec["why_empty"]))

    def test_the_meta_declares_itself(self):
        meta = self.book["_meta"]
        for field in ("purpose", "who_writes_this", "why_partial", "schema", "source_tier", "updated"):
            self.assertIn(field, meta)
        self.assertEqual("curated_reference", meta["source_tier"])

    def test_the_gate_drops_and_counts_a_name_neither_file_holds(self):
        bad = {"_meta": {}, "systems": {"thyroid": {"traits": ["hypothyroidism", "not a trait"]},
                                        "spleen": {"traits": ["gout"]}}}
        with mock.patch.object(core, "_read_knowledge",
                               lambda name: bad if name == "prs_system_map.json"
                               else _load(name)):
            m = SP.prs_system_map()
        self.assertEqual(["hypothyroidism"], m["systems"]["thyroid"]["traits"])
        self.assertNotIn("spleen", m["systems"])
        self.assertEqual(2, m["refused"])


class TestTheScoresOnTheCard(unittest.TestCase):

    def test_rows_land_on_the_mapped_system_and_an_unmapped_trait_on_none(self):
        with _with(FINDINGS):
            thyroid = SP.system("thyroid", "clinician")["genetics"]["polygenic"]
            everywhere = [r["trait"] for d in SP.domains() if d["genetic_half"]
                          for r in SP.system(d["key"], "clinician")["genetics"]["polygenic"]["rows"]]
        self.assertEqual("ok", thyroid["status"])
        self.assertEqual(["hypothyroidism", "Graves disease"], [r["trait"] for r in thyroid["rows"]])
        self.assertEqual(["hypothyroidism"], thyroid["high"])
        self.assertEqual((3, 2), (thyroid["mapped"], thyroid["scored"]))
        self.assertEqual(["thyroid cancer"], thyroid["unscored"])
        self.assertNotIn("migraine", everywhere)

    def test_a_reliable_high_score_is_one_question_and_an_unreliable_one_is_none(self):
        with _with(FINDINGS):
            r = SP.system("thyroid", "clinician")
        qs = [q for q in r["questions"]["rows"] if q["origin"] == "polygenic"]
        self.assertEqual(1, len(qs))
        self.assertEqual("hypothyroidism", qs[0]["trait"])
        self.assertTrue(qs[0]["text"].rstrip().endswith("?"), "a question, not an instruction")
        self.assertIn("not a probability", qs[0]["text"])
        self.assertIn("European", qs[0]["text"])
        self.assertIn("polygenic", SP.QUESTION_ORIGINS)
        asked = [q for q in r["next"]["ask"]["rows"] if q.get("origin") == "polygenic"]
        self.assertEqual(1, len(asked), "the question reaches the ask basket once")
        unreliable = next(x for x in r["genetics"]["polygenic"]["rows"] if not x["reliable"])
        self.assertEqual("coverage below the line", unreliable["validity_note"])

    def test_the_verdict_and_the_score_are_byte_identical_with_and_without_scores(self):
        for reg in SP.REGISTERS:
            with self.subTest(register=reg):
                with _with(FINDINGS):
                    loud = SP.system("thyroid", reg)
                with _with(NO_SCORES):
                    quiet = SP.system("thyroid", reg)
                self.assertEqual(json.dumps(loud["verdict"], sort_keys=True),
                                 json.dumps(quiet["verdict"], sort_keys=True))
                self.assertEqual(loud["verdict_line"], quiet["verdict_line"])
                self.assertEqual(loud["labs"].get("score"), quiet["labs"].get("score"))
                self.assertEqual("ok", loud["genetics"]["polygenic"]["status"])
                self.assertEqual("no_scores", quiet["genetics"]["polygenic"]["status"])

    def test_the_patient_register_lacks_the_model_id_and_the_clinician_has_it(self):
        with _with(FINDINGS):
            pt = SP.system("thyroid", "patient")["genetics"]["polygenic"]
            cl = SP.system("thyroid", "clinician")["genetics"]["polygenic"]
        self.assertEqual([r["trait"] for r in pt["rows"]], [r["trait"] for r in cl["rows"]],
                         "both registers carry the same rows")
        for r in pt["rows"]:
            self.assertEqual({"trait", "label", "percentile", "reliable"}, set(r))
        for r in cl["rows"]:
            self.assertEqual("PGS000001", r["pgs_id"])
            self.assertEqual("clinical", r["evidence"])
        self.assertEqual(pt["high"], cl["high"])

    def test_both_languages_resolve_and_the_scores_print_under_their_own_head(self):
        for code, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            # `set_lang`, not only the environment: a thread that already chose a
            # language (any CLI run in the same process does) keeps it over the
            # variable, and the suite runs such tests first.
            with self.subTest(lang=code), mock.patch.dict("os.environ", {"SCHOLION_LANG": code}), \
                    _with(FINDINGS):
                i18n.set_lang(code); self.addCleanup(i18n.set_lang, None)
                core.reset_cache()
                for reg in SP.REGISTERS:
                    text = fmt.system_report(SP.system("thyroid", reg))
                    self.assertNotIn("⟦", text)
                    self.assertIn(cat["system.polygenic.title"], text)
                    self.assertIn(cat["system.polygenic.caveat"], text)
                    # Never interleaved: the head of the scores comes after
                    # the last gene row of layer 3 and before layer 4.
                    layer3 = text.split("**3. ", 1)[1].split("**4. ", 1)[0]
                    head = layer3.index(cat["system.polygenic.title"])
                    # The noun of a score row in this language, read off the
                    # catalogue rather than spelled here (the language gate
                    # counts every Russian word in a test).
                    import re as _re
                    tpl = cat["system.polygenic.row"]
                    for ph in ("{label}", "{percentile}", "{reliable}"):
                        tpl = tpl.replace(ph, " ")
                    word = max(_re.findall(r"[^\W\d_]+", tpl), key=len)
                    for line in layer3[:head].splitlines():
                        self.assertFalse(line.startswith("   · ") and word in line,
                                         "a score row printed among the gene rows: " + line)
                    bullets = [ln for ln in layer3[head:].splitlines() if ln.startswith("   · ")]
                    self.assertEqual(2, len(bullets))
                    for line in bullets:
                        self.assertIn(word, line, "a gene row printed among the scores: " + line)
                    self.assertIn("99", layer3[head:])
                    if reg == "clinician":
                        self.assertIn("PGS000001", layer3[head:])
                    else:
                        self.assertNotIn("PGS000001", layer3[head:])
        core.reset_cache()

    def test_the_listing_counts_the_scores_per_system_and_never_folds_them_into_a_ring(self):
        with _with(FINDINGS):
            d = SP.systems()
            listing = fmt.systems_report(d)
        by = {s["key"]: s["genetics"]["polygenic"] for s in d["systems"]}
        self.assertEqual({"status": "ok", "mapped": 3, "scored": 2, "high": 1}, by["thyroid"])
        self.assertEqual(0, by["fitness"]["mapped"])
        self.assertEqual("no_map", by["adrenals"]["status"])
        self.assertIn("polygenic: scored 2 of 3", listing)
        with _with(NO_SCORES):
            quiet = {s["key"]: s["genetics"] for s in SP.systems()["systems"]}
        for s in d["systems"]:
            with self.subTest(system=s["key"]):
                g = s["genetics"]
                self.assertEqual((g["read_count"], g["unread_count"]),
                                 (quiet[s["key"]]["read_count"], quiet[s["key"]]["unread_count"]),
                                 "the second ring moved when scores appeared")
                self.assertFalse({"completeness", "index", "combined"} & set(g))


class TestWithoutScoresAndWithoutAFullGenome(unittest.TestCase):
    """The fixture: no `prs_results.json`, no genome file."""

    def test_no_scores_says_so_and_names_where_scores_come_from(self):
        r = SP.system("thyroid")
        poly = r["genetics"]["polygenic"]
        self.assertEqual("no_scores", poly["status"])
        self.assertEqual([], poly["rows"])
        self.assertEqual(3, poly["mapped"])
        self.assertIn("preparing-the-genome", poly["why"])
        self.assertIn("full genome", poly["why"])
        self.assertIn(poly["why"], fmt.system_report(r))

    def test_a_system_with_no_model_says_why_in_the_readers_language(self):
        r = SP.system("adrenals")
        self.assertEqual("no_map", r["genetics"]["polygenic"]["status"])
        self.assertIn("adrenal", r["genetics"]["polygenic"]["why"])
        with mock.patch.dict("os.environ", {"SCHOLION_LANG": "ru"}):
            i18n.set_lang("ru"); self.addCleanup(i18n.set_lang, None)
            core.reset_cache()
            why_ru = SP.system("adrenals")["genetics"]["polygenic"]["why"]
        i18n.set_lang(None); core.reset_cache()
        raw = json.loads(core.knowledge_path("prs_system_map.json").read_text(encoding="utf-8"))
        expected = raw["systems"]["adrenals"]["why_empty"]["ru"]
        self.assertEqual(expected, why_ru)
        self.assertNotEqual(r["genetics"]["polygenic"]["why"], why_ru, "the two languages differ")

    def test_the_genome_basket_names_what_a_full_genome_would_close(self):
        fg = SP.system("thyroid")["next"]["genome"]["full_genome"]
        self.assertEqual("none", fg["input"])
        self.assertGreater(fg["genes"], 0)
        self.assertEqual(3, fg["scores"])
        self.assertIn("full genome", fg["text"])
        self.assertIn(str(fg["genes"]), fg["text"])
        self.assertIn("preparing-the-genome", fg["text"])
        self.assertIn(fg["text"], fmt.system_report(SP.system("thyroid")))
        self.assertIsNone(SP.system("fitness")["next"]["genome"]["full_genome"])

    def test_an_array_and_an_exome_are_named_and_a_full_genome_says_nothing(self):
        gen = {"status": "composed", "rows": [{"gene": "A", "read": False}, {"gene": "B", "read": True}],
               "polygenic": {"status": "no_scores", "mapped": 4}}
        with mock.patch("scholion.genome.available", lambda: {"ready": True, "input_profile": "array"}):
            fg = SP._full_genome(gen)
            self.assertEqual(("array", 1, 4), (fg["input"], fg["genes"], fg["scores"]))
            self.assertIn(en.MESSAGES["system.input.array"], fg["text"])
        with mock.patch("scholion.genome.available", lambda: {"ready": True, "input_profile": "exome"}):
            self.assertEqual("exome", SP._full_genome(gen)["input"])
        with mock.patch("scholion.genome.available", lambda: {"ready": True, "input_profile": "panel"}):
            fg = SP._full_genome(gen)
            self.assertEqual("narrow", fg["input"])
            self.assertIn("panel", fg["text"])
        with mock.patch("scholion.genome.available",
                        lambda: {"ready": True, "input_profile": "whole_genome"}):
            self.assertIsNone(SP._full_genome(gen))
        with mock.patch("scholion.genome.available", lambda: {"ready": True}):
            self.assertIsNone(SP._full_genome(gen), "an unmeasured but ready input is not accused")
        # Nothing to close: everything read, scores present.
        with mock.patch("scholion.genome.available", lambda: {"ready": False}):
            self.assertIsNone(SP._full_genome({"status": "composed", "rows": [{"gene": "B", "read": True}],
                                               "polygenic": {"status": "ok", "mapped": 4}}))

    def test_every_new_key_is_in_both_catalogues_and_the_question_asks_in_both(self):
        keys = [k for k in en.MESSAGES if k.startswith(("system.polygenic.", "system.input.",
                                                        "system.next.full_genome"))]
        keys += ["system.q.polygenic", "systems.polygenic"]
        self.assertGreaterEqual(len(keys), 18)
        for k in keys:
            with self.subTest(key=k):
                self.assertIn(k, ru.MESSAGES)
        self.assertTrue(ru.MESSAGES["system.q.polygenic"].rstrip().endswith("?"))


if __name__ == "__main__":
    unittest.main()
