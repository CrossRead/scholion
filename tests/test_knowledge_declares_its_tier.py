"""Finding 63: every claim in the knowledge base should say where it came from.

A gate, not a document. Some entries carry a PMID, some are compiled by hand
from a guideline, some are curated reference data — and until now nothing in the
schema told them apart, so a hand-paraphrased CPIC table (findings 33/34/47/48/50)
looked exactly like a verbatim one. Each knowledge file now declares a
machine-readable `source_tier`; this test refuses a file that does not, and
refuses a tier outside the vocabulary. When the verbatim CPIC import lands, its
file moves from `guideline_compiled` to `guideline_verbatim` and the change is
visible here.
"""
from __future__ import annotations

import json
import pathlib
import unittest

import support  # noqa: F401
from scholion import core

KNOWLEDGE = pathlib.Path(core.__file__).resolve().parent / "knowledge"

VALID_TIERS = {
    "guideline_verbatim",    # copied from a primary guideline/authority
    "guideline_compiled",    # hand-compiled from published guidelines — needs verbatim replacement
    # A file can honestly be BOTH. cpic_drug_gene.json carries verbatim phenotype
    # models and verbatim quoted recommendations beside project-written
    # patient-facing notes; calling the whole of it «verbatim» would be a claim
    # that is false of part of it, and «compiled» would understate the part that
    # is now exact. A file using this tier must also carry source_tier_note
    # saying which part is which — enforced below.
    "guideline_mixed",
    "primary_literature",    # from cited primary sources
    "curated_reference",     # project-curated reference data (dictionaries, ranges, tool metadata)
    "derived",               # computed/mechanical
}


class TestEveryKnowledgeFileDeclaresATier(unittest.TestCase):
    def test_a_mixed_tier_must_say_which_part_is_which(self):
        """«Mixed» without the breakdown is just a vaguer claim, not an honest one."""
        import glob, json, os
        for f in glob.glob("src/scholion/knowledge/*.json"):
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            meta = (d.get("_meta") or {}) if isinstance(d, dict) else {}
            if meta.get("source_tier") == "guideline_mixed":
                self.assertTrue(meta.get("source_tier_note"),
                                f"{os.path.basename(f)}: mixed tier with no breakdown")

    def test_all_meta_files_carry_a_valid_source_tier(self):
        missing, bad = [], []
        for p in sorted(KNOWLEDGE.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict) or "_meta" not in d:
                continue
            tier = (d["_meta"] or {}).get("source_tier")
            if tier is None:
                missing.append(p.name)
            elif tier not in VALID_TIERS:
                bad.append(f"{p.name}: {tier}")
        self.assertEqual(missing, [],
                         f"knowledge files without a source_tier: {missing}")
        self.assertEqual(bad, [],
                         f"knowledge files with an unknown source_tier: {bad}")

    def test_the_cpic_base_states_which_of_its_layers_is_verbatim(self):
        """The one that matters most. It began as «compiled» — an honest label for
        a hand-paraphrased file. Now the phenotype models and the quoted
        recommendations are verbatim while the patient-facing notes are not, so
        the label is «mixed» and the file must say which part is which. What must
        never happen is a paraphrase presented as the guideline's words."""
        d = json.loads((KNOWLEDGE / "cpic_drug_gene.json").read_text(encoding="utf-8"))
        self.assertEqual(d["_meta"].get("source_tier"), "guideline_mixed")
        self.assertIn("verbatim", d["_meta"].get("source_tier_note", ""))

    def test_a_quoted_recommendation_is_separate_from_our_own_wording(self):
        """A `cpic` block holds the guideline's words; `note` holds ours. If a
        future edit ever writes our sentence into the quoted field, the quote
        stops being a quote — and nothing else in the system would notice."""
        d = json.loads((KNOWLEDGE / "cpic_drug_gene.json").read_text(encoding="utf-8"))
        quoted = 0
        for drug in d["drugs"]:
            for key, g in (drug.get("guidance") or {}).items():
                cp = g.get("cpic") if isinstance(g, dict) else None
                if not cp:
                    continue
                quoted += 1
                self.assertTrue(cp.get("recommendation"), f"{key}: empty quote")
                self.assertIsInstance(cp["recommendation"], str,
                                      "a quote must be one string in the source language, "
                                      "not a per-language map — translating it would end the quote")
                self.assertIn(cp.get("classification"),
                              ("Strong", "Moderate", "Optional", "No Recommendation"),
                              f"{key}: strength of recommendation missing or unknown")
                note = g.get("note")
                if isinstance(note, dict):
                    self.assertNotEqual(note.get("en", "").strip(),
                                        cp["recommendation"].strip(),
                                        "our paraphrase and the quote are the same string — "
                                        "one of the two is mislabelled")
        self.assertGreaterEqual(quoted, 25,
                                "the verbatim recommendations have disappeared from the base")


if __name__ == "__main__":
    unittest.main()
