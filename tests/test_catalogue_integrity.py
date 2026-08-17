"""The knowledge catalogues agree with each other.

A whole class of defect lives here and none of it is architectural: a rule that
names a marker which does not exist, a drug class nobody defined, a gene model
narrower than the project's own locus catalogue. Each is invisible in use —
nothing crashes, the rule simply never fires and the gene simply never contributes
— and each was found by reading rather than by running.

What they have in common is that a machine can check them in a second. That is the
whole argument for this file: the alternative is somebody noticing.

Three found by the audit of v2.4.0 and fixed in the release that brought this
file:

* `dysbiosis_fungal` fired on `tartaric_acid`, a key absent from the whole
  repository. The real one, `oa_tartaric`, sat in the same rule's `covers`, and
  the rule's threshold 8.58 was exactly its `ref_high`. The rule had never once
  fired, silently.
* TPMT was modelled by `*2` alone while `*3C` — the frequent deficient allele —
  sat in the project's own `loci.json`. The model's default label said in words
  that `*3A/*3C` were needed. It knew.
* Amiodarone belonged to no class, so its two real interactions — with warfarin
  and with simvastatin — resolved to "no interactions found".
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import support

K = support.ROOT / "src" / "scholion" / "knowledge"


def _load(name):
    return json.loads((K / name).read_text(encoding="utf-8"))


def _walk(obj, key):
    """Every value stored under `key`, at any depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield from (v if isinstance(v, list) else [v])
            else:
                yield from _walk(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, key)


class TestEveryReferencePointsAtSomething(unittest.TestCase):

    def test_test_rules_name_markers_that_exist(self):
        """A rule naming a marker that does not exist never fires, and says nothing.

        This is worse than a rule that is wrong: a wrong rule argues with you, a
        rule that cannot fire agrees with everything.
        """
        lab = _load("lab_markers.json")
        markers = set(lab.get("markers", lab))
        used = {m for m in _walk(_load("test_rules.json"), "marker") if isinstance(m, str)}
        missing = sorted(used - markers)
        self.assertEqual(missing, [],
                         "test_rules.json names markers absent from lab_markers.json: "
                         + ", ".join(missing))

    def test_covered_markers_exist_too(self):
        lab = _load("lab_markers.json")
        markers = set(lab.get("markers", lab))
        used = {c for c in _walk(_load("test_rules.json"), "covers") if isinstance(c, str)}
        # `covers` occasionally carries a free-text note; only bare keys are checked
        suspect = sorted(c for c in used - markers if " " not in c and c.islower())
        self.assertEqual(suspect, [], "covers names markers that do not exist: " + ", ".join(suspect))

    def test_every_drug_class_used_is_defined(self):
        """An undefined class silently removes a drug from every interaction check."""
        known = set(_load("med_classes.json").get("classes", {}))
        used = set()
        for src in ("test_rules.json", "drug_interactions.json", "drug_lab_monitoring.json"):
            path = K / src
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in ("applies_when_class", "a", "b", "class"):
                used |= {c for c in _walk(data, key) if isinstance(c, str)}
        undefined = sorted(c for c in used - known if c and c.replace("_", "").isalpha())
        self.assertEqual(undefined, [],
                         "a class is used and never defined in med_classes.json: "
                         + ", ".join(undefined))


class TestTheModelIsNotNarrowerThanTheCatalogue(unittest.TestCase):
    """A gene interpreted by fewer alleles than the project already ships.

    The failure this prevents is not a crash but a green light: a true poor
    metaboliser read as normal, because the allele that would have said so was in
    `loci.json` and not in the model.
    """

    #: Alleles knowingly not modelled, with the reason. An entry here is a
    #: decision; an absence from here is an oversight.
    ACCEPTED = {
        # A1298C carries far less weight than C677T and MTHFR is not a CPIC
        # level A gene: adding it would be extending the model, not repairing it.
        ("MTHFR", "rs1801131"),
    }

    def test_every_deficient_allele_is_modelled_or_accepted(self):
        kb = _load("cpic_drug_gene.json")
        loci = _load("loci.json")["loci"]
        gaps = []
        for gene, gdef in (kb.get("genes") or {}).items():
            modelled = {m["rsid"] for m in gdef.get("markers", [])}
            for rsid, entry in loci.items():
                if entry.get("gene") != gene or rsid in modelled:
                    continue
                if (gene, rsid) in self.ACCEPTED:
                    continue
                gaps.append(f"{gene}/{rsid} ({entry.get('star', '?')})")
        self.assertEqual(
            gaps, [],
            "the interpretation model is narrower than the project's own locus "
            "catalogue: " + ", ".join(gaps)
            + " — model them, or record the decision in ACCEPTED with a reason")

    #: The DPYD variants the 2024 joint consensus calls Tier 1 — "must be
    #: included in a clinical DPYD genotyping panel". Written out here, from the
    #: publication, because the invariant above compares the model against OUR
    #: catalogue, and two files can narrow together without either noticing: on
    #: 17.08.2026 both carried the same two variants of seven and the check was
    #: green. A panel measured only against itself always looks complete.
    #:
    #: Source: DPYD Genotyping Recommendations: A Joint Consensus Recommendation
    #: of AMP, ACMG, CPIC, CAP, DPWG, ESPT, PharmGKB and PharmVar.
    #: J Mol Diagn 2024;26(10):851-863. https://pubmed.ncbi.nlm.nih.gov/39032821/
    #: HapB3 is one allele carried by two tags, hence two rsIDs on one row.
    DPYD_TIER_1 = {
        "rs3918290":   "*2A / c.1905+1G>A",
        "rs55886062":  "*13 / c.1679T>G",
        "rs75017182":  "HapB3 / c.1129-5923C>G",
        "rs56038477":  "HapB3 / c.1236G>A",
        "rs115232898": "c.557A>G",
        "rs146356975": "c.868A>G",
        "rs112766203": "c.2279C>T",
        "rs67376798":  "c.2846A>T",
    }

    def test_the_dpyd_panel_covers_tier_1(self):
        """Measured against the outside world, not against ourselves.

        A missing Tier 1 variant is not a smaller answer, it is a wrong one: with
        the variant absent from the model a carrier is reported as having normal
        DPD activity, and the drug in question kills people at full dose.
        """
        kb = _load("cpic_drug_gene.json")
        modelled = {m["rsid"] for m in (kb["genes"].get("DPYD") or {}).get("markers", [])}
        missing = sorted(set(self.DPYD_TIER_1) - modelled)
        self.assertEqual(
            missing, [],
            "the DPYD model does not cover Tier 1 of the 2024 consensus: "
            + ", ".join(f"{r} ({self.DPYD_TIER_1[r]})" for r in missing))

    def test_every_tier_1_variant_has_coordinates(self):
        """Modelled but unlocatable is the same gap one file further on."""
        loci = _load("loci.json")["loci"]
        missing = sorted(r for r in self.DPYD_TIER_1 if r not in loci)
        self.assertEqual(missing, [], "Tier 1 variants absent from loci.json: " + ", ".join(missing))

    def test_hapb3_is_one_allele_carried_by_two_tags(self):
        """Both tags must declare the same haplotype, or the carrier counts twice.

        rs75017182 and rs56038477 travel together. Counted separately, one
        heterozygous carrier yields two decreased-function alleles — activity
        score 1.0 read as 0.0. The phenotype rules do not yet distinguish the
        two, which is the reason to fix it now rather than after they do.
        """
        kb = _load("cpic_drug_gene.json")
        tags = {m["rsid"]: m.get("haplotype")
                for m in kb["genes"]["DPYD"]["markers"]
                if m["rsid"] in ("rs75017182", "rs56038477")}
        self.assertEqual(len(tags), 2, "both HapB3 tags must be modelled")
        self.assertEqual(set(tags.values()), {"HapB3"},
                         f"the HapB3 tags do not share a haplotype: {tags}")

    def test_model_markers_exist_in_the_locus_catalogue(self):
        """The other direction: a model marker with no coordinates cannot be read from a VCF."""
        kb = _load("cpic_drug_gene.json")
        loci = _load("loci.json")["loci"]
        orphan = [f"{g}/{m['rsid']}" for g, d in (kb.get("genes") or {}).items()
                  for m in d.get("markers", []) if m["rsid"] not in loci]
        self.assertEqual(orphan, [], "model markers absent from loci.json: " + ", ".join(orphan))

    def test_the_variant_allele_matches_the_catalogue(self):
        """The allele counted as a variant is the ALT of the same locus.

        Taken from `loci.json` rather than written by hand, because a wrong
        variant allele inverts the phenotype without any other symptom.
        """
        kb = _load("cpic_drug_gene.json")
        loci = _load("loci.json")["loci"]
        wrong = []
        for gene, gdef in (kb.get("genes") or {}).items():
            for m in gdef.get("markers", []):
                alt = (loci.get(m["rsid"]) or {}).get("alt")
                if alt and m.get("variant_allele") and m["variant_allele"] != alt:
                    wrong.append(f"{gene}/{m['rsid']}: model {m['variant_allele']} vs catalogue {alt}")
        self.assertEqual(wrong, [], "; ".join(wrong))


class TestThresholdsDoNotContradictEachOther(unittest.TestCase):

    def test_one_marker_does_not_have_two_different_action_thresholds(self):
        """Two screens in one session disagreeing on one number is worse than either.

        `vit_d_low` sat at 50 ng/mL while `clinical_thresholds.json` and
        `lab_markers.json` agreed on 30 with a citation — and the threshold file
        even explained that 50 is a laboratory's choice rather than an action
        threshold. At 50 the rule fired on almost everybody and therefore carried
        no information.
        """
        rules = _load("test_rules.json")
        thresholds = _load("clinical_thresholds.json").get("markers", {})
        clashes = []
        for rule in rules.get("rules", []):
            when = rule.get("when") or {}
            marker, op, value = when.get("marker"), when.get("op"), when.get("value")
            if not marker or not isinstance(value, (int, float)):
                continue
            for t in thresholds.get(marker, []):
                if t.get("side") == "low" and op == "<" and t.get("value") != value:
                    clashes.append(f"{marker}: rule <{value} vs threshold {t['value']}")
        self.assertEqual(clashes, [], "; ".join(clashes))


class TestTheTestMetadataDescribesTestsThatExist(unittest.TestCase):
    """`lab_test_meta` says HOW to draw a test; `lab_markers` says what the test is.

    They are joined by the marker key and by nothing else, and nothing checked the
    join. Three of the forty-eight entries pointed at keys the marker dictionary
    has never had — `lp_a` (the marker is `lpa`), `testosterone_free` (it is
    `free_testosterone`) and `testosterone_total`, a byte-for-byte duplicate of
    `testosterone` left behind by a rename. Two of the three carried LOINC codes,
    so the codes were attached to tests that do not exist in this system.

    Nothing failed. An orphan is simply never looked up: the draw checklist skips
    the preparation note, the tier and the biomaterial for that test and says
    nothing about having skipped them. The `requires` lists have the same shape —
    `dht` demanded a prerequisite that could never be satisfied, because the key it
    named was not a marker.
    """

    @classmethod
    def setUpClass(cls):
        cls.tests = _load("lab_test_meta.json")["tests"]
        cls.markers = _load("lab_markers.json")["markers"]

    def test_every_described_test_is_a_marker(self):
        orphans = sorted(set(self.tests) - set(self.markers))
        self.assertEqual(orphans, [], "lab_test_meta describes tests the dictionary does not "
                                      "have, so their preparation notes are never printed: "
                                      + ", ".join(orphans))

    def test_every_prerequisite_is_a_marker(self):
        bad = sorted({r for k, v in self.tests.items() for r in (v.get("requires") or [])
                      if r not in self.markers})
        self.assertEqual(bad, [], "a computed index requires a marker that does not exist, so the "
                                  "requirement can never be met: " + ", ".join(bad))

    def test_a_loinc_code_is_not_attached_to_a_test_that_does_not_exist(self):
        coded = {k for k, v in self.tests.items() if v.get("loinc")}
        self.assertEqual(sorted(coded - set(self.markers)), [],
                         "an external identifier is published for a test this system has no "
                         "marker for — the worst kind of orphan, because it looks exportable")

    def test_no_two_entries_are_the_same_test_under_two_names(self):
        """`testosterone` and `testosterone_total` held identical bodies.

        Two names for one test means the checklist can print the same draw twice,
        and a rename can leave one of them behind — which is what happened.
        """
        seen = {}
        dupes = []
        for k, v in self.tests.items():
            sig = json.dumps(v, sort_keys=True, ensure_ascii=False)
            if sig in seen:
                dupes.append(f"{seen[sig]} == {k}")
            seen[sig] = k
        self.assertEqual(dupes, [], "the same test is described twice under different keys: "
                                    + ", ".join(dupes))


if __name__ == "__main__":
    unittest.main()
