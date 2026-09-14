"""A body system answers as one subject: seven layers, a verdict, three baskets, questions.

Task 168, step 3 — the engine, no screen yet. What is held here:

  * an empty curated file gives a meaningful answer for every system: «not
    composed, and here is why» for ten of them, the base-generated monogenic
    half for the thyroid, «no genetic half by design» for fitness — and the
    three are different answers, not three empty blocks;
  * a system with an unread row is never `clear_measured`;
  * a row without a source is dropped and counted; with a source and no
    phrase for the state found it is pending; without a mode it is dropped;
  * Limited / Disputed / Refuted never become a finding in any register;
  * for a recessive gene one copy is a carrier and a question, not a risk;
  * a single common variant prints only with an effect size from a study;
  * an `expect` on a marker outside the panel is dropped; on a marker never
    taken it is a gap, not a disagreement; on a measured marker it is a
    QUESTION with the person's numbers;
  * a rule that fired on a marker of the system lands in the «lab» basket and
    is not repeated in «ask»; every empty basket names its reason;
  * the two registers differ in density and never in the verdict;
  * genetics does not move the 0–100 score — the test changes the genetic
    layer and reads the score twice.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

# ---- one synthetic state -----------------------------------------------------
LOCI = {"loci": {f"rs{g}": {"gene": g} for g in
                 ("LIM", "REC", "TWO", "DOM", "PL", "PAR", "PCV", "PPEND", "PNA",
                  "PABS", "PUNR", "PEXP", "GX")}}
CALLS = {"rsPL": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsPAR": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsPCV": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsPPEND": {"genotype": "GG", "confidence": "called", "depth": 30},
         "rsPNA": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsPABS": {"genotype": "AA", "confidence": "called", "depth": 30},
         "rsPUNR": {"genotype": None, "confidence": "assumed_ref"},
         "rsPEXP": {"genotype": "AG", "confidence": "called", "depth": 30}}


def _lookup(rsid=None, gene=None):
    res = CALLS.get(rsid)
    return {"status": "ok", "rsid": rsid,
            "result": dict(res) if res else {"confidence": "confirmed_ref", "depth": 20}}


TXT = {"en": "what follows", "ru": "what follows (ru)"}


def _sub(classification, moi_code, submitter="A", disease="a disease"):
    return {"disease": disease, "disease_id": "MONDO:1", "classification": classification,
            "moi": moi_code, "moi_code": moi_code, "submitter": submitter,
            "curated_on": "2024-01-01", "mode": "monogenic"}


BASE = {"_meta": {"export_last_modified": "2026-09-06", "downloaded": "2026-09-12",
                  "filter_version": "t.1"},
        "systems": {"thyroid": {"source": "a test", "genes": {
            "LIM": {"submissions": [_sub("Limited", "AD")]},
            "REC": {"submissions": [_sub("Strong", "AR")]},
            "TWO": {"submissions": [_sub("Limited", "AD", "A"), _sub("Strong", "AR", "B")]},
            "DOM": {"submissions": [_sub("Definitive", "AD")]}}}}}

CLINVAR = {"status": "ok", "by_gene": {"LIM": [{"zygosity": "hom"}], "REC": [{"zygosity": "het"}],
                                       "TWO": [{"zygosity": "het"}], "DOM": [{"zygosity": "het"}]}}


def _pos(rs, gene, **over):
    row = {"rsid": rs, "gene": gene, "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
           "mode": "monogenic", "classification": "Strong", "moi": "AD",
           "text": {"het": TXT, "hom": TXT}, "source": "the author"}
    row.update(over)
    return row


CURATED = {"_meta": {"why_empty": "nobody wrote a row",
                     "absent_template": {"text": {"en": "{gene} {rsid}: not found ({confidence}, {depth})",
                                                  "ru": "{gene} {rsid}: not found (ru) ({confidence}, {depth})"}}},
           "systems": {"thyroid": {"source": None, "positions": [
               _pos("rsPL", "PL", classification="Limited"),
               _pos("rsPAR", "PAR", moi="AR"),
               _pos("rsPCV", "PCV", mode="common_variant", classification=None, moi=None,
                    effect_size="0.1 SD per allele", study="PMID 1"),
               _pos("rsPCV", "PCVNO", mode="common_variant", classification=None, moi=None),
               _pos("rsPPEND", "PPEND", text={"het": None, "hom": None}),
               _pos("rsPNA", "PNA", risk_allele=None),
               _pos("rsPABS", "PABS"),
               _pos("rsPUNR", "PUNR"),
               _pos("rsPL", "NOMODE", mode=None),
               _pos("rsPL", "NOSRC", source=None),
               _pos("rsPEXP", "PEXPBAD", expect={"marker": "ldl", "direction": "lower"}),
               _pos("rsPEXP", "PEXP", expect={"marker": "tsh", "direction": "lower"})]}}}


class _State(unittest.TestCase):
    base, curated, terms = BASE, CURATED, {}

    def setUp(self):
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True}),
            mock.patch.object(SP, "_base", lambda: self.base),
            mock.patch.object(SP, "_curated", lambda: self.curated),
            mock.patch.object(SP, "_terms", lambda: self.terms),
            mock.patch.object(SP, "_clinvar_by_gene", lambda scan: dict(CLINVAR)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def rows(self, register="clinician"):
        return {r["gene"]: r for r in SP.system("thyroid", register)["genetics"]["rows"]}


class TestTheBaseHalfAndTheClinicianSignature(_State):

    def test_the_base_rows_carry_the_export_they_came_from(self):
        g = SP.system("thyroid", "clinician")["genetics"]
        self.assertEqual("2026-09-06", g["base"]["version"])
        self.assertEqual("2026-09-12", g["base"]["downloaded"])
        self.assertIn("2026-09-06", self.rows()["DOM"]["source"])

    def test_a_limited_assertion_is_never_a_finding_in_either_register(self):
        for reg in SP.REGISTERS:
            with self.subTest(register=reg):
                r = SP.system("thyroid", reg)
                self.assertNotIn("LIM", r["verdict"].get("genes") or [])
                self.assertEqual(0, sum(x["findings"] for x in r["genetics"]["rows"]
                                        if x["gene"] == "LIM"))
        lim = self.rows()["LIM"]
        self.assertFalse(lim["finding_grade"])
        self.assertEqual(1, lim["clinvar"]["withheld"], "the hit is counted, not lost")

    def test_one_copy_in_a_recessive_gene_is_a_carrier_and_a_question(self):
        rec = self.rows()["REC"]
        self.assertTrue(rec["carrier"])
        self.assertEqual(0, rec["findings"])
        q = [x for x in SP.system("thyroid")["questions"]["rows"]
             if x["origin"] == "moi" and x["gene"] == "REC"]
        self.assertEqual(1, len(q))
        self.assertNotIn("risk", q[0]["text"].split("not risk")[0].lower().replace("carriership", ""))

    def test_submitters_who_disagree_stand_side_by_side(self):
        two = self.rows()["TWO"]
        self.assertEqual(2, len(two["assertions"]))
        self.assertEqual(["Limited", "Strong"], two["classifications"])
        self.assertTrue(two["finding_grade"], "the Strong assertion is not averaged away")
        self.assertTrue(two["recessive_only"], "the strong assertion is recessive")
        self.assertTrue(two["carrier"])

    def test_a_dominant_definitive_gene_with_a_pathogenic_call_is_a_finding(self):
        dom = self.rows()["DOM"]
        self.assertEqual(1, dom["findings"])
        v = SP.system("thyroid")["verdict"]
        self.assertEqual("finding", v["kind"])
        self.assertIn("DOM", v["genes"])
        # REC and TWO from the base, PAR from the curated positions — counted
        # beside the finding, never folded into it.
        self.assertEqual(3, v["carriers"])

    def test_an_exclusion_with_a_source_removes_the_gene_and_is_listed(self):
        cur = json.loads(json.dumps(CURATED))
        cur["systems"]["thyroid"]["exclusions"] = {
            "DOM": {"reason": {"en": "not for an asymptomatic adult", "ru": "(ru)"}, "source": "signed"},
            "REC": {"reason": {"en": "no source", "ru": "(ru)"}}}
        with mock.patch.object(SP, "_curated", lambda: cur):
            g = SP.system("thyroid", "clinician")["genetics"]
        genes = {r["gene"] for r in g["rows"]}
        self.assertNotIn("DOM", genes)
        self.assertIn("REC", genes, "an exclusion without a source is not applied")
        self.assertEqual(["DOM"], [e["gene"] for e in g["excluded"]])
        self.assertEqual(1, g["refused"]["by_reason"]["exclusion_without_source"])


class TestTheCuratedPositionsThroughTheGate(_State):

    def test_what_the_gate_dropped_is_counted_by_reason(self):
        g = SP.system("thyroid", "clinician")["genetics"]
        self.assertEqual({"no_source": 1, "no_mode": 1, "common_variant_without_effect": 1,
                          "expect_marker_not_in_panel": 1}, g["refused"]["by_reason"])
        self.assertEqual(4, g["refused"]["total"])
        for dropped in ("NOSRC", "NOMODE", "PCVNO", "PEXPBAD"):
            self.assertNotIn(dropped, self.rows())

    def test_a_limited_position_is_never_a_finding_in_either_register(self):
        pl = self.rows()["PL"]
        self.assertEqual(0, pl["findings"])
        self.assertEqual("classification", pl["not_a_finding_why"])
        self.assertNotIn("PL", self.rows("patient"))

    def test_a_recessive_position_with_one_copy_is_a_carrier_not_a_finding(self):
        par = self.rows()["PAR"]
        self.assertTrue(par["carrier"])
        self.assertEqual(0, par["findings"])
        self.assertEqual("carrier", par["not_a_finding_why"])
        self.assertTrue(any(q["origin"] == "moi" and q["rsid"] == "rsPAR"
                            for q in SP.system("thyroid")["questions"]["rows"]))

    def test_a_common_variant_prints_only_with_an_effect_size_from_a_study(self):
        self.assertEqual(1, self.rows()["PCV"]["findings"])
        self.assertNotIn("PCVNO", self.rows())

    def test_a_named_position_without_a_phrase_for_its_state_is_pending(self):
        p = self.rows()["PPEND"]
        self.assertTrue(p["pending"])
        self.assertEqual("hom", p["genotype"]["state"])
        self.assertEqual("no_text_for_state", p["pending_why"])
        self.assertTrue(any(q["origin"] == "pending" and q["rsid"] == "rsPPEND"
                            for q in SP.system("thyroid")["questions"]["rows"]))

    def test_a_risk_allele_nobody_named_is_not_derived(self):
        p = self.rows()["PNA"]
        self.assertEqual("risk_allele_not_declared", p["genotype"]["state"])
        self.assertTrue(p["read"])
        self.assertEqual("risk_allele", p["pending_why"])
        self.assertTrue(any(q["origin"] == "risk_allele" for q in SP.system("thyroid")["questions"]["rows"]))

    def test_the_absent_phrase_is_the_template_and_names_the_reading(self):
        p = self.rows()["PABS"]
        self.assertEqual("absent", p["genotype"]["state"])
        self.assertIn("PABS rsPABS", p["text"])
        self.assertIn("called", p["text"])
        self.assertIn("30", p["text"])

    def test_a_position_with_no_row_is_unread_and_goes_to_the_genome_basket(self):
        p = self.rows()["PUNR"]
        self.assertIs(False, p["read"])
        self.assertEqual("assumed_ref", p["read_why"])
        basket = SP.system("thyroid")["next"]["genome"]
        self.assertIn("rsPUNR", [x.get("rsid") for x in basket["rows"]])
        self.assertIsNone(basket["empty_why"])

    def test_an_expect_on_a_marker_never_taken_is_a_gap_not_a_disagreement(self):
        """Never a disagreement, and since 13.09.2026 never a question of its
        own when the marker already stands in «never taken»: the positions that
        wait on it are named inside that one question."""
        qs = SP.system("thyroid")["questions"]["rows"]
        self.assertFalse(any(q["origin"] == "expect" for q in qs))
        gap = [q for q in qs if q["origin"] == "gap" and "tsh" in (q["data"].get("waiting") or {})]
        standalone = [q for q in qs if q["origin"] == "expect_gap" and q["marker"] == "tsh"]
        self.assertEqual(1, len(gap) + len(standalone),
                         "the expectation on TSH is asked once — folded into the gap, or alone")

    def _three_waiting_on_tsh(self, tests_layer=None):
        cur = {"_meta": CURATED["_meta"], "systems": {"thyroid": {"source": "the author", "positions": [
            _pos("rsPL", "PL", expect={"marker": "tsh", "direction": "higher"}),
            _pos("rsPAR", "PAR", expect={"marker": "tsh", "direction": "lower"}),
            _pos("rsPEXP", "PEXP", expect={"marker": "tsh", "direction": "higher"})]}}}
        patches = [mock.patch.object(SP, "_base", lambda: {}),
                   mock.patch.object(SP, "_curated", lambda: cur),
                   mock.patch("scholion.genome.available", lambda: {"ready": True}),
                   mock.patch.object(core, "loci", lambda: LOCI),
                   mock.patch("scholion.genome.lookup", _lookup)]
        if tests_layer is not None:
            patches.append(mock.patch.object(SP, "_tests_layer", tests_layer))
        for pt in patches:
            pt.start()
        try:
            return SP.system("thyroid")["questions"]["rows"]
        finally:
            for pt in reversed(patches):
                pt.stop()

    def test_several_positions_waiting_on_one_untaken_marker_make_one_question(self):
        """13.09.2026: the lipid card of a profile with no labs asked «take LDL»
        five times, once per position, beside a sixth question saying the same.
        One marker, one question; every waiting position named in it."""
        qs = self._three_waiting_on_tsh()
        mentioning = [q for q in qs if any(f"{g} rs{g}" in q["text"] for g in ("PL", "PAR", "PEXP"))]
        self.assertEqual(1, len(mentioning), [q["origin"] for q in mentioning])
        (q,) = mentioning
        self.assertEqual("gap", q["origin"])
        # In the card's own row order (by gene), not in the order they were written.
        self.assertEqual(["PAR rsPAR", "PEXP rsPEXP", "PL rsPL"], q["data"]["waiting"]["tsh"])
        self.assertFalse(any(x["origin"] == "expect_gap" for x in qs))

    def test_when_a_rule_already_asks_for_the_marker_the_positions_still_share_one_question(self):
        fired = lambda markers: {"status": "ok", "rows": [{"id": "r", "markers_hit": ["tsh"]}], "empty_why": None}
        qs = self._three_waiting_on_tsh(tests_layer=fired)
        eg = [q for q in qs if q["origin"] == "expect_gap"]
        self.assertEqual(1, len(eg))
        self.assertEqual("tsh", eg[0]["marker"])
        self.assertEqual(["PAR rsPAR", "PEXP rsPEXP", "PL rsPL"], eg[0]["positions"])
        self.assertTrue(eg[0]["text"].rstrip().endswith("?"))
        self.assertFalse(any("tsh" in (q.get("markers") or []) for q in qs if q["origin"] == "gap"))

    def test_a_system_with_an_unread_row_is_never_clear_measured(self):
        cur = json.loads(json.dumps(CURATED))
        keep = ("PABS", "PUNR")
        cur["systems"]["thyroid"]["positions"] = [p for p in cur["systems"]["thyroid"]["positions"]
                                                  if p["gene"] in keep]
        with mock.patch.object(SP, "_base", lambda: {}), \
             mock.patch.object(SP, "_curated", lambda: cur):
            v = SP.system("thyroid")["verdict"]
        self.assertEqual("clear_partial", v["kind"])
        self.assertEqual(1, v["unread"])
        self.assertEqual(2, v["total"])

    def test_clear_measured_only_when_every_row_was_read(self):
        cur = json.loads(json.dumps(CURATED))
        cur["systems"]["thyroid"]["positions"] = [p for p in cur["systems"]["thyroid"]["positions"]
                                                  if p["gene"] == "PABS"]
        with mock.patch.object(SP, "_base", lambda: {}), \
             mock.patch.object(SP, "_curated", lambda: cur):
            v = SP.system("thyroid")["verdict"]
        self.assertEqual("clear_measured", v["kind"])


class TestTheTwoRegisters(_State):

    def test_the_registers_differ_in_density_and_not_in_verdict(self):
        pt, cl = SP.system("thyroid", "patient"), SP.system("thyroid", "clinician")
        self.assertEqual(pt["verdict"], cl["verdict"])
        self.assertEqual(pt["verdict_line"], cl["verdict_line"])
        self.assertLess(len(pt["genetics"]["rows"]), len(cl["genetics"]["rows"]))
        self.assertTrue(all("genotype" in r for r in cl["genetics"]["rows"] if r["unit"] == "position"))
        self.assertTrue(all("assertions" not in r for r in pt["genetics"]["rows"]))
        self.assertEqual(pt["genetics"]["finding_count"], cl["genetics"]["finding_count"])

    def test_an_unknown_register_is_refused_by_name_with_the_two_listed(self):
        """Refused, not defaulted: until 12.09.2026 «editor» was served the
        patient's card under its own name through the HTTP and tool doors,
        where argparse's `choices` does not stand."""
        out = SP.system("thyroid", "editor")
        self.assertEqual("unknown_register", out["status"])
        self.assertEqual("editor", out["register"])
        self.assertEqual(["patient", "clinician"], out["registers"])
        self.assertNotIn("labs", out, "a refusal carries no card")
        from scholion import format as fmt
        line = fmt.system_report(out)
        self.assertIn("editor", line)
        self.assertIn("clinician", line)


class TestGeneticsNeverTouchesTheScore(unittest.TestCase):

    def test_changing_the_genetic_layer_leaves_the_score_where_it_was(self):
        with mock.patch.object(SP, "_base", lambda: {}), mock.patch.object(SP, "_curated", lambda: {}):
            before = SP.system("glucose")
        loud = {"_meta": {"export_last_modified": "x"},
                "systems": {"glucose": {"genes": {"GX": {"submissions": [_sub("Definitive", "AD")]}}}}}
        with mock.patch.object(SP, "_base", lambda: loud), \
             mock.patch.object(SP, "_curated", lambda: {}), \
             mock.patch("scholion.genome.available", lambda: {"ready": True}), \
             mock.patch.object(core, "loci", lambda: LOCI), \
             mock.patch("scholion.genome.lookup", _lookup), \
             mock.patch.object(SP, "_clinvar_by_gene",
                               lambda scan: {"status": "ok", "by_gene": {"GX": [{"zygosity": "hom"}]}}):
            after = SP.system("glucose")
        self.assertNotEqual(before["verdict"]["kind"], after["verdict"]["kind"],
                            "the genetic layer did not change — the test proves nothing")
        self.assertEqual("finding", after["verdict"]["kind"])
        self.assertEqual(before["labs"]["score"], after["labs"]["score"])
        self.assertEqual(before["labs"], after["labs"])
        self.assertEqual(before["dynamics"], after["dynamics"])


class TestTheShippedFilesAnswerForEverySystem(unittest.TestCase):

    def test_every_laboratory_system_is_composed_and_fitness_has_no_half(self):
        """Since 13.09.2026 (task 178) every laboratory system carries a
        genetic half composed from the base — eleven that day, twelve since
        «Heart and vessels» joined the radar later the same day (task 179);
        the day before, ten said `not_composed` with a reason, and that answer
        is still the one an empty base produces (tested with a mocked base
        elsewhere)."""
        for d in SP.domains():
            with self.subTest(system=d["key"]):
                r = SP.system(d["key"])
                g = r["genetics"]
                if d["key"] == "fitness":
                    self.assertEqual("no_genetic_half", g["status"])
                    self.assertEqual("no_genetic_half", r["verdict"]["why"])
                else:
                    self.assertEqual("composed", g["status"])
                    self.assertGreater(g["base"]["genes"], 0)
                    self.assertTrue(g["base"]["version"])
                    if d["key"] == "thyroid":
                        self.assertEqual(38, g["base"]["genes"])
                self.assertNotIn("⟦", r["verdict_line"])
                for basket in SP.BASKETS:
                    b = r["next"][basket]
                    self.assertTrue(b["rows"] or b["empty_why"],
                                    f"{d['key']}/{basket}: an empty basket with no reason")

    def test_no_genetic_half_and_an_empty_list_are_different_answers(self):
        fit, lip = SP.system("fitness"), SP.system("lipids")
        self.assertNotEqual(fit["genetics"]["status"], lip["genetics"]["status"])
        self.assertNotEqual(fit["verdict_line"], lip["verdict_line"])

    def test_the_real_base_shows_disagreeing_submitters_and_its_date(self):
        r = SP.system("thyroid", "clinician")
        # The gene-unit row: the TG positions of the clinician's panel stand
        # beside it since 13.09.2026 and carry no assertions of their own.
        tg = [x for x in r["genetics"]["rows"] if x["gene"] == "TG" and x["unit"] == "gene"][0]
        self.assertGreaterEqual(len(tg["assertions"]), 2)
        self.assertIn("Limited", tg["classifications"])
        self.assertIn("Strong", tg["classifications"])
        meta = json.loads(core.knowledge_path("gencc_gene_disease.json").read_text(encoding="utf-8"))["_meta"]
        self.assertEqual(meta["export_last_modified"], r["genetics"]["base"]["version"])

    def test_every_system_key_of_the_three_files_is_a_domain(self):
        keys = {d["key"] for d in SP.domains()}
        for name in ("system_gene_panels.json", "gencc_gene_disease.json", "system_disease_terms.json"):
            data = json.loads(core.knowledge_path(name).read_text(encoding="utf-8"))
            with self.subTest(file=name):
                self.assertTrue(set(data.get("systems") or {}) <= keys,
                                f"{name} names a system the radar does not have")

    def test_the_shipped_panels_pass_their_own_gate_in_every_system(self):
        """Until 13.09.2026 the file shipped empty; the segment panels agreed by
        the owner that day (task 179) fill twelve systems. Every row goes
        through the gate — a source, a mode the engine knows, a classification
        with an inheritance for a monogenic row, an effect size for a common
        variant — and nothing is refused; the three genes short reads cannot
        read are named as such and never counted as read."""
        book = SP._curated()
        systems = book.get("systems") or {}
        self.assertEqual(12, len(systems))
        total = 0
        for key, spec in systems.items():
            with self.subTest(system=key):
                g = SP.system(key, "clinician")["genetics"]
                self.assertEqual(0, g["refused"]["total"], g["refused"])
                pos = [r for r in g["rows"] if r["unit"] == "position"]
                self.assertEqual(len(spec.get("positions") or []), len(pos))
                total += len(pos)
                for r in pos:
                    self.assertTrue(r.get("source"), f"{key}/{r.get('rsid')}: no source")
                    self.assertIn(r.get("mode"), SP.MODES)
                # The panel stands before the base list.
                units = [r["unit"] for r in g["rows"]]
                self.assertEqual(units, sorted(units, key=lambda u: u != "position"))
                for u in spec.get("unreadable") or {}:
                    self.assertIn(u, [x["gene"] for x in g["unreadable"]])
                    for r in g["rows"]:
                        if r["unit"] == "gene" and r["gene"] == u.upper():
                            self.assertFalse(r["read"]); self.assertEqual("separate_method", r["read_why"])
        self.assertGreater(total, 80)
        self.assertEqual({"adrenals": ["CYP21A2"], "gonads": ["AR (CAG repeat)"], "liver": ["UGT1A1*28"]},
                         {k: list(v["unreadable"]) for k, v in systems.items() if v.get("unreadable")})
        (comt,) = [r for r in systems["adrenals"]["positions"] if r["rsid"] == "rs4680"]
        self.assertEqual(("COMT", "pgx", "asked_about", "A"), (comt["gene"], comt["mode"], comt["kind"], comt["risk_allele"]))
        meta = book.get("_meta") or {}
        for key in ("why_empty", "gate", "pending", "kind_is_hers_too", "registers", "modes",
                    "limited_is_not_a_finding", "moi_changes_the_heterozygote",
                    "common_variant_only_as_score", "absent_template", "exclusions", "unreadable"):
            self.assertIn(key, meta)
        self.assertTrue(meta["absent_template"]["text"])

    def test_the_index_from_the_genome_side_names_the_systems(self):
        idx = SP.genes_index()
        self.assertEqual(["thyroid"], idx.get("TPO"))

    def test_the_listing_says_what_each_system_holds(self):
        s = SP.systems()
        by = {r["key"]: r for r in s["systems"]}
        # 12 until 13.09.2026; 13 since «Heart and vessels» was added (task 179).
        self.assertEqual(13, s["count"])
        self.assertEqual("composed", by["thyroid"]["genetics"]["status"])
        self.assertEqual("composed", by["cardio"]["genetics"]["status"])
        self.assertEqual("no_genetic_half", by["fitness"]["genetics"]["status"])
        self.assertEqual("composed", by["lipids"]["genetics"]["status"])
        self.assertGreater(by["renal"]["genetics"]["base_genes"], by["growth"]["genetics"]["base_genes"])
        self.assertEqual({"en", "ru"}, set(by["thyroid"]["labels"]))

    def test_an_unknown_system_is_named_rather_than_empty(self):
        r = SP.system("spleen")
        self.assertEqual("unknown_system", r["status"])
        self.assertIn("thyroid", r["systems"])


class TestTheBasketsAndTheQuestions(unittest.TestCase):

    RULE = {"rules": [{"id": "g_rule", "when": {"marker": "glucose", "op": ">", "value": 0},
                       "suggest": "s", "why": "w", "priority": "high", "covers": ["hba1c"]}]}

    def test_a_rule_fired_on_a_system_marker_lands_in_lab_and_not_in_ask(self):
        with mock.patch.object(core, "test_rules", lambda: self.RULE):
            r = SP.system("glucose")
        self.assertEqual(["g_rule"], [x["id"] for x in r["tests"]["rows"]])
        self.assertEqual(["g_rule"], [x.get("id") for x in r["next"]["lab"]["rows"] if x["origin"] == "rule"])
        self.assertFalse(any(x["origin"] == "rule" for x in r["next"]["ask"]["rows"]))
        gap = [q for q in r["questions"]["rows"] if q["origin"] == "gap"]
        self.assertEqual(1, len(gap))
        self.assertNotIn("hba1c", gap[0]["markers"], "a marker a rule covers is not also a gap question")
        self.assertNotIn("glucose", gap[0]["markers"])

    def test_an_expect_on_a_measured_marker_is_a_question_with_the_numbers(self):
        cur = {"systems": {"glucose": {"positions": [
            _pos("rsPEXP", "PEXP", expect={"marker": "glucose", "direction": "higher"})]}}}
        with mock.patch.object(SP, "_base", lambda: {}), \
             mock.patch.object(SP, "_curated", lambda: cur), \
             mock.patch("scholion.genome.available", lambda: {"ready": True}), \
             mock.patch.object(core, "loci", lambda: LOCI), \
             mock.patch("scholion.genome.lookup", _lookup):
            r = SP.system("glucose")
        q = [x for x in r["questions"]["rows"] if x["origin"] == "expect"]
        self.assertEqual(1, len(q))
        self.assertIn(str(q[0]["data"]["value"]), q[0]["text"])
        self.assertIn(q[0]["data"]["position"], ("below", "within", "above", "unknown"))
        self.assertTrue(q[0]["text"].rstrip().endswith("?"), "a question is printed as a question")

    def test_every_empty_basket_names_one_of_the_reasons(self):
        dom = {"key": "x", "source": "labs", "genetic_half": True, "markers": ["a"]}
        gen = {"status": "composed", "rows": [], "scan": {"status": "ok"}}
        n = SP._next(dom, gen, {"missing": [], "stale": []}, {"rows": []},
                     {"rows": [], "empty_why": "nothing_open"})
        self.assertEqual("all_measured_no_rule", n["lab"]["empty_why"])
        self.assertEqual("all_read", n["genome"]["empty_why"])
        self.assertEqual("nothing_open", n["ask"]["empty_why"])
        n = SP._next(dom, gen, {"missing": ["a"], "stale": []}, {"rows": []}, {"rows": []})
        self.assertEqual("gaps_are_questions", n["lab"]["empty_why"])
        n = SP._next(dict(dom, source="wearables"), {"status": "no_genetic_half", "rows": []},
                     {"missing": []}, {"rows": []}, {"rows": []})
        self.assertEqual("no_lab_half", n["lab"]["empty_why"])
        self.assertEqual("no_genetic_half", n["genome"]["empty_why"])
        n = SP._next(dom, {"status": "composed", "rows": [], "scan": {"status": "not_ready"}},
                     {"missing": []}, {"rows": []}, {"rows": []})
        self.assertEqual("scan_not_run", n["genome"]["empty_why"])
        for why in ("all_measured_no_rule", "all_read", "nothing_open", "gaps_are_questions",
                    "no_lab_half", "no_genetic_half", "scan_not_run", "no_genetic_panel"):
            for cat in (en.MESSAGES, ru.MESSAGES):
                self.assertIn("system.why." + why, cat)

    def test_a_stale_marker_goes_to_the_lab_basket(self):
        dom = {"key": "x", "source": "labs", "genetic_half": True, "markers": ["a"]}
        n = SP._next(dom, {"status": "not_composed", "rows": []},
                     {"missing": [], "stale": [{"key": "a", "name": "A", "date": "2020-01"}]},
                     {"rows": []}, {"rows": []})
        self.assertEqual(["stale"], [x["origin"] for x in n["lab"]["rows"]])
        self.assertIn("2020-01", n["lab"]["rows"][0]["text"])


class TestTheAddressOfAPosition(unittest.TestCase):

    def test_a_refseq_snv_becomes_a_locus_and_an_indel_does_not(self):
        loc = SP._loc_from_hgvs("NC_000014.9:g.80203237T>C", "rs225014", "DIO2")
        self.assertEqual({"chrom": "14", "pos": 80203237, "ref": "T", "alt": "C"},
                         {k: loc[k] for k in ("chrom", "pos", "ref", "alt")})
        self.assertEqual("X", SP._loc_from_hgvs("NC_000023.11:g.5A>G", "r", "g")["chrom"])
        self.assertIsNone(SP._loc_from_hgvs("NC_000009.12:g.89328754del", "r", "g"))
        self.assertIsNone(SP._loc_from_hgvs("", "r", "g"))

    def test_a_reference_call_is_hom_when_the_named_allele_is_the_reference(self):
        with mock.patch("scholion.genome.lookup",
                        lambda rsid=None, gene=None: {"status": "ok", "result": {"confidence": "confirmed_ref", "depth": 20}}):
            g = SP._genotype("rsX", "NC_000001.11:g.100A>G", "G", "A", {"status": "ok"})
            self.assertEqual("hom", g["state"])
            g = SP._genotype("rsX", "NC_000001.11:g.100A>G", "G", "G", {"status": "ok"})
            self.assertEqual("absent", g["state"])
            g = SP._genotype("rsX", "NC_000001.11:g.100A>G", "G", None, {"status": "ok"})
            self.assertEqual("risk_allele_not_declared", g["state"])


class TestTheWordsAreQuestionsNotOrders(unittest.TestCase):

    def test_every_question_key_exists_in_both_languages_and_asks(self):
        keys = [k for k in en.MESSAGES if k.startswith("system.q.")]
        self.assertGreaterEqual(len(keys), 6)
        for k in keys:
            with self.subTest(key=k):
                self.assertIn(k, ru.MESSAGES)
                self.assertTrue(en.MESSAGES[k].rstrip().endswith("?")
                                or "decision" in en.MESSAGES[k])
                first = en.MESSAGES[k].split()[0].lower().strip("{}")
                self.assertNotIn(first, ("start", "stop", "take", "increase", "reduce", "cancel"))

    def test_every_system_key_is_in_both_catalogues(self):
        mine = [k for k in en.MESSAGES if k.startswith("system.")]
        self.assertTrue(mine)
        for k in mine:
            with self.subTest(key=k):
                self.assertIn(k, ru.MESSAGES)


if __name__ == "__main__":
    unittest.main()
