"""The demo profile: the product is visible before you hand it your own data.

The demo is not decoration but an answer to an honest question from a new
person: "what do I get if I upload my medical record here?" Answering it by
asking them to upload the record first is not allowed. That is why the demo is
obliged (a) to work on all the reading commands, (b) to be recognisably SOMEONE
ELSE'S and invented, so that it is never taken for the data of the project's
author or for one's own.

The test is skipped if the build has no `demo/` folder.
"""
import json
import unittest
from pathlib import Path

import support
from scholion import contract

DEMO = support.ROOT / "demo" / "profile"

# Reading commands without mandatory arguments: the demo must answer on all of them.
READ_COMMANDS = [
    ["overview"], ["labs"], ["suggest-tests"], ["second-opinion"], ["radar"],
    ["medications"], ["markers"], ["metrics"], ["goal"], ["focus"], ["brief"],
    ["lifestyle"], ["phenoage", "--panels"], ["assistant"],
]


@unittest.skipUnless(DEMO.is_dir(), "there is no demo profile in this build")
class TestDemoWorks(unittest.TestCase):

    def test_reading_commands_answer(self):
        for argv in READ_COMMANDS:
            with self.subTest(command=argv[0]):
                code, out, err = support.run(argv, profile_dir=DEMO)
                self.assertEqual(code, 0, f"{argv[0]} on the demo: exit code {code}\n{err[-500:]}")
                self.assertNotIn("Traceback", err)
                self.assertTrue(out.strip())

    def test_the_demo_has_something_to_show(self):
        """An empty demo is worse than a missing one: the person will decide the product can do nothing."""
        labs = support.run_json(["labs"], profile_dir=DEMO)
        self.assertGreaterEqual(labs["count"], 15, "too few markers in the demo")
        self.assertGreaterEqual(labs["abnormal_count"], 3,
                                "no abnormalities in the demo — what the product is for stays invisible")

    def test_the_demo_does_not_lie_about_completeness(self):
        """The demo has gaps on purpose: the product is shown honest, not perfect."""
        panels = support.run_json(["phenoage", "--panels"], profile_dir=DEMO)
        incomplete = [p for p in panels.get("panels", []) if not p.get("complete")]
        self.assertTrue(incomplete,
                        "every panel is complete — the demo has stopped showing the behaviour "
                        "«biological age is not computed from an incomplete panel»")

    def test_every_file_is_declared_synthetic(self):
        """The demo is obliged to be signed as invented in EVERY file: otherwise it
        is indistinguishable from someone else's medical record — neither for a
        human nor for an audit."""
        words = ("СИНТЕТ", "ВЫМЫШЛ", "SYNTHETIC", "ДЕМО")
        for f in sorted(DEMO.glob("*.json")):
            with self.subTest(file=f.name):
                data = json.loads(f.read_text(encoding="utf-8"))
                meta = data.get("_meta") or data.get("meta") or {}
                declared = bool(meta.get("synthetic")) or any(
                    w in " ".join(str(v) for v in meta.values() if isinstance(v, str)).upper()
                    for w in words)
                self.assertTrue(declared, f"{f.name}: no mark of synthetic origin in _meta")

    def test_the_demo_describes_a_different_person(self):
        """The demo is deliberately about an invented woman of 33, not about the
        author: that way nobody takes someone else's numbers for their own and
        nobody confuses them with the owner's data."""
        idx = (DEMO / "index.md")
        if not idx.exists():
            self.skipTest("there is no index.md in the demo")
        text = idx.read_text(encoding="utf-8").upper()
        # The index is written in the language of the demo itself (the fictional
        # person is ours, so the demo speaks English); the word that has to be
        # there is the declaration of synthetic origin, in either language.
        self.assertTrue(any(w in text for w in ("SYNTHETIC", "СИНТЕТ")),
                        "index.md does not declare the profile synthetic")


if __name__ == "__main__":
    unittest.main()
