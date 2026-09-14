"""The alignment and the reference are written down, not remembered.

Until 13.09.2026 this product knew where every input of it lived — the folder of
laboratory forms, the wearable export, the genome file itself — except two: the
alignment the reads were called from and the reference they were called against.
Those were found by the layout the project's own pipeline happens to write, and
anybody whose files lie elsewhere could only name them with an environment
variable: for one run, on one machine, remembered by nobody. The first real run
of `recompute` refused three times over exactly this.

Held here:

  * both paths are recorded beside the profile, at the top of `sources.json`,
    where the genome file already sat;
  * the order of precedence is the variable, then the recorded path, then the
    layout — a variable names a file for one run, a record for every run after;
  * a reference with no `.fai` is refused with a sentence and NOTHING is
    written: every reader of that path skips a FASTA without an index, so a
    recorded one would be a setting the program then ignores;
  * an empty path clears the record;
  * the refusal a person actually reads names the command that records the path,
    in both languages — not only the variable that names it once.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as F, gene_region, i18n, store
from scholion.i18n import en, ru


class _Profile(unittest.TestCase):
    """A profile of its own, so nothing here touches anybody's settings."""

    def setUp(self):
        self.dir = Path(support.temp_dir(self)) if hasattr(support, "temp_dir") else None
        if self.dir is None:
            import tempfile
            self._tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp.cleanup)
            self.dir = Path(self._tmp.name)
        self.env = mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(self.dir)})
        self.env.start()
        self.addCleanup(self.env.stop)
        core.reset_cache()
        self.addCleanup(core.reset_cache)
        self.bam = self.dir / "sample.bam"
        self.bam.write_bytes(b"not really a bam")
        self.ref = self.dir / "reference.fa"
        self.ref.write_text(">chr1\nACGT\n", encoding="utf-8")

    def sources(self) -> dict:
        p = self.dir / "sources.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


class TestThePathsAreRecorded(_Profile):

    def test_the_alignment_is_written_at_the_top_of_the_sources_file(self):
        r = store.set_genome_bam(str(self.bam))
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(str(self.bam), self.sources().get("genome_bam"))
        self.assertEqual(str(self.bam), core.chosen_genome_bam())

    def test_a_file_that_is_not_an_alignment_is_refused_and_nothing_is_written(self):
        other = self.dir / "notes.txt"
        other.write_text("x", encoding="utf-8")
        r = store.set_genome_bam(str(other))
        self.assertFalse(r.get("ok"))
        self.assertIn("notes.txt", r.get("error") or "")
        self.assertNotIn("genome_bam", self.sources())

    def test_a_reference_without_its_index_is_refused_in_words(self):
        r = store.set_genome_reference(str(self.ref))
        self.assertFalse(r.get("ok"), "a FASTA with no .fai must not be recorded")
        self.assertIn("samtools faidx", r.get("error") or "")
        self.assertNotIn("genome_reference", self.sources())
        Path(str(self.ref) + ".fai").write_text("chr1\t4\t6\t4\t5\n", encoding="utf-8")
        r = store.set_genome_reference(str(self.ref))
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(str(self.ref), core.chosen_genome_reference())

    def test_an_empty_path_clears_the_record(self):
        store.set_genome_bam(str(self.bam))
        self.assertTrue(core.chosen_genome_bam())
        store.set_genome_bam("")
        self.assertIsNone(core.chosen_genome_bam())
        self.assertNotIn("genome_bam", self.sources())


class TestWhichPathAnswers(_Profile):

    def test_the_variable_wins_over_the_record_and_the_record_over_the_layout(self):
        other = self.dir / "other.bam"
        other.write_bytes(b"x")
        store.set_genome_bam(str(self.bam))
        with mock.patch.dict(os.environ, {"SCHOLION_GENOME_BAM": str(other)}):
            self.assertEqual(other, gene_region.bam_path())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SCHOLION_GENOME_BAM", None)
            self.assertEqual(self.bam, gene_region.bam_path(),
                             "the recorded path must answer when no variable does")

    def test_the_recorded_reference_answers_only_with_its_index(self):
        os.environ.pop("SCHOLION_GENOME_REFERENCE", None)
        Path(str(self.ref) + ".fai").write_text("chr1\t4\t6\t4\t5\n", encoding="utf-8")
        store.set_genome_reference(str(self.ref))
        self.assertEqual(self.ref, gene_region.reference_path())
        Path(str(self.ref) + ".fai").unlink()
        self.assertNotEqual(self.ref, gene_region.reference_path(),
                            "a reference whose index vanished must not answer")


class TestTheRefusalNamesWhereThePathIsRecorded(unittest.TestCase):

    def test_both_languages_name_the_command_and_not_only_the_variable(self):
        for words in (en.MESSAGES, ru.MESSAGES):
            for key in ("recompute.why.no_bam", "recompute.why.no_reference"):
                with self.subTest(key=key):
                    text = words[key]
                    self.assertIn("choose-genome", text,
                                  "the refusal names no way to record the path")
                    self.assertIn("SCHOLION_GENOME_", text,
                                  "the variable is still the way to name it for one run")

    def test_the_sentence_a_person_reads_carries_it(self):
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            try:
                text = F.genotype_sites_report({"ok": False, "status": "refused",
                                                "reason": "no_bam"})
            finally:
                i18n.set_lang(None)
            self.assertIn("choose-genome --bam", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
