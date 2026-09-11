"""The coordinate catalogue, checked mechanically instead of by memory.

The reader now refuses a row whose reference base is not the one the locus is
written with. That guard is only as good as the catalogue: an entry carrying the
wrong reference turns a correct file into a refusal, and — worse — an entry
carrying somebody's cDNA notation instead of the genomic base turns a real
finding into silence.

`F5 rs6025` is the case that makes this concrete. The gene sits on the minus
strand, so the change everybody names — 1691G>A — is the genomic C>T. Write the
cDNA pair into the genomic fields and every file in the world stops matching,
while the catalogue looks perfectly reasonable to a reader.

Nothing here reaches the network: this is the shape of the catalogue, checked
against itself. What only an external reference can settle — that C really is
the base at 1:169549811 — is the job of `src/tools/check_catalogue_alleles.py`,
which asks Ensembl for both builds and is run by hand.
"""
from __future__ import annotations

import re
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome

COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
_CDNA = re.compile(r"\b\d+([ACGT])>([ACGT])\b")


def catalogue():
    return genome.loci().get("loci", {})


class TestEveryEntryHasAlleles(unittest.TestCase):
    """Without these the new guard in `_gt_at` has nothing to compare against."""

    def test_one_base_each_and_not_the_same_base(self):
        for rs, loc in catalogue().items():
            with self.subTest(rs=rs):
                ref, alt = loc.get("ref"), loc.get("alt")
                self.assertIn(ref, COMPLEMENT, f"{rs}: reference base")
                self.assertIn(alt, COMPLEMENT, f"{rs}: alternative base")
                self.assertNotEqual(ref, alt, f"{rs}: a variant that changes nothing")

    def test_the_key_is_an_rsid(self):
        for rs in catalogue():
            self.assertRegex(rs, r"^rs\d+$")


class TestBothBuildsAreRealCoordinates(unittest.TestCase):
    """A file is read at its own build and nothing is converted, so both numbers
    have to be right — and a coordinate copied from one build into the other is
    the silent way to lose that."""

    def test_every_locus_carries_both(self):
        for rs, loc in catalogue().items():
            with self.subTest(rs=rs):
                self.assertIsInstance(loc.get("pos"), int)
                self.assertIsInstance(loc.get("pos_grch37"), int)

    def test_the_two_builds_do_not_share_a_number(self):
        for rs, loc in catalogue().items():
            with self.subTest(rs=rs):
                self.assertNotEqual(loc["pos"], loc["pos_grch37"],
                                    f"{rs}: the same number in both builds is a copy, not a coordinate")

    def test_a_contig_is_named_the_short_way(self):
        """`chr19` and `19` are the same contig and different strings; the reader
        adds the prefix the file uses."""
        for rs, loc in catalogue().items():
            self.assertNotIn("chr", str(loc.get("chrom", "")).lower(), rs)

    def test_no_two_loci_stand_on_one_coordinate(self):
        """Row selection is by position first. Two catalogue entries on one base
        would make «which locus is this row about» unanswerable."""
        for field in ("pos", "pos_grch37"):
            seen = {}
            for rs, loc in catalogue().items():
                key = (str(loc["chrom"]), loc[field])
                self.assertNotIn(key, seen, f"{rs} and {seen.get(key)} share {field} {key}")
                seen[key] = rs


class TestCdnaNotationDoesNotLeakIntoTheGenomicFields(unittest.TestCase):
    """The F5 case, generalised so the next minus-strand entry is caught too."""

    def test_a_minus_strand_note_agrees_with_the_genomic_pair(self):
        checked = 0
        for rs, loc in catalogue().items():
            note = " ".join(str(v) for v in (loc.get("note") or {}).values()) \
                if isinstance(loc.get("note"), dict) else str(loc.get("note") or "")
            if "minus strand" not in note.lower():
                continue
            m = _CDNA.search(note)
            if not m:
                continue
            checked += 1
            c_ref, c_alt = m.group(1), m.group(2)
            with self.subTest(rs=rs):
                self.assertEqual(COMPLEMENT[c_ref], loc["ref"],
                                 f"{rs}: the note says the cDNA reference is {c_ref}; "
                                 f"on the minus strand the genomic base is "
                                 f"{COMPLEMENT[c_ref]}, the catalogue says {loc['ref']}")
                self.assertEqual(COMPLEMENT[c_alt], loc["alt"], rs)
        self.assertGreaterEqual(checked, 1,
                                "rs6025 carries such a note; if it stops doing so, "
                                "this test has quietly become vacuous")


if __name__ == "__main__":
    unittest.main()
