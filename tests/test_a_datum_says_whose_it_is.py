"""Every datum records whose it is, and two people never share one profile.

Task 102. The demonstration profile marked the FILE: `scholion init --demo`
writes `synthetic: true` into the metadata of each file it lays down. A file is
not what a conclusion is drawn from. Adding one's own measurement to a
demonstration therefore worked in silence — the point joined a series of invented
numbers, the file went on declaring itself synthetic, which had become false, and
the overview counted the abnormalities of a person who was half fictional.

The same shape one layer over: the project can fetch a published reference genome
so that the genomic layer has something real to read. It is a real genome of a
real other person, and read beside a demonstration's laboratory history it makes
one case out of two strangers.

So the mark moves to the datum, and one rule holds: **one profile, one person.**
The person's own measurement does not join a fictional history, it replaces it —
the demonstration is generated from a seed and comes back in one command, which
is what makes erasing it the safe move rather than the drastic one.

Four things are guarded here, and the last two are the ones that matter in a
year:

  * every writer in the tree says whose datum it is writing (walked, not trusted);
  * the erase fires, and takes the whole demonstration with it;
  * the erase CANNOT fire on anything that is not marked — an unmarked profile is
    every real installation, and a gate that could take one of those would be
    worse than no gate at all;
  * silence is not a claim: a genome folder that says nothing is this profile's,
    and only a folder that names another person is refused.
"""
from __future__ import annotations

import ast
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

import support

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import store, subject  # noqa: E402

#: The writers that put a datum into a profile. Named here so that the walk below
#: covers a writer added tomorrow to any of the three, rather than to labs alone.
WRITERS = ("add_lab_point", "add_metric_point", "add_medication")


def _demo_profile() -> pathlib.Path:
    """A real demonstration profile, built by the product's own command."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="whose_"))
    code, out, err = support.run(["init", "--demo", "--dir", str(d / "profile")])
    assert code == 0, f"the demo did not build: {err or out}"
    return d / "profile"


class TestEveryWriterSaysWhose(unittest.TestCase):

    def test_every_call_in_the_tree_passes_subject(self):
        missing = []
        for path in sorted((ROOT / "src").rglob("*.py")):
            if path.name == "store.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                              # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = (fn.attr if isinstance(fn, ast.Attribute)
                        else getattr(fn, "id", None))
                if name not in WRITERS:
                    continue
                if not any(kw.arg == "subject" for kw in node.keywords):
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno} ({name})")
        self.assertEqual([], missing,
                         "these calls write a datum without saying whose it is")

    def test_the_walk_would_notice(self):
        """The guard above passes on an empty search as readily as on a clean tree."""
        found = 0
        for path in sorted((ROOT / "src").rglob("*.py")):
            if path.name == "store.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                              # pragma: no cover
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = (fn.attr if isinstance(fn, ast.Attribute)
                            else getattr(fn, "id", None))
                    if name in WRITERS:
                        found += 1
        self.assertGreaterEqual(found, 8, "the walk found almost no writers — it is scanning nothing")


class TestTheVocabularyIsClosed(unittest.TestCase):

    def test_the_words_are_the_declared_ones(self):
        for word in ("owner", "demo", "reference", "unattributed"):
            self.assertIn(word, subject.SUBJECTS)
        for word in subject.NOT_THE_OWNER:
            self.assertIn(word, subject.SUBJECTS)
        self.assertNotIn("owner", subject.NOT_THE_OWNER)

    def test_a_word_nobody_declared_is_refused_and_nothing_is_written(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_"))
        self.addCleanup(shutil.rmtree, d, True)
        import os
        old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(d)
        try:
            from scholion import core
            core.reset_cache()
            res = store.add_lab_point("glucose", "2020-01-01", 5.0, unit="mmol/L",
                                      date_source="manual", subject="my_neighbour")
            self.assertFalse(res.get("ok"))
            self.assertIn("my_neighbour", res.get("error", ""))
            self.assertFalse((d / "labs.json").exists(),
                             "the refusal still wrote the file")
        finally:
            if old is None:
                os.environ.pop("SCHOLION_PROFILE_DIR", None)
            else:
                os.environ["SCHOLION_PROFILE_DIR"] = old
            from scholion import core
            core.reset_cache()


class TestTheFirstOwnMeasurementTakesTheProfile(unittest.TestCase):

    def test_the_demonstration_is_erased_and_the_point_stands_alone(self):
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        before = json.loads((p / "labs.json").read_text(encoding="utf-8"))
        self.assertGreater(len(before["markers"]["glucose"]["series"]), 1,
                           "the demonstration has no glucose series to be contaminated")

        code, out, err = support.run(
            ["add-lab", "glucose", "2026-08-01", "5.4", "--unit", "mmol/L"],
            profile_dir=p)
        self.assertEqual(0, code, err)

        after = json.loads((p / "labs.json").read_text(encoding="utf-8"))
        series = after["markers"]["glucose"]["series"]
        self.assertEqual(1, len(series), "the real point joined the invented ones")
        self.assertEqual("owner", series[0]["subject"])
        self.assertFalse((p / "pharmacogenomics.json").exists(),
                         "a fictional person's genotypes stayed beside a real measurement")
        self.assertFalse((p / "index.md").exists(),
                         "the demonstration's own description stayed")
        # And it said so, in words, before the ✓ line.
        self.assertIn("erased", out.lower())
        self.assertIn("scholion init --demo", out)

    def test_what_is_erased_is_only_what_carries_the_mark(self):
        """The gate, from the dangerous side. Every real profile is unmarked."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_"))
        self.addCleanup(shutil.rmtree, d, True)
        code, out, err = support.run(["init", "--dir", str(d / "profile")])
        self.assertEqual(0, code, err)
        p = d / "profile"
        before = sorted(x.name for x in p.iterdir())
        self.assertTrue(before, "init wrote nothing, so this proves nothing")
        self.assertEqual([], subject.erasable(p),
                         "a profile written by `init` was listed as erasable")
        code, out, err = support.run(
            ["add-lab", "glucose", "2026-08-01", "5.4", "--unit", "mmol/L"],
            profile_dir=p)
        self.assertEqual(0, code, err)
        self.assertEqual(before, sorted(x.name for x in p.iterdir()),
                         "a write into an ordinary profile removed files from it")
        self.assertNotIn("erased", out.lower())

    def test_a_file_holding_one_real_datum_is_never_erasable(self):
        """The mixed file cannot arise any more — and if it did it would be kept.

        A file whose metadata says synthetic while one point in it says `owner`
        is exactly the state this task removes. It is asserted rather than
        assumed, because the cost of the gate being wrong here is somebody's
        laboratory history.
        """
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "labs.json").write_text(json.dumps({
            "_meta": {"synthetic": True},
            "markers": {"glucose": {"name": "Glucose", "unit": "mmol/L", "series": [
                {"date": "2020-01-01", "value": 5.0},
                {"date": "2026-08-01", "value": 5.4, "subject": "owner"}]}}},
            ensure_ascii=False), encoding="utf-8")
        self.assertEqual([], subject.erasable(d))
        self.assertEqual(["demo", "owner"],
                         subject.subjects_in(json.loads((d / "labs.json").read_text())))
        self.assertEqual("mixed", subject.profile_subject(d))

    def test_an_edited_description_is_not_the_demonstrations_to_erase(self):
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        (p / "index.md").write_text("my own notes\n", encoding="utf-8")
        store_claim = subject.claim_for_owner(p)
        self.assertTrue(store_claim["claimed"])
        self.assertTrue((p / "index.md").exists(),
                        "a file somebody had written in was erased with the demonstration")
        self.assertNotIn("index.md", store_claim["erased"])


class TestAWearableExportIsAMeasurementToo(unittest.TestCase):
    """An export off the wrist claims the profile like a lab point does."""

    def test_importing_an_export_erases_the_demonstration_first(self):
        fixture = ROOT / "tests" / "fixtures" / "whoop"
        if not fixture.is_dir():                             # pragma: no cover
            self.skipTest("no wearable fixture in this tree")
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        code, out, err = support.run(["ingest-wearable", str(fixture)], profile_dir=p)
        self.assertEqual(0, code, err)
        self.assertIn("erased", out.lower())
        self.assertFalse((p / "labs.json").exists(),
                         "a fictional laboratory history stayed under real nights of sleep")
        data = json.loads((p / "wearable_trends.json").read_text(encoding="utf-8"))
        self.assertEqual(["whoop"], sorted(data.get("sources") or {}),
                         "the demonstration's generated device survived the erase")


class TestAGenomeSaysWhoseItIs(unittest.TestCase):

    def _reference_folder(self) -> pathlib.Path:
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_genome_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "SUBJECT.json").write_text(json.dumps(
            {"subject": "reference", "sample": "HG005",
             "who": "a published reference sample"}), encoding="utf-8")
        (d / "HG005_benchmark.vcf.gz").write_bytes(b"")
        return d

    def test_a_reference_genome_is_not_read_beside_a_demonstration(self):
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        g = self._reference_folder()
        conflict = subject.genome_conflict(g / "HG005_benchmark.vcf.gz", p)
        self.assertIsNotNone(conflict, "two people were allowed into one profile")
        self.assertEqual("another_person", conflict["reason"])
        # The message names BOTH sides. «Refused» alone sends the reader to look
        # for a fault in the file, which is the one place there is no fault.
        self.assertIn("reference sample", conflict["message"])
        self.assertIn("demonstration", conflict["message"])
        self.assertTrue(conflict["fix"])

    def test_the_reason_travels_to_the_status_command(self):
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        g = self._reference_folder()
        import os, subprocess
        env = support.env(profile_dir=p)
        env["SCHOLION_GENOME_DIR"] = str(g)
        env.pop("SCHOLION_GENOME_VCF", None)
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import genome; a = genome.available();"
                "print(json.dumps({'reason': a['reason'], 'not_ours': bool(a['not_ours']),"
                " 'vcf': a['vcf'], 'ready': a['ready']}))" % str(support.SRC))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env=env, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(0, r.returncode, r.stderr)
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual("another_person", got["reason"])
        self.assertTrue(got["not_ours"])
        self.assertIsNone(got["vcf"], "the file was still offered as the genome to read")
        self.assertFalse(got["ready"])
        from scholion import genome
        self.assertIn("another_person", genome.REFUSAL_REASONS)

    def test_a_folder_that_says_nothing_belongs_to_this_profile(self):
        """Silence is not a claim — every genome anybody owns is unmarked."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_genome_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "mine.vcf.gz").write_bytes(b"")
        p = _demo_profile()
        self.addCleanup(shutil.rmtree, p.parent, True)
        self.assertEqual("unattributed", subject.of_genome(d / "mine.vcf.gz"))
        self.assertIsNone(subject.genome_conflict(d / "mine.vcf.gz", p))

    def test_the_same_person_is_no_conflict(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_genome_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "SUBJECT.json").write_text(json.dumps({"subject": "owner"}), encoding="utf-8")
        (d / "mine.vcf.gz").write_bytes(b"")
        e = pathlib.Path(tempfile.mkdtemp(prefix="whose_"))
        self.addCleanup(shutil.rmtree, e, True)
        support.run(["init", "--dir", str(e / "profile")])
        self.assertIsNone(subject.genome_conflict(d / "mine.vcf.gz", e / "profile"))


class TestTheFetchToolMarksWhatItFetches(unittest.TestCase):

    def _tool(self):
        import importlib.util
        path = ROOT / "src" / "tools" / "fetch_demo_genome.py"
        if not path.exists():                                # pragma: no cover
            self.skipTest("the fetch tool does not ship in the package")
        spec = importlib.util.spec_from_file_location("fetch_demo_genome", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m, path

    def test_the_note_says_reference_and_names_the_sample(self):
        m, _ = self._tool()
        d = pathlib.Path(tempfile.mkdtemp(prefix="whose_genome_"))
        self.addCleanup(shutil.rmtree, d, True)
        m.write_sidecar(d, "HG005", m.SAMPLES["HG005"], "x_benchmark.vcf.gz")
        note = json.loads((d / m.SIDECAR).read_text(encoding="utf-8"))
        self.assertEqual("reference", note["subject"])
        self.assertTrue(note["who"])
        self.assertTrue(note["consent"])
        self.assertTrue(subject.valid(note["subject"]))

    def test_the_note_is_written_before_the_file_is(self):
        """An interrupted download must not leave an unmarked stranger's genome."""
        m, path = self._tool()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        main = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        order = []
        for node in ast.walk(main):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if name in ("write_sidecar", "download"):
                    order.append((node.lineno, name))
        order.sort()
        self.assertTrue(order, "neither call was found — the walk is scanning nothing")
        self.assertEqual("write_sidecar", order[0][1],
                         "the genome is downloaded before anything says whose it is")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
