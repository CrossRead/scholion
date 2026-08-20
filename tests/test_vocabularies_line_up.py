"""A gene's phenotype vocabulary and the tables keyed in it must line up.

This gate exists because of a defect it would have caught the moment it was
introduced. `34d7d39` moved DPYD from hand-written rules to CPIC's activity
score. That changed the vocabulary the model emits — `deficient/intermediate/
normal` became `NM/IM/PM` — and the fluorouracil table stayed keyed in the old
one. Every DPYD lookup then missed its row and fell through to the «no
recommendation in the catalogue» branch: a complete DPD deficiency, the one
finding in this base where a standard dose can kill, answered as an unknown.
619 tests passed throughout, because every test either checked the phenotype or
checked a different drug, and nothing compared the two vocabularies.

So the vocabulary is now declared (`emits` on each gene) and the correspondence
is checked here. The point is not the DPYD row; it is that renaming a model's
output can no longer silently orphan the tables written in its old words.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import core

#: Keys every table may carry whatever the gene emits: the two fall-backs.
_UNIVERSAL = {"unknown", "default"}


class TestGuidanceIsKeyedInItsGenesVocabulary(unittest.TestCase):
    def setUp(self):
        self.kb = core.cpic_kb()

    def test_every_gene_declares_what_it_can_emit(self):
        for gene, gdef in self.kb["genes"].items():
            with self.subTest(gene=gene):
                self.assertTrue(gdef.get("emits"),
                                f"{gene} does not declare the phenotypes its model produces, "
                                "so nothing can check the tables keyed in them")

    def test_no_table_row_is_written_in_a_vocabulary_its_gene_never_speaks(self):
        """An unreachable row is worse than a missing one: it looks like coverage."""
        orphans = []
        for drug in self.kb["drugs"]:
            gene = drug.get("gene")
            emits = set((self.kb["genes"].get(gene) or {}).get("emits") or [])
            if not emits:
                continue
            for key in (drug.get("guidance") or {}):
                if key in _UNIVERSAL or key in emits:
                    continue
                name = drug["names"][1] if len(drug["names"]) > 1 else drug["names"][0]
                orphans.append(f"{name} ({gene}): row «{key}» — {gene} emits {sorted(emits)}")
        self.assertEqual(orphans, [],
                         "guidance rows that no phenotype can ever reach:\n  " +
                         "\n  ".join(orphans))

    def test_a_severe_phenotype_is_never_answered_from_the_gap_branch(self):
        """The consequence, checked end to end rather than structurally.

        A gene that can emit PM must have a PM row in every drug table that names
        it: falling back to «the catalogue has nothing» for the most severe
        phenotype is the specific harm this whole gate is about.
        """
        missing = []
        for drug in self.kb["drugs"]:
            gene = drug.get("gene")
            emits = set((self.kb["genes"].get(gene) or {}).get("emits") or [])
            guidance = drug.get("guidance") or {}
            declared = set((drug.get("guidance_gaps") or {}))
            for severe in ("PM", "low_function", "high_sensitivity"):
                if severe in emits and severe not in guidance and severe not in declared:
                    name = drug["names"][1] if len(drug["names"]) > 1 else drug["names"][0]
                    missing.append(f"{name} ({gene}): no row for {severe}")
        self.assertEqual(missing, [],
                         "the most severe phenotype has no row and would answer as unknown:\n  " +
                         "\n  ".join(missing))

    def test_a_declared_gap_carries_its_reason(self):
        """A row may be missing on purpose. Silence may not: an undeclared absence
        is indistinguishable from an oversight, and this whole series began with
        an oversight that looked like coverage."""
        for drug in self.kb["drugs"]:
            for key, spec in (drug.get("guidance_gaps") or {}).items():
                name = drug["names"][1] if len(drug["names"]) > 1 else drug["names"][0]
                with self.subTest(drug=name, phenotype=key):
                    reason = (spec or {}).get("guidance_gap_reason") if isinstance(spec, dict) else spec
                    self.assertTrue(str(reason or "").strip(),
                                    "a declared gap with no reason recorded")
                    if not key.startswith("__"):
                        self.assertNotIn(key, drug.get("guidance") or {},
                                         "declared as a gap while a row exists — one of the two is wrong")

    def test_the_dpyd_regression_specifically(self):
        """Named, because it shipped. rs3918290 homozygous is complete DPD
        deficiency; fluorouracil at a standard dose can be fatal."""
        import json, os, pathlib, tempfile
        from scholion.engine import pgx
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps(
            {"genotypes": [{"rsid": "rs3918290", "genotype": "TT", "confidence": "called"}]}))
        core.reset_cache()
        try:
            r = pgx.check_drug_gene("5-fu")
            self.assertEqual(r["phenotype"], "PM")
            self.assertFalse(r.get("guidance_gap"),
                             "complete DPD deficiency fell through to the gap branch")
            self.assertEqual(r["level"], "high")
            self.assertIn("Avoid", r["cpic"]["recommendation"])
        finally:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            core.reset_cache()


if __name__ == "__main__":
    unittest.main()
