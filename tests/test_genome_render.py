"""What was measured about a locus reaches the reader.

The genome layer computes three levels of confidence in a genotype and, for a
shallow read, a note saying the call cannot be trusted. Both were being lost on
the last mile — one printed as an empty string, the other printed nowhere at
all — which is the project's own rule about qualifiers, broken in the module the
rule was written for.

These tests go through the render, not the structure. A field that only exists
in `--json` is exactly the failure being fixed.
"""
from __future__ import annotations

import unittest

import support
from scholion import format as fmt


def _answer(confidence, depth=None, note=None, catalogue_note=None):
    """The shape `engine.genome_lookup` returns for a single rsID."""
    res = {"genotype": "CC", "confidence": confidence, "source": "vcf"}
    if depth is not None:
        res["depth"] = depth
    if note:
        res["note"] = note
    return {"status": "ok", "rsid": "rs4149056", "gene": "SLCO1B1",
            "chrom": "12", "pos": 21178615, "star": "*5",
            "result": res, "note": catalogue_note, "disclaimer": "—"}


class TestEveryConfidenceLevelIsNamed(unittest.TestCase):

    def test_confirmed_ref_is_not_rendered_as_an_empty_string(self):
        """The strongest evidence used to print as "(, depth 25)".

        `confirmed_ref` means the reference was confirmed by an actual call at
        the position rather than inferred from a missing row — the best answer
        the layer can give. It had no line in the render map, so it came out as a
        dangling comma, while the WEAKER `assumed_ref` was labelled properly. A
        reader comparing two loci would have read the better-evidenced one as the
        vaguer of the two.
        """
        out = fmt.genome_report(_answer("confirmed_ref", depth=25))
        self.assertNotIn("(,", out, "the confidence label is empty — see the render map")
        self.assertNotIn("( ,", out)
        for level in ("called", "confirmed_ref", "assumed_ref"):
            with self.subTest(confidence=level):
                text = fmt.genome_report(_answer(level, depth=25))
                self.assertNotIn("(,", text)

    def test_the_three_levels_do_not_read_alike(self):
        """Three names for three states, or the distinction is decorative."""
        seen = {lvl: fmt.genome_report(_answer(lvl, depth=25))
                for lvl in ("called", "confirmed_ref", "assumed_ref")}
        self.assertEqual(len(set(seen.values())), 3,
                         "two confidence levels render identically: " + repr(seen))


class TestTheWarningAboutThisReadIsPrinted(unittest.TestCase):

    def test_a_low_depth_note_reaches_the_report(self):
        """The note about THIS read, which reached no channel at all.

        Two different notes live in this answer. `note` at the top level is the
        catalogue's remark about the locus — the same text for everybody.
        `result.note` is about this person's read of this position, and it is
        where "depth is low (4 reads) — the call is unreliable" lives. Only the
        first was printed. The locus that demonstrated it is rs4149056, statin
        myopathy, read four times: no warning anywhere.
        """
        out = fmt.genome_report(_answer("called", depth=4,
                                        note="depth is low (4 reads) — the call is unreliable"))
        self.assertIn("unreliable", out,
                      "the warning about an unreliable call is not in the report")

    def test_the_measurement_leads_the_catalogue_remark(self):
        """Order matters: whether the call can be trusted changes what the
        catalogue's remark about the locus is worth."""
        out = fmt.genome_report(_answer(
            "called", depth=4,
            note="depth is low (4 reads) — the call is unreliable",
            catalogue_note="a curated remark about this locus"))
        self.assertIn("unreliable", out)
        self.assertIn("curated remark", out)
        self.assertLess(out.index("unreliable"), out.index("curated remark"),
                        "the catalogue's remark is printed above the warning about the read")

    def test_the_web_names_the_same_field(self):
        """The parity that matters here is not routes but content.

        A qualifier restored in one channel and forgotten in another is how this
        defect spread in the first place: it survives in two channels out of
        five, and every new channel inherits the loss by default.
        """
        page = (support.ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("res.note", page,
                      "the web page never reads the note about the read itself")
        self.assertIn("confirmed_ref", page,
                      "the web page has no label for the strongest confidence level")


if __name__ == "__main__":
    unittest.main()
