"""The reader can be named, and a name that cannot be honoured stops the run.

Task 78, the second tail of the reference stand. Which of the three readers
answers is decided by `shutil.which("bcftools")` — a property of the machine,
not of the project. That is fine for a person and wrong for a measurement: the
internal reference test is run to see what a NEW user gets, somebody with no
external tools, going through `tabixlite`; on a machine that has bcftools the
same run silently measures the other path and prints the same numbers. The
instrument was reading a different scale from the one printed on it.

Two properties are guarded, and the second is the one that makes the first
worth anything:

  * a pin actually pins — the readers that were not named answer «not here»,
    whatever is installed on the machine running these tests;
  * a pin that cannot be honoured — a word nobody declared, or a reader that is
    not installed — REFUSES. Falling back would give a run through a reader
    nobody asked for at the exact moment somebody is trying to measure.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import genome  # noqa: E402


class _Pinned:
    """Set (or clear) the pin for the body of a test, and put it back after."""

    def __init__(self, value):
        self.value, self.old = value, None

    def __enter__(self):
        self.old = os.environ.get("SCHOLION_GENOME_ENGINE")
        if self.value is None:
            os.environ.pop("SCHOLION_GENOME_ENGINE", None)
        else:
            os.environ["SCHOLION_GENOME_ENGINE"] = self.value
        return self

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop("SCHOLION_GENOME_ENGINE", None)
        else:
            os.environ["SCHOLION_GENOME_ENGINE"] = self.old
        return False


class TestThePinIsClosedAndReal(unittest.TestCase):

    def test_the_vocabulary_is_the_three_readers(self):
        self.assertEqual(("bcftools", "pysam", "tabixlite"), genome.ENGINES)

    def test_a_word_nobody_declared_is_refused_not_ignored(self):
        with _Pinned("bcftool"):                      # one letter short, on purpose
            problem = genome.engine_problem()
            self.assertIsNotNone(problem, "an undeclared reader name was ignored")
            self.assertEqual("engine_unknown", problem["reason"])
            self.assertIn("bcftool", problem["value"])
            for engine in genome.ENGINES:
                self.assertIn(engine, problem["accepted"])

    def test_pinning_one_reader_switches_the_others_off(self):
        """The property the stand needs, and it holds whatever this machine has."""
        with _Pinned("tabixlite"):
            self.assertFalse(genome._have_bcftools(), "bcftools answered while tabixlite was pinned")
            self.assertFalse(genome._have_pysam(), "pysam answered while tabixlite was pinned")
        with _Pinned("bcftools"):
            self.assertFalse(genome._have_pysam(), "pysam answered while bcftools was pinned")

    def test_without_a_pin_nothing_changes(self):
        with _Pinned(None):
            self.assertIsNone(genome.engine_pin())
            self.assertIsNone(genome.engine_problem())
            # The pin must not have become a second, quieter way of disabling a
            # reader that is genuinely installed.
            self.assertEqual(genome._pysam_importable(), genome._have_pysam())

    def test_a_reader_that_is_not_installed_here_is_refused(self):
        missing = [e for e in ("bcftools", "pysam")
                   if (e == "bcftools" and not _which("bcftools"))
                   or (e == "pysam" and not genome._pysam_importable())]
        if not missing:                                        # pragma: no cover
            self.skipTest("this machine has both external readers")
        for engine in missing:
            with self.subTest(engine=engine), _Pinned(engine):
                problem = genome.engine_problem()
                self.assertIsNotNone(problem)
                self.assertEqual("engine_missing", problem["reason"])
                self.assertEqual(engine, problem["value"])

    def test_tabixlite_is_always_honourable(self):
        """It ships with the project, so pinning it can never be a refusal."""
        with _Pinned("tabixlite"):
            self.assertIsNone(genome.engine_problem())


class TestABrokenPinStopsTheLayer(unittest.TestCase):

    def test_the_status_refuses_and_says_which_word(self):
        with _Pinned("nonsuch"):
            st = genome.available()
            self.assertFalse(st["ready"])
            self.assertIsNone(st["vcf"], "a file was offered for reading through no reader")
            self.assertEqual("engine_unknown", st["reason"])
            self.assertEqual("nonsuch", st["engine_problem"]["value"])

    def test_both_reasons_can_be_printed(self):
        # A reason with no sentence prints its own key at a person — the defect
        # task 88 was written after. `test_no_refusal_prints_a_key` walks this
        # list; the two new words have to be in it to be walked.
        for reason in ("engine_unknown", "engine_missing"):
            self.assertIn(reason, genome.REFUSAL_REASONS)

    def test_the_refusal_does_not_read_as_no_genome(self):
        from scholion import format as fmt
        with _Pinned("nonsuch"):
            text = fmt.genome_status_report(genome.available())
        self.assertIn("nonsuch", text)
        self.assertIn("SCHOLION_GENOME_ENGINE", text)
        self.assertNotIn("⟦", text, "a catalogue key leaked into the refusal")


def _which(name: str):
    import shutil
    return shutil.which(name)


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
