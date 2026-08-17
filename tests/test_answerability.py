"""A value may not be presented without its evidential status.

This is the invariant the audit of v2.4.0 named as the single cause behind most
of its findings: the data layer computes a status, the decision layer receives
only the value, the output layer prints the value as a fact. The failures it
produced were clinical, not cosmetic — the strongest of them being that
CONNECTING A GENOME made the answer less cautious than having none.

What is fixed here is the pharmacogenetic half of the chain. Each test is named
after the failure it prevents rather than after the function it calls, because
the function will be refactored and the failure must not come back with it.

Every case runs through public entry points on a throwaway synthetic profile —
never on anyone's real one, and never on internal helpers, so that the guarantees
survive a rewrite of the internals.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support


def _model_markers(gene):
    """The rsIDs the interpretation model uses for a gene, read from the catalogue."""
    import json
    kb = json.loads((support.ROOT / "src" / "scholion" / "knowledge"
                     / "cpic_drug_gene.json").read_text(encoding="utf-8"))
    return [m["rsid"] for m in kb["genes"][gene]["markers"]]


def _profile(genotypes=None, medications=None):
    """A synthetic profile directory; removed in tearDown."""
    d = Path(tempfile.mkdtemp(prefix="answerability_"))
    (d / "pharmacogenomics.json").write_text(json.dumps(
        {"meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
         "genotypes": genotypes or []}, ensure_ascii=False), encoding="utf-8")
    (d / "medications.json").write_text(json.dumps(
        {"meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
         "medications": medications or []}, ensure_ascii=False), encoding="utf-8")
    (d / "labs.json").write_text(json.dumps(
        {"meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
         "markers": {}}, ensure_ascii=False), encoding="utf-8")
    return d


class _Base(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def profile(self, **kw):
        d = _profile(**kw)
        self._dirs.append(d)
        return d


class TestUnknownIsNotGreen(_Base):
    """An input that was never measured may not read as a reassuring answer."""

    def test_a_drug_check_without_any_genotype_is_not_low(self):
        """The five drugs whose catalogue `default` said `low`.

        A person with no genotype at all was told, on the gene that matters for
        that drug, that there was nothing to see. Azathioprine was among them —
        TPMT deficiency is the classic thiopurine myelotoxicity gene.
        """
        p = self.profile()
        for drug in ("azathioprine", "voriconazole", "omeprazole",
                     "citalopram", "methotrexate", "capecitabine"):
            with self.subTest(drug=drug):
                r = support.run_json(["drug", drug], profile_dir=p)
                self.assertEqual(r.get("phenotype"), "unknown",
                                 "the fixture is meant to have no genotype at all")
                self.assertNotEqual(
                    r.get("level"), "low",
                    f"«{drug}»: no genotype was read, and the answer still came out low")

    def test_the_wording_does_not_claim_a_finding_either(self):
        """Half of the fix is worthless: the field and the prose must agree.

        The catalogue's `default` note for voriconazole reads "no features have
        been found by the markers". Said to somebody whose markers were never
        read, that is the same defect one layer down — and this project has the
        opposite failure on record too, honest prose beside a green field.
        """
        p = self.profile()
        r = support.run_json(["drug", "voriconazole"], profile_dir=p)
        text = (r.get("recommendation") or "").lower()
        self.assertIn("not determined", text,
                      "the answer does not say that the phenotype was never determined")

    def test_a_verdict_is_lifted_off_low_and_says_why(self):
        """The one condition behind five of the six clinical failures.

        `check_new_prescription` summed only `high` and `moderate`, so `unknown`
        contributed nothing and the verdict came out green. Lifting it is not
        enough on its own: a raised verdict with no stated reason leaves the
        reader guessing which input is missing, so the reason is required to be
        machine-readable rather than only in the prose.
        """
        p = self.profile()
        r = support.run_json(["prescription", "voriconazole"], profile_dir=p)
        self.assertNotEqual(r.get("overall"), "low")
        kinds = {u.get("what") for u in (r.get("unresolved") or [])}
        self.assertIn("pharmacogenetics", kinds,
                      "the verdict was raised, but nothing says the genotype is missing")

    def test_a_determined_phenotype_still_gives_a_definite_answer(self):
        """The reverse test, and the reason it is here.

        A change after which the system refuses more often than it should is as
        wrong as the state it replaced. A carrier of a CYP2C19 loss-of-function
        allele on clopidogrel is a case where the catalogue has a real
        recommendation, and it must come out as one.
        """
        p = self.profile(genotypes=[{"gene": "CYP2C19", "rsid": "rs4244285",
                                     "genotype": "GA"}])
        r = support.run_json(["drug", "clopidogrel"], profile_dir=p)
        self.assertEqual(r.get("phenotype"), "IM")
        self.assertEqual(r.get("level"), "high",
                         "a real recommendation for a determined phenotype was lost")
        self.assertFalse(r.get("guidance_gap"))


class TestTheCatalogueSilenceIsNotAnAnswer(_Base):
    """A phenotype the catalogue says nothing about is reported as such."""

    def test_a_phenotype_without_its_own_entry_is_named_a_gap(self):
        """Voriconazole has UM, RM, PM and `default` — and no IM, NM or unknown.

        So a carrier of a loss-of-function allele, a normal metaboliser and a
        person with no data received one and the same sentence. The catalogue's
        silence about a phenotype was printed as a statement about the patient.
        """
        p = self.profile(genotypes=[{"gene": "CYP2C19", "rsid": "rs4244285",
                                     "genotype": "GA"}])
        r = support.run_json(["drug", "voriconazole"], profile_dir=p)
        self.assertEqual(r.get("phenotype"), "IM")
        self.assertTrue(r.get("guidance_gap"),
                        "the missing entry is not reported as a gap in the reference data")
        self.assertNotEqual(r.get("level"), "low")

    def test_the_carrier_and_the_unmeasured_do_not_get_one_answer(self):
        """The failure as a reader would meet it: two different people, two answers."""
        carrier = support.run_json(
            ["drug", "voriconazole"],
            profile_dir=self.profile(genotypes=[{"gene": "CYP2C19",
                                                 "rsid": "rs4244285", "genotype": "GA"}]))
        nobody = support.run_json(["drug", "voriconazole"], profile_dir=self.profile())
        self.assertNotEqual(carrier.get("recommendation"), nobody.get("recommendation"),
                            "a carrier and a person with no data are told the same thing")


class TestTheTableBelongsToTheDrug(_Base):
    """A recommendation table is keyed by (drug, gene), never by the gene."""

    def test_a_proton_pump_inhibitor_does_not_get_the_clopidogrel_table(self):
        """Not merely somebody else's table — an inverted one.

        The lookup took the first catalogue record with a matching gene, and for
        CYP2C19 that is clopidogrel. For a PPI a reduced CYP2C19 function means
        MORE exposure, not an insufficient effect, so the screen advised a
        platelet function test about omeprazole.
        """
        p = self.profile(genotypes=[{"gene": "CYP2C19", "rsid": "rs4244285",
                                     "genotype": "GA"}])
        ppi = support.run_json(["drug", "esomeprazole"], profile_dir=p)
        clopidogrel = support.run_json(["drug", "clopidogrel"], profile_dir=p)

        self.assertEqual(ppi.get("gene"), "CYP2C19")
        self.assertEqual(ppi.get("phenotype"), "IM")
        self.assertNotEqual(
            ppi.get("recommendation"), clopidogrel.get("recommendation"),
            "the proton pump inhibitor is answered out of the clopidogrel table")
        self.assertEqual(ppi.get("level"), "low",
                         "the PPI's own table says the standard approach applies at IM")


class TestAnEmptyBaselineSaysSo(_Base):
    """"Nothing found" and "nothing to compare against" are different answers."""

    def test_no_prescriptions_is_not_a_clean_interaction_check(self):
        """The state of every fresh install, before the first `add-med`.

        The answer "no interactions with your current prescriptions" was
        byte-identical for a person on five drugs and for a person on none — and
        the second of those is the moment somebody is most likely to try the
        feature.
        """
        empty = support.run_json(["prescription", "clopidogrel"],
                                 profile_dir=self.profile())
        loaded = support.run_json(
            ["prescription", "clopidogrel"],
            profile_dir=self.profile(medications=[{"name": "omeprazole", "dose": "20 mg"}]))

        self.assertTrue((empty.get("interactions") or {}).get("baseline", {}).get("empty"),
                        "an empty prescription list is not reported as empty")
        self.assertFalse((loaded.get("interactions") or {}).get("baseline", {}).get("empty"))
        self.assertIn("interactions",
                      {u.get("what") for u in (empty.get("unresolved") or [])},
                      "there was nothing to compare against, and the answer does not say so")


class TestTheReasonReachesTheReader(_Base):
    """A field that never reaches the render does not exist."""

    def test_the_unresolved_block_is_printed(self):
        """Checked on the rendered text, not on the structure.

        This project has a standing rule that a computed qualifier which stops
        before the output layer is not an implementation. `unresolved` was added
        to answer the verdict question, so it is required to be visible in the
        channel a person actually reads.
        """
        code, out, err = support.run(["prescription", "voriconazole"],
                                     profile_dir=self.profile())
        self.assertEqual(code, 0, err)
        self.assertIn("Not determined", out,
                      "the reason the verdict was raised never reaches the report")


class TestUnknownIsAnInstructionNotAVerdict(_Base):
    """"Not determined" has to say what is there, what is missing, and what closes it.

    The owner's rule, and the reason the rest of this file exists: a reader can
    act on "one of two markers was read, rs12248560 (*17) was not, and a full VCF
    closes it". Nobody can act on the word "unknown". Where an answer can still be
    given from part of the panel it IS given — marked as assumed, with what would
    make it certain — because throwing away real information is its own kind of
    dishonesty.
    """

    def test_it_names_what_was_read_and_what_was_not(self):
        r = support.run_json(["drug", "clopidogrel"], profile_dir=self.profile())
        note = r.get("recommendation") or ""
        self.assertIn("rs4244285", note, "the missing marker is not named")
        self.assertIn("rs12248560", note)
        basis = r.get("basis") or {}
        # Counted from the catalogue, not written here: the model grows, and a
        # test pinned to yesterday's number fails for the wrong reason.
        self.assertEqual(basis.get("total"), len(_model_markers("CYP2C19")))
        self.assertEqual(basis.get("read"), [])
        self.assertEqual({m["rsid"] for m in basis["missing"]}, set(_model_markers("CYP2C19")))
        self.assertTrue(all(m["obtainable"] for m in basis["missing"]),
                        "the answer does not know these are obtainable from the person's own data")

    def test_it_says_what_would_close_the_gap(self):
        r = support.run_json(["drug", "clopidogrel"], profile_dir=self.profile())
        self.assertIn("VCF", r.get("recommendation") or "",
                      "nothing tells the reader how to obtain what is missing")

    def test_it_admits_what_even_a_full_vcf_would_not_close(self):
        """Where the panel IS narrower than the catalogue, the answer says so.

        Promising that a VCF closes everything would be the comfortable answer
        and the false one. CYP2C19 used to be the example — rs4986893 sat in
        loci.json and not in the model — and was repaired; MTHFR/rs1801131 is the
        case that remains, deliberately, and is recorded in the integrity test.
        """
        from scholion import engine
        basis = engine.compute_phenotype("MTHFR").get("basis") or {}
        self.assertIn("rs1801131", basis.get("not_modelled") or [],
                      "an allele the catalogue knows and the model ignores is not reported")
        r = support.run_json(["drug", "methotrexate"], profile_dir=self.profile())
        self.assertIn("rs1801131", r.get("recommendation") or "")

    def test_a_partial_panel_answers_and_marks_the_answer(self):
        p = self.profile(genotypes=[{"gene": "CYP2C19", "rsid": "rs4244285",
                                     "genotype": "GA"}])
        r = support.run_json(["drug", "clopidogrel"], profile_dir=p)
        self.assertEqual(r.get("phenotype"), "IM", "a usable answer was thrown away")
        self.assertEqual(r.get("certainty"), "assumed")
        self.assertIn("ASSUMED", r.get("phenotype_label") or "",
                      "an assumed phenotype is presented as a determined one")
        self.assertIn("rs12248560", r.get("recommendation") or "")

    def test_a_full_panel_carries_no_hedging(self):
        """The reverse: certainty must not be diluted where it exists."""
        p = self.profile(genotypes=[{"gene": "CYP2C19", "rsid": rs, "genotype": "GG"}
                                    for rs in _model_markers("CYP2C19")])
        r = support.run_json(["drug", "clopidogrel"], profile_dir=p)
        self.assertEqual(r.get("certainty"), "determined")
        self.assertNotIn("ASSUMED", r.get("phenotype_label") or "")
        self.assertNotIn("not read", r.get("recommendation") or "")

    def test_the_verdict_reports_the_gap_even_when_it_also_has_a_finding(self):
        """A graded concern and a missing input are not alternatives.

        Clopidogrel with no genotype returns `moderate` from its catalogue
        default — a real recommendation — while the phenotype is still unknown.
        Reporting only the first left the reader with a raised verdict and no
        sight of the one thing they could act on.
        """
        r = support.run_json(["prescription", "clopidogrel"], profile_dir=self.profile())
        kinds = {u.get("what") for u in (r.get("unresolved") or [])}
        self.assertIn("pharmacogenetics", kinds)
        pgx = next(u for u in r["unresolved"] if u["what"] == "pharmacogenetics")
        self.assertTrue(pgx.get("closable"))
        self.assertIn("rs4244285", pgx.get("missing") or [])


GENOME_FIXTURE = support.ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz"


@unittest.skipUnless(GENOME_FIXTURE.exists(), "the tiny VCF fixture is not part of this build")
class TestConnectingAGenomeCannotMakeTheAnswerLessCautious(_Base):
    """The strongest finding of the audit, as an acceptance test.

    A person with a full VCF connected, whose DPYD positions were never called,
    used to be told the drug looked normal — while the same person WITHOUT a
    genome was told the status was unknown and the test was mandatory before any
    fluoropyrimidine. Connecting more data made the answer less cautious, and it
    did so on the one gene where the mistake is measured in deaths.

    Two links produced it. `core.genotype_at` returned a bare string, so
    `assumed_ref` — "no row at this position: either the reference or no coverage"
    — arrived downstream as a measured genotype. And `genome_gaps` closed a gene
    when the FILE existed and the coordinates were in the catalogue, which is a
    statement about two files rather than about the person.

    The fixture is a real VCF, indexed, with one called variant far from any
    pharmacogene and nothing at all at the DPYD positions.
    """

    def _env(self, with_genome):
        if with_genome:
            return {"SCHOLION_GENOME_VCF": str(GENOME_FIXTURE),
                    "SCHOLION_GENOME_DIR": str(GENOME_FIXTURE.parent)}
        return {"SCHOLION_GENOME_VCF": str(support.ROOT / "tests/fixtures/no-such-file.vcf.gz"),
                "SCHOLION_GENOME_DIR": str(support.ROOT / "tests/fixtures/no-genome")}

    def _check(self, with_genome, drug="capecitabine"):
        import os, subprocess, sys, json as _json
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT),
                   SCHOLION_PROFILE_DIR=str(self.profile()))
        env.update(self._env(with_genome))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import engine, core;"
                "r = engine.check_drug_gene(%r);"
                "r['_gaps'] = core.genome_gaps();"
                "print(json.dumps(r, default=str))" % (str(support.SRC), drug))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        return _json.loads(p.stdout.strip().splitlines()[-1])

    _ORDER = {"low": 0, "moderate": 1, "unknown": 2, "high": 3}

    @staticmethod
    def no_less_cautious(without, with_):
        """Did connecting a genome make the answer less cautious? → (ok, why).

        The first version of this compared the two level words by the order
        above, on capecitabine alone. Extend it to azathioprine and it cries
        wolf: the fixture carries a CALLED heterozygous `rs1800462`, so with a
        genome the answer is `moderate` with phenotype IM, and without one it is
        `unknown`. By the order that is `unknown → moderate`, a softening; in
        substance it is the system doing exactly what it should — a real variant
        was read and the answer says so, marked `assumed` because one position of
        the panel is still missing.

        The two shapes need two different invariants, and which one applies is
        decided by the data rather than by the drug:

        * **nothing was read either way** — the words are comparable, and the one
          with more data may not be the calmer one. This is the capecitabine
          case, and the failure it guards against is the audit's strongest
          finding;
        * **something was read** — the words are not comparable, because a
          reading legitimately turns «unknown» into a graded answer. What must
          hold instead is that an incomplete panel is never presented as settled:
          with positions still missing, `certainty` may not be `determined`.

        Kept as a pure function of two records so that the invariant itself can
        be tested on fabricated ones, including a genuine softening — which the
        real engine, now fixed, no longer produces.
        """
        read_with = (with_.get("basis") or {}).get("read") or []
        read_without = (without.get("basis") or {}).get("read") or []
        if not read_with and not read_without:
            ok = (TestConnectingAGenomeCannotMakeTheAnswerLessCautious._ORDER[with_["level"]]
                  >= TestConnectingAGenomeCannotMakeTheAnswerLessCautious._ORDER[without["level"]])
            return ok, (f"nothing was read with or without the genome, and the answer moved "
                        f"{without['level']} → {with_['level']}")
        missing = (with_.get("basis") or {}).get("missing") or []
        if missing:
            return (with_.get("certainty") != "determined",
                    f"{len(missing)} position(s) of the panel were never read, and the answer "
                    f"is presented as «{with_.get('certainty')}»")
        return True, ""

    def test_the_answer_with_a_genome_is_no_less_cautious(self):
        """Both shapes, on the two drugs that produce them."""
        for drug in ("capecitabine", "azathioprine"):
            with self.subTest(drug=drug):
                ok, why = self.no_less_cautious(self._check(False, drug), self._check(True, drug))
                self.assertTrue(ok, f"{drug}: {why}")

    def test_the_invariant_still_refuses_a_real_softening(self):
        """The guard has to be seen failing, or it pins nothing.

        Fabricated records, not the engine: the engine no longer produces this
        shape, and a check that can only be watched passing is indistinguishable
        from one that always passes.
        """
        blind = {"level": "unknown", "basis": {"read": [], "missing": [{"rsid": "rs3918290"}]}}
        softened = {"level": "low", "certainty": "determined",
                    "basis": {"read": [], "missing": [{"rsid": "rs3918290"}]}}
        ok, why = self.no_less_cautious(blind, softened)
        self.assertFalse(ok, "a genome that turned «unknown» into «low» passed the invariant")
        self.assertIn("unknown → low", why)

    def test_the_invariant_refuses_an_incomplete_panel_called_settled(self):
        blind = {"level": "unknown", "basis": {"read": [], "missing": [{"rsid": "rs1800462"}]}}
        overconfident = {"level": "moderate", "certainty": "determined",
                         "basis": {"read": [{"rsid": "rs1800462"}],
                                   "missing": [{"rsid": "rs1142345"}]}}
        ok, _ = self.no_less_cautious(blind, overconfident)
        self.assertFalse(ok, "a panel with an unread position was presented as determined")

    def test_the_invariant_accepts_a_reading_that_grades_the_answer(self):
        """The azathioprine shape, spelled out: this must NOT be read as softening."""
        blind = {"level": "unknown", "basis": {"read": [], "missing": [{"rsid": "rs1800462"}]}}
        graded = {"level": "moderate", "certainty": "assumed",
                  "basis": {"read": [{"rsid": "rs1800462"}], "missing": [{"rsid": "rs1142345"}]}}
        ok, _ = self.no_less_cautious(blind, graded)
        self.assertTrue(ok, "a real reading marked «assumed» was rejected as a softening")

    def test_an_uncalled_position_is_not_a_measured_genotype(self):
        """`assumed_ref` counted as zero variant copies is the whole mechanism."""
        r = self._check(True)
        self.assertEqual(r["phenotype"], "unknown",
                         "a phenotype was computed from positions that were never called")
        self.assertEqual(r["basis"]["read"], [])

    def test_a_gene_is_not_closed_by_the_file_merely_existing(self):
        r = self._check(True)
        self.assertIn("DPYD", r["_gaps"],
                      "the gene left the gap list because a VCF exists, not because it was read")

    def test_the_instruction_matches_which_case_this_is(self):
        """Two different absences, two different remedies.

        With no VCF the answer is to build one. With a VCF whose rows do not
        cover these positions, building another changes nothing — the positions
        have to be genotyped from the BAM, and telling the reader to make a VCF
        would be advice that cannot work.
        """
        without, with_ = self._check(False), self._check(True)
        self.assertIn("full VCF closes this", without["recommendation"])
        self.assertIn("no row in it", with_["recommendation"])
        self.assertNotIn("full VCF closes this", with_["recommendation"])

    def test_a_called_variant_is_still_read_normally(self):
        """The reverse: a position that WAS called must behave like a reading.

        Without this the repair could have degenerated into refusing everything,
        which is as wrong as the state it replaced.
        """
        import os, subprocess, sys, json as _json
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT),
                   SCHOLION_PROFILE_DIR=str(self.profile()), **self._env(True))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import core;"
                "print(json.dumps(core.genotype_status('rs1800462'), default=str))"
                % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=60)
        st = _json.loads(p.stdout.strip().splitlines()[-1] or "null")
        self.assertTrue(st, "the one variant actually present in the fixture was not found")
        self.assertEqual(st["confidence"], "called")


class TestASourceNeverReachedCannotMakeANegativeStatement(_Base):
    """«Nothing was found» and «nobody was asked» are different sentences.

    `net.get_json` turns every failure into `None`, and `cpic_genes` turned that
    `None` into `[]` — the same value the database returns for a drug that
    genuinely has no meaningful pharmacogenetics. Downstream the empty list
    printed «no genes affecting the dose or the effect were found»: a statement
    about a source that had never answered, made with the confidence of one that
    had. The same shape one section lower said no lab monitoring was required for
    a class the catalogue simply has no entry for — nine of the project's 41
    classes, among them SSRI/SNRI, clopidogrel and amiodarone.

    Amiodarone offline is the whole case in one run: classified locally, never
    resolved in RxNorm, absent from the monitoring catalogue. It used to come out
    **green** with three negative statements, none of which had been checked.
    """

    def _check(self, drug="amiodarone"):
        import os, subprocess, sys, json as _json
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT),
                   SCHOLION_PROFILE_DIR=str(self.profile()),
                   SCHOLION_GENOME_VCF=str(support.ROOT / "tests/fixtures/no-such-file.vcf.gz"),
                   SCHOLION_GENOME_DIR=str(support.ROOT / "tests/fixtures/no-genome"))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import engine, format as fmt;"
                "r = engine.check_new_prescription(%r);"
                "print(json.dumps({'r': r, 'text': fmt.prescription_check(r)}, default=str))"
                % (str(support.SRC), drug))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-800:])
        return _json.loads(p.stdout.strip().splitlines()[-1])

    def test_the_database_is_marked_unasked_rather_than_empty(self):
        got = self._check()
        self.assertFalse(got["r"]["genome"]["cpic"]["asked"],
                         "CPIC is reported as answered although the network is off and the drug "
                         "was never resolved to an rxcui")

    def test_the_report_does_not_claim_the_drug_has_no_pharmacogenetics(self):
        text = self._check()["text"]
        self.assertNotIn("no genes affecting the dose", text,
                         "a negative statement about CPIC printed without CPIC having answered")
        self.assertIn("NOT checked against CPIC", text)

    def test_the_report_does_not_claim_no_monitoring_is_needed(self):
        """Amiodarone needs TSH, liver enzymes and an ECG. The catalogue is silent
        about its class, and silence was being printed as a clinical statement."""
        got = self._check()
        self.assertEqual(got["r"]["labs"]["basis"]["with_rules"], [])
        self.assertNotIn("No lab monitoring specific to this class is required", got["text"])
        self.assertIn("no lab-monitoring rule", got["text"])

    def test_neither_absence_leaves_the_verdict_green(self):
        got = self._check()
        self.assertNotEqual(got["r"]["overall"], "low",
                            "the verdict stayed green on two unchecked negatives")
        whats = {u.get("what") for u in got["r"]["unresolved"]}
        self.assertIn("pharmacogenetics", whats)
        self.assertIn("monitoring", whats)

    def test_an_answered_database_still_reads_as_an_answer(self):
        """The reverse: a cached CPIC answer must keep licensing the negative.

        Without this the repair degenerates into never making a statement, which
        is as useless as making an unfounded one.
        """
        import json as _json, os, subprocess, sys, tempfile
        cache = Path(tempfile.mkdtemp(prefix="cpic_cache_"))
        self._dirs.append(cache)
        (cache / "drug_cache.json").write_text(_json.dumps({"cpic:6809": []}), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_CACHE_DIR=str(cache))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import drugsource;"
                "print(json.dumps(drugsource.cpic_lookup('6809')))" % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-600:])
        got = _json.loads(p.stdout.strip().splitlines()[-1])
        self.assertTrue(got["asked"], "a cached CPIC answer was reported as never asked")
        self.assertEqual(got["genes"], [])

    def test_the_reason_says_which_absence_it_was(self):
        """«Offline» and «the drug was never identified» send the reader to
        different actions; one word of difference is the whole value here."""
        self.assertEqual(self._check()["r"]["genome"]["cpic"]["reason"], "not_identified")


class TestAPartlyReadListSaysWhichPartWasNotRead(_Base):
    """A negative statement about interactions may not rest on half the list.

    `baseline` was added so that «no interactions found with your current
    prescriptions» could not be printed for a person who has none. It answered the
    extreme case — `empty` — and nothing between: a list of two, one of them a name
    the dictionary does not recognise, gave `empty: False`, `status: ok` and the
    same flat sentence as a list of two that were both read. The unread half was
    never named, so the reader had no way to know a comparison had been skipped, or
    which drug to name to their doctor.

    Nothing about that is specific to the number two. Every profile assembled by
    hand carries a herbal preparation, a foreign brand or a supplement the class
    dictionary has no entry for, and each one silently shrinks the basis of the
    most consequential sentence the report prints.
    """

    #: A name deliberately outside the class dictionary — a herbal preparation, the
    #: commonest thing to find on a real prescription list and the commonest thing
    #: for a class dictionary to miss.
    UNREAD = "Fitolizin paste"

    def _check(self, meds, drug="metformin"):
        import os, subprocess, sys, json as _json
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1",
                   SCHOLION_LANG="en", SCHOLION_REPO_DIR=str(support.ROOT),
                   SCHOLION_PROFILE_DIR=str(self.profile(medications=meds)),
                   SCHOLION_GENOME_VCF=str(support.ROOT / "tests/fixtures/no-such-file.vcf.gz"),
                   SCHOLION_GENOME_DIR=str(support.ROOT / "tests/fixtures/no-genome"))
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import engine, format as fmt;"
                "r = engine.check_new_prescription(%r);"
                "print(json.dumps({'r': r, 'text': fmt.prescription_check(r)}, default=str))"
                % (str(support.SRC), drug))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-800:])
        return _json.loads(p.stdout.strip().splitlines()[-1])

    def test_the_unread_part_of_the_list_is_carried_in_the_answer(self):
        got = self._check([{"name": "Vitamin D3"}, {"name": self.UNREAD}])
        self.assertEqual(got["r"]["interactions"]["baseline"]["unclassified"], [self.UNREAD])
        self.assertFalse(got["r"]["interactions"]["baseline"]["empty"],
                         "the fixture must be a PARTLY read list, not an empty one — that case "
                         "was already covered and is a different sentence")

    def test_the_reader_is_told_which_drug_was_not_compared(self):
        text = self._check([{"name": "Vitamin D3"}, {"name": self.UNREAD}])["text"]
        self.assertIn(self.UNREAD, text,
                      "the report never names the prescription that took no part in the "
                      "comparison, so the reader cannot tell a full check from a partial one")
        self.assertNotIn("No explicit interactions with the current prescriptions were found",
                         text, "the unconditional sentence is still printed on a partial basis")

    def test_the_verdict_does_not_stay_green_on_a_partial_basis(self):
        got = self._check([{"name": "Vitamin D3"}, {"name": self.UNREAD}])
        self.assertNotEqual(got["r"]["overall"], "low")
        self.assertTrue(any(u.get("what") == "interactions" for u in got["r"]["unresolved"]))

    def test_a_fully_read_list_keeps_the_plain_sentence(self):
        """The repair must not turn every answer into a caveat.

        With every prescription recognised the comparison really did cover the list,
        and the flat sentence is the correct one.
        """
        got = self._check([{"name": "Vitamin D3"}])
        self.assertEqual(got["r"]["interactions"]["baseline"]["unclassified"], [])
        self.assertIn("No explicit interactions with the current prescriptions were found",
                      got["text"])

if __name__ == "__main__":
    unittest.main()
