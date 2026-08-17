"""The recorded demo profile and its generator do not drift apart.

The package carries the generator, not the data: `pip install` gives you
`scholion/demo.py`, and the fourteen files are created by the command. The
repository additionally keeps a recorded copy under `demo/profile/`, and that is
deliberate — someone browsing the project on GitHub can see what a profile looks
like without installing anything.

A generator and its own output stored side by side can only be trusted while
something compares them. Edit `demo.py`, and the recorded copy stays as it was:
the repository then shows one thing and the command produces another, and only
whoever compares them finds out. The comparison is exact because the generator is
deterministic — SEED is fixed for exactly this reason.
"""
import json
import tempfile
import unittest
from pathlib import Path

import support
from scholion import demo as _demo

RECORDED = support.ROOT / "demo" / "profile"


@unittest.skipUnless(RECORDED.is_dir(), "the recorded demo profile is not in this build")
class TestDemoDrift(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.generated = _demo.build_all()

    def test_the_same_files(self):
        recorded = {p.name for p in RECORDED.glob("*.json")}
        generated = {f"{n}" for n in self.generated}
        missing = sorted(generated - recorded)
        extra = sorted(recorded - generated)
        self.assertEqual(missing, [], "the generator produces files the recorded copy lacks")
        self.assertEqual(extra, [], "the recorded copy has files the generator no longer produces")

    def test_the_content_is_identical(self):
        """Compared as parsed JSON rather than bytes: formatting is not the point,
        values are. A difference here means the repository shows a different
        fictional person from the one the command builds."""
        for name, data in sorted(self.generated.items()):
            with self.subTest(file=name):
                p = RECORDED / name
                self.assertTrue(p.exists(), f"{name} is missing from demo/profile/")
                self.assertEqual(json.loads(p.read_text(encoding="utf-8")), data,
                                 f"{name}: the recorded demo has drifted from the generator — "
                                 f"rebuild it with `scholion demo --out demo/profile --force`")

    def test_the_generator_is_deterministic(self):
        """Without this the comparison above would be meaningless: a generator
        that varies cannot be checked against anything."""
        again = _demo.build_all()
        self.assertEqual(again, self.generated, "two runs give different data")

    def test_the_index_travels_too(self):
        idx = RECORDED / "index.md"
        self.assertTrue(idx.exists(), "demo/profile/index.md is missing")
        self.assertEqual(idx.read_text(encoding="utf-8"), _demo.INDEX_MD,
                         "index.md has drifted from the generator")


if __name__ == "__main__":
    unittest.main()
