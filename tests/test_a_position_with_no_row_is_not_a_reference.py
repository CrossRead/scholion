"""A position with no row in the file is not a confirmed reference.

A VCF of variants has no line where the genome matches the reference — and no
line where nothing was read either. The two are indistinguishable in such a file,
which is why the layer calls that state `assumed_ref` and every decision in the
engine excludes it: `engine/pgx.py`, `core.py` and `engine/genomics.py` each drop
it with a comment saying why.

The last mile did not. It rendered `assumed_ref` in the shape of an ANSWER —
«genotype TT (reference (the site is not variant))» — with the honest note
underneath. On a single locus a reader got both: a reassuring label and a warning
contradicting it on the next line. In a GENE LISTING they got only the first,
because the list keeps `.split("\n")[0]` and the note is the second line.

A physician running `genome --gene DPYD` on a file with no DPYD rows met eight
positions labelled reference. DPYD is fluoropyrimidines — capecitabine, 5-FU —
where the genotype is required BEFORE the first dose, and «reference» reads as
permission to prescribe. The engine would have refused; the screen had already
answered.

The rule this file holds: **the weakest state may not be rendered in the shape of
the strongest**, and it must survive being cut to one line.

The second half is the other side of the same silence. A genotype read from a
position the curated catalogue does not carry is a number with nothing standing
behind it — and the gap gets filled by whoever is talking. It was: asked about
COMT, the product returned rs4680 with a depth of 36 and said, correctly, that
the variant is outside its curated set; the assistant then supplied «the
low-activity variant, slower breakdown of dopamine» from its own general
knowledge, with no source inside the product. So the product says it itself now.
"""
from __future__ import annotations

import re
import unittest

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion.i18n import en, ru


def answer(confidence, *, depth=25, note=None, resolved_by="catalog"):
    """The shape `engine.genome_lookup` returns for one rsID."""
    res = {"genotype": "CC", "confidence": confidence, "source": "vcf"}
    if depth is not None:
        res["depth"] = depth
    if note:
        res["note"] = note
    return {"status": "ok", "rsid": "rs4149056", "gene": "SLCO1B1",
            "chrom": "12", "pos": 21178615, "resolved_by": resolved_by,
            "result": res, "disclaimer": "—"}


def gene_listing(*confidences):
    """The shape the `--gene` path renders: one line per locus."""
    return {"status": "ok", "gene": "DPYD",
            "loci": [answer(c) for c in confidences], "disclaimer": "—"}


class TestTheWeakestStateIsNotShapedLikeAnAnswer(unittest.TestCase):

    def test_a_missing_row_does_not_print_a_genotype(self):
        out = fmt.genome_report(answer("assumed_ref"))
        self.assertNotIn("CC", out,
                         "a genotype was printed for a position with no row in the file")

    def test_a_confirmed_reference_still_does(self):
        """Otherwise the test above passes by printing nothing for anything."""
        out = fmt.genome_report(answer("confirmed_ref"))
        self.assertIn("CC", out)
        self.assertIn("25", out, "the depth that makes it confirmed is not shown")

    def test_the_three_states_are_still_told_apart(self):
        seen = {c: fmt.genome_report(answer(c))
                for c in ("called", "confirmed_ref", "assumed_ref")}
        self.assertEqual(3, len(set(seen.values())), repr(seen))

    def test_the_first_line_alone_is_true(self):
        """The defect in one assertion: a gene listing keeps one line per locus,
        so whatever that line says stands on its own."""
        first = fmt.genome_report(answer("assumed_ref")).split("\n")[0]
        self.assertNotIn("CC", first)
        self.assertTrue(first.lstrip().startswith("\u26aa"),
                        f"not rendered as a refusal: {first!r}")

    def test_the_gene_listing_says_there_is_no_row(self):
        out = fmt.genome_report(gene_listing("assumed_ref", "confirmed_ref"))
        lines = [l for l in out.split("\n") if l.startswith("•")]
        self.assertEqual(2, len(lines), out)
        self.assertIn("\u26aa", lines[0], "the unread position is shaped like an answer")
        self.assertNotIn("CC", lines[0])
        self.assertIn("CC", lines[1], "the read position lost its genotype")

    def test_the_reason_reaches_the_reader_on_a_single_locus(self):
        out = fmt.genome_report(answer(
            "assumed_ref", note="the site is not in the variant VCF"))
        self.assertIn("not in the variant VCF", out)


class TestNoFaceCallsItReference(unittest.TestCase):
    """The card on the page has one line and no room for a note, so the line is
    the whole statement. It said «reference (not a variant site)»."""

    def test_the_page_maps_the_state_to_a_phrase_of_its_own(self):
        from pathlib import Path
        from scholion import engine
        page = (Path(engine.__file__).resolve().parent.parent
                / "web" / "index.html").read_text(encoding="utf-8")
        m = re.search(r"assumed_ref:'([\w.]+)'", page)
        self.assertIsNotNone(m, "the page no longer names a phrase for this state")
        self.assertIn(m.group(1), en.MESSAGES)
        self.assertIn(m.group(1), ru.MESSAGES)

    def test_the_phrase_is_not_the_one_used_for_a_confirmed_reference(self):
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            with self.subTest(lang=lang):
                self.assertNotEqual(cat["web.genome.assumed_ref"],
                                    cat["genome.confirmed_ref_short"])

    def test_the_phrase_does_not_open_with_the_word_reference(self):
        """Inequality with the confirmed-reference phrase was the first guard,
        and the old phrase — «reference (not a variant site)» — passed it. What
        the reader takes from a card is its first word."""
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            with self.subTest(lang=lang):
                first = cat["web.genome.assumed_ref"].strip().lower()
                self.assertFalse(first.startswith(("reference", "референс")),
                                 f"the page still opens with «reference»: {first!r}")

    def test_the_phrase_is_not_borrowed_from_a_state_that_was_read(self):
        """Structural rather than a word check: whatever this state is called, it
        may not be called what a state with evidence behind it is called."""
        read_states = ("genome.confirmed_ref_short", "genome.called",
                       "genome.called_array")
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            for key in read_states:
                with self.subTest(lang=lang, borrowed=key):
                    self.assertNotEqual(cat["web.genome.assumed_ref"], cat[key])


class TestAGenotypeWithNoCuratedReadingSaysSo(unittest.TestCase):

    def test_a_position_outside_the_catalogue_carries_the_sentence(self):
        out = fmt.genome_report(answer("called", resolved_by="Ensembl"))
        self.assertIn(en.MESSAGES["genome.no_curated_reading"].split(":")[0], out)

    def test_a_catalogued_position_does_not(self):
        """The sentence is about a gap. Printing it where there is no gap would
        make every answer look unsupported."""
        out = fmt.genome_report(answer("called", resolved_by="catalog"))
        self.assertNotIn(en.MESSAGES["genome.no_curated_reading"].split(":")[0], out)

    def test_the_sentence_exists_in_both_languages(self):
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertIn("genome.no_curated_reading", cat)


class TestThePageDoesNotPrintAGenotypeForAMissingRow(unittest.TestCase):
    """The engine hands `assumed_ref` a genotype string — the reference bases,
    which is what «no row» WOULD mean if the site had been read — and the card
    put it in the large answer slot, with the honest phrase in small type
    beside it. The CLI had already moved this state to the refusal shape; the
    page had not. Read structurally, because the page runs under no interpreter
    the suite can rely on: the expression that fills the answer slot must
    choose «—» for this state before it reaches for the genotype.
    """

    def page(self):
        from pathlib import Path
        from scholion import engine
        return (Path(engine.__file__).resolve().parent.parent
                / "web" / "index.html").read_text(encoding="utf-8")

    def card(self):
        m = re.search(r"function genomeCard\(r\)\{.*?\n\}\n", self.page(), re.S)
        self.assertIsNotNone(m, "the card renderer is no longer where this test looks")
        return m.group(0)

    def test_the_answer_slot_is_guarded_on_a_single_locus(self):
        card = self.card()
        slot = [l for l in card.split("\n") if 'class="value"' in l]
        self.assertEqual(1, len(slot), card)
        self.assertNotIn("res.genotype", slot[0],
                         "the answer slot reads the genotype straight from the result")
        self.assertRegex(card, r"res\.confidence==='assumed_ref'\?'—':",
                         "no branch chooses «—» for a position with no row")

    def test_the_gene_listing_is_guarded_too(self):
        """The list keeps one line per locus, and it printed the genotype of
        every locus whatever its state — the DPYD case, on the page."""
        card = self.card()
        listing = [l for l in card.split("\n") if "r.loci.map" in l]
        self.assertEqual(1, len(listing), card)
        self.assertIn("confidence==='assumed_ref'?null", listing[0],
                      "a locus with no row is listed with a genotype")


if __name__ == "__main__":
    unittest.main()
