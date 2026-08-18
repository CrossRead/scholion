"""A new profile says nothing about the person who just created it.

`scholion init` lays down the templates, and the templates used to carry data:
one triglyceride measurement dated 2024-01, one prescription, a sex, a year of
birth and a height. A minute after installing, before loading anything, the
first screen showed «0 red flags», the labs tab showed a value «within range»
with a date on it, and the header counted a prescription. Two readers with no
context both said they would have repeated those numbers to a doctor.

That is the project's own invariant broken at the only moment every user passes
through: a statement about a person, made from a template. The four tests below
are named after that failure rather than after the files, because the files will
be reorganised and the failure must not come back with them.

The second half is the language. Every template shipped in Russian — including
the parenthesis reading «example, replace with your own», which was the ONLY
marker anywhere on the screen that any of it was a specimen. An English-speaking
reader met a Russian first screen in which the one disclaimer that would have
saved them was the part they could not read.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import support

# The Cyrillic block by code point rather than by literal, so that the check for
# Russian is not itself a line of Russian in the tree it checks.
CYRILLIC = re.compile("[\u0400-\u04FF\u0500-\u052F]")
TEMPLATES = support.ROOT / "src" / "scholion" / "templates"


def _walk(value, path="$"):
    """Every scalar in a JSON tree, with the path it was found at."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, value


class TestTheTemplatesCarryNobodysData(unittest.TestCase):
    """A container ships empty. What is in it is what the owner put there."""

    def test_no_template_ships_a_measurement_a_drug_or_a_body(self):
        cases = [
            ("labs.json", "markers", "a lab value with a date on it is indistinguishable "
                                     "from one the reader had taken"),
            ("medications.json", "medications", "a specimen prescription is counted in the "
                                                "header and checked for interactions"),
            ("pharmacogenomics.json", "genotypes", "a specimen genotype is a statement "
                                                   "about somebody's DNA"),
            ("experiments.json", "experiments", "a specimen experiment claims the reader "
                                                "ran one"),
        ]
        for name, key, why in cases:
            with self.subTest(file=name):
                data = json.loads((TEMPLATES / "profile" / name).read_text(encoding="utf-8"))
                self.assertIn(key, data)
                self.assertFalse(data[key], f"{name}: {key} ships non-empty — {why}")

    def test_the_static_profile_does_not_guess_a_sex_an_age_or_a_height(self):
        """These three feed the BMI and the biological-age panels.

        A default of male / 1985 / 178 cm does not read as a placeholder on screen;
        it reads as a body, and every number computed from it is about that body
        rather than the reader's. Refusing until they are filled in is the correct
        answer, not a missing feature.
        """
        data = json.loads((TEMPLATES / "profile" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(data.get("profile"), {},
                         "the template assigns the reader a sex, a year of birth or a height")

    def test_no_goal_is_set_until_somebody_sets_one(self):
        """A specimen goal at the top level is shown on the first screen as the reader's.

        The example is kept — it is the fastest way to learn the shape — but under
        `_meta`, where the engine does not look for targets.
        """
        data = json.loads((TEMPLATES / "profile" / "health_goals.json").read_text(encoding="utf-8"))
        self.assertNotIn("targets", data,
                         "a goal with somebody else's target values is set for every new user")
        self.assertIn("_example", data.get("_meta", {}),
                      "the shape of a goal is no longer documented anywhere the reader will look")


class TestAFreshProfileReportsNothingMeasured(unittest.TestCase):
    """Through the CLI, the way a person actually meets it."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="fresh_profile_"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_first_overview_counts_nothing(self):
        code, out, err = support.run(["init", "--dir", str(self.dir)], profile_dir=self.dir)
        self.assertEqual(code, 0, err)
        r = support.run_json(["overview"], profile_dir=self.dir)
        self.assertEqual(r["markers_total"], 0,
                         "a marker exists in a profile nobody has put anything into")
        self.assertEqual(r["abnormal_count"], 0)
        self.assertEqual(r["medications_count"], 0,
                         "the header counts a prescription the reader was never given")
        self.assertIsNone(r["subject_id"],
                          "an unknown subject is printed as a value rather than omitted")
        self.assertFalse(r["synthetic"],
                         "an ordinary profile is being announced as the demo")


class TestTheTemplatesAreInTheLanguageThatShips(unittest.TestCase):
    """The files a new user reads first were the ones never translated.

    `check_language.py` counts the Russian left in the tree, but it is a ratchet on
    VOLUME: a comment inside `redact.py` and the heading of the first screen weigh
    the same to it. These files are the ones the reader meets before anything else,
    so they are held to a flat rule of their own rather than to a budget.
    """

    def test_no_template_carries_russian(self):
        for f in sorted((TEMPLATES / "profile").iterdir()):
            if not f.is_file():
                continue
            with self.subTest(file=f.name):
                hits = [ln for ln in f.read_text(encoding="utf-8").splitlines()
                        if CYRILLIC.search(ln)]
                self.assertEqual(hits, [], f"{f.name}: the first files a new user opens "
                                           f"are not in the language the package ships in")

    def test_a_template_explains_itself_where_the_reader_will_look(self):
        """Emptiness has to be legible as a decision, or it reads as a broken install."""
        for name in ("labs.json", "medications.json", "metrics.json", "health_goals.json"):
            with self.subTest(file=name):
                meta = json.loads((TEMPLATES / "profile" / name)
                                  .read_text(encoding="utf-8")).get("_meta", {})
                self.assertIn("why_empty", meta,
                              f"{name}: nothing tells the reader the file is empty on purpose")
                self.assertTrue(str(meta["why_empty"]).strip())


if __name__ == "__main__":
    unittest.main()
