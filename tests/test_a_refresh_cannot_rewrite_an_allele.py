"""A refresh may move a coordinate. It may not decide what the alleles are.

One documented run of `update_catalog.py --add …` refreshed every existing locus
as well and wrote into `alt` what Ensembl returns — the full observed set, `A/T`,
`C/G`, `A/C`. The catalogue's invariant is one nucleotide on each side, and the
genotype comparison reads one character from each. Thirty-five of fifty-five loci
came out compound, among them the ones dose answers are drawn from: SLCO1B1 for
statin myopathy, CYP2C9 for warfarin, CYP2C19 for clopidogrel. The file grew from
679 lines to 1130.

The suite caught it, and that is the only reason it was seen. A user who ran the
documented command and does not run the tests would have been left with a quietly
broken catalogue and a script that printed «Written to:» over it — which is why
the invariant is now checked inside the script, before it writes, and a run that
would break it writes nothing and exits non-zero.

Two more things the same run left behind. `--add` created an empty record for
every rsID before asking the source, so every rsID the network or the filter
refused stayed in the file as a locus with no gene and no alleles. And a position
the source reports as three-allele has no representation here at all: choosing one
of three would be writing down a number nobody published. It is named and left
out.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

ROOT = Path(support.__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "ingest" / "update_catalog.py"


def _load():
    """The script is not importable as a package member; it is loaded by path.

    Deliberately the real file rather than a copy: the point of this whole file
    is what the documented command does, and a copy is the second version of a
    thing that will one day disagree with the first.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("update_catalog_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UC = _load()

TWO = {"chrom": "1", "pos": 100, "alleles": ["A", "G"],
       "clinical_significance": [], "consequence": "missense_variant"}
THREE = {"chrom": "1", "pos": 200, "alleles": ["C", "A", "G", "T"],
         "clinical_significance": [], "consequence": "intron_variant"}


class TestWhatCountsAsAPairOfAlleles(unittest.TestCase):

    def test_two_single_bases_are_a_pair(self):
        self.assertEqual(("A", "G"), UC.single_pair(["A", "G"]))

    def test_three_alleles_are_not(self):
        self.assertIsNone(UC.single_pair(["C", "A", "G"]))

    def test_an_indel_is_not_a_pair_of_bases(self):
        self.assertIsNone(UC.single_pair(["AT", "A"]))
        self.assertIsNone(UC.single_pair(["-", "A"]))

    def test_one_allele_is_not_a_pair(self):
        self.assertIsNone(UC.single_pair(["A"]))
        self.assertIsNone(UC.single_pair([]))


class TestTheInvariantIsCheckedByTheScriptItself(unittest.TestCase):

    def test_a_compound_alt_is_reported(self):
        bad = {"loci": {"rs1": {"ref": "A", "alt": "T/G"}}}
        self.assertEqual(1, len(UC.invariant_problems(bad)))
        self.assertIn("rs1", UC.invariant_problems(bad)[0])

    def test_a_clean_catalogue_reports_nothing(self):
        self.assertEqual([], UC.invariant_problems({"loci": {"rs1": {"ref": "A", "alt": "G"}}}))

    def test_the_shipped_catalogue_satisfies_it(self):
        cat = json.loads((ROOT / "src" / "scholion" / "knowledge" / "loci.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual([], UC.invariant_problems(cat))

    def test_the_check_walks_something(self):
        """A check that sees no entries passes like a clean one."""
        cat = json.loads((ROOT / "src" / "scholion" / "knowledge" / "loci.json")
                         .read_text(encoding="utf-8"))
        self.assertGreater(len(cat["loci"]), 40)


class TestTheSourceReaderShapesTheAnswerAndDoesNotJoinIt(unittest.TestCase):
    """The defect lived in `fetch`, and the first version of this file mocked
    `fetch` away — so re-introducing the defect left every test green. A mock
    that replaces the function under suspicion proves the callers, not it."""

    PAYLOAD = {"mappings": [{"assembly_name": "GRCh38", "seq_region_name": "1",
                             "start": 100, "allele_string": "C/A/G/T"}],
               "clinical_significance": [], "most_severe_consequence": "intron_variant"}

    def _fetch(self):
        import io
        with mock.patch.object(UC.urllib.request, "urlopen",
                               lambda *a, **k: io.BytesIO(json.dumps(self.PAYLOAD).encode())):
            return UC.fetch("rs1")

    def test_the_alleles_come_back_as_a_list(self):
        self.assertEqual(["C", "A", "G", "T"], self._fetch()["alleles"])

    def test_no_joined_allele_string_is_produced_at_all(self):
        """One `"/".join(...)` is the whole of the original defect: a field that
        holds one nucleotide receiving three, with nothing downstream able to
        tell. The reader does not build that value in the first place."""
        rec = self._fetch()
        for field in ("alt", "ref"):
            with self.subTest(field=field):
                self.assertNotIn(field, rec)

    def test_the_coordinate_still_arrives(self):
        rec = self._fetch()
        self.assertEqual(("1", 100), (rec["chrom"], rec["pos"]))


class TestARefreshLeavesTheAllelesAlone(unittest.TestCase):

    def _run(self, catalogue, answers, add=()):
        path = Path(self.tmp) / "loci.json"
        path.write_text(json.dumps(catalogue, ensure_ascii=False), encoding="utf-8")
        argv = ["update_catalog.py", "--add", *add] if add else ["update_catalog.py"]
        with mock.patch.object(UC, "LOCI", path), \
             mock.patch.object(UC, "fetch", lambda rs: answers.get(rs)), \
             mock.patch.object(UC.time, "sleep", lambda *_: None), \
             mock.patch.object(sys, "argv", argv):
            code = UC.main()
        return code, json.loads(path.read_text(encoding="utf-8"))

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def test_a_three_allele_answer_does_not_touch_a_single_letter_alt(self):
        cat = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 100,
                                "ref": "C", "alt": "T"}}}
        # The answer carries the exact fields the old reader produced, so this
        # holds whatever `fetch` happens to return: the refresh must not copy
        # them even when they are handed to it.
        code, out = self._run(cat, {"rs1": {**THREE, "pos": 100,
                                            "ref": "C", "alt": "A/G/T"}})
        self.assertEqual(0, code)
        self.assertEqual(("C", "T"), (out["loci"]["rs1"]["ref"], out["loci"]["rs1"]["alt"]))

    def test_a_disagreement_about_alleles_is_reported_and_not_applied(self):
        cat = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 100,
                                "ref": "C", "alt": "T"}}}
        code, out = self._run(cat, {"rs1": TWO})
        self.assertEqual(0, code)
        self.assertEqual("T", out["loci"]["rs1"]["alt"], "the refresh overwrote an allele")

    def test_the_coordinate_is_still_refreshed(self):
        cat = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 999,
                                "ref": "A", "alt": "G"}}}
        _, out = self._run(cat, {"rs1": TWO})
        self.assertEqual(100, out["loci"]["rs1"]["pos"])

    def test_the_manual_fields_survive(self):
        cat = {"loci": {"rs1": {"gene": "G1", "star": "*2", "note": "n",
                                "chrom": "1", "pos": 1, "ref": "A", "alt": "G"}}}
        _, out = self._run(cat, {"rs1": TWO})
        for field in ("gene", "star", "note"):
            with self.subTest(field=field):
                self.assertIn(field, out["loci"]["rs1"])


class TestAddingALocus(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def _add(self, rsid, answer):
        path = Path(self.tmp) / "loci.json"
        path.write_text(json.dumps({"loci": {}}), encoding="utf-8")
        with mock.patch.object(UC, "LOCI", path), \
             mock.patch.object(UC, "fetch", lambda rs: answer), \
             mock.patch.object(UC.time, "sleep", lambda *_: None), \
             mock.patch.object(sys, "argv", ["update_catalog.py", "--add", rsid]):
            code = UC.main()
        return code, json.loads(path.read_text(encoding="utf-8"))

    def test_a_two_allele_position_is_added(self):
        code, out = self._add("rs1", TWO)
        self.assertEqual(0, code)
        self.assertEqual("G", out["loci"]["rs1"]["alt"])

    def test_a_three_allele_position_is_entered_without_an_alternative(self):
        """Task 167 gave it a representation: the position is held with the
        alleles observed there and no `alt` chosen. What must never happen is an
        `alt` picked out of three — see the invariant and the reader's refusal in
        `test_a_position_with_three_alternatives_is_held_without_a_guess.py`."""
        code, out = self._add("rs2", THREE)
        self.assertEqual(0, code)
        entry = out["loci"]["rs2"]
        self.assertNotIn("alt", entry, "one of three alternatives was chosen")
        self.assertEqual(["C", "A", "G", "T"], entry["alleles_observed"])

    def test_a_source_that_did_not_answer_leaves_no_empty_record(self):
        """The old order created the entry before asking. Every rsID the network
        refused stayed in the file as a locus with no gene and no alleles."""
        code, out = self._add("rs3", None)
        self.assertEqual(0, code)
        self.assertEqual({}, out["loci"])


class TestNothingIsWrittenOverABrokenCatalogue(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def test_a_run_that_would_break_the_invariant_writes_nothing_and_fails(self):
        path = Path(self.tmp) / "loci.json"
        original = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 1,
                                     "ref": "A", "alt": "T/G"}}}
        path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(UC, "LOCI", path), \
             mock.patch.object(UC, "fetch", lambda rs: TWO), \
             mock.patch.object(UC.time, "sleep", lambda *_: None), \
             mock.patch.object(sys, "argv", ["update_catalog.py"]):
            code = UC.main()
        self.assertEqual(1, code, "a broken catalogue exited as success")
        self.assertEqual(original, json.loads(path.read_text(encoding="utf-8")),
                         "the file was written despite the invariant failing")

    def test_the_script_still_parses_and_offers_its_help(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("--dry-run", r.stdout)


if __name__ == "__main__":
    unittest.main()
