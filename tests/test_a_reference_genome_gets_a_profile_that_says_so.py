"""A profile laid out for a published reference sample says so in every file.

The demo fetcher pulls a Genome in a Bottle sample and prints the recipe:
`scholion init --dir <folder>`, then point the product at both. Run as printed
on 13.09.2026, the recipe ended in a refusal — the empty templates read as the
owner's, the folder's SUBJECT.json said «reference», and the subject gate did
what it is for. `init --subject reference` stamps the templates, so the
reference genome is read beside a profile that is its own.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import store, subject
from scholion.i18n import en, ru


class TestInitForAReferenceSample(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="refsub_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(support.pin_cache(self.root / "cache"))
        (self.root / "genome").mkdir()
        (self.root / "genome" / "SUBJECT.json").write_text(json.dumps(
            {"subject": "reference", "sample": "HG005", "who": "a trio's son", "file": "x.vcf.gz"}),
            encoding="utf-8")
        self.vcf = self.root / "genome" / "x.vcf.gz"
        self.vcf.write_bytes(b"")

    def test_every_file_says_reference_and_the_genome_is_read_beside_it(self):
        r = store.init_profile(target=str(self.root / "profile"), subject="reference")
        self.assertTrue(r["ok"], r)
        self.assertEqual("reference", r.get("subject"))
        for name in r["written"]:
            fp = self.root / "profile" / name
            if fp.suffix == ".json":
                with self.subTest(file=name):
                    self.assertEqual("reference", json.loads(fp.read_text(encoding="utf-8"))["_meta"]["subject"])
        self.assertEqual("reference", subject.profile_subject(self.root / "profile"))
        self.assertIsNone(subject.genome_conflict(self.vcf, self.root / "profile"))

    def test_without_the_flag_the_recipe_still_refuses_by_name(self):
        r = store.init_profile(target=str(self.root / "profile"))
        self.assertTrue(r["ok"], r)
        self.assertEqual("owner", subject.profile_subject(self.root / "profile"))
        conflict = subject.genome_conflict(self.vcf, self.root / "profile")
        self.assertEqual("another_person", conflict["reason"])
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertIn("--subject reference", cat["genome.refused.another_person"],
                          "the refusal names the way out")

    def test_an_unknown_subject_is_refused(self):
        r = store.init_profile(target=str(self.root / "profile"), subject="martian")
        self.assertFalse(r["ok"])

    def test_the_command_line_carries_the_flag(self):
        code, out, err = support.run(["init", "--dir", str(self.root / "profile"), "--subject", "reference", "--json"])
        self.assertEqual(0, code, err or out)
        self.assertEqual("reference", json.loads(out)["subject"])


if __name__ == "__main__":
    unittest.main()
