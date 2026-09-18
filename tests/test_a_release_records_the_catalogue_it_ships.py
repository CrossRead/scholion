"""A release records how big the locus catalogue was, so its growth is not found on somebody's profile.

`loci_sites.vcf.gz` answers for the catalogue it was made from, and the catalogue grew
three times in five weeks: 61 → 113 with 0.5.1, 113 → 141 on 17.09.2026, 141 → 250 on
18.09. Each time a profile that was never re-genotyped read the positions added since as
«not read» — 21 of 92, then 5, then 26 of 231 — each time the fix was one command and
three seconds, and each time it was noticed on the owner's own data, after the release.

So the publication record stops being version → fingerprint. It carries the size of the
catalogue that travelled and the date of that catalogue, and the check compares the tree
against the last version that recorded one: if it changed, the release entry has to name
the step that closes it. That is the whole mechanism — it does not decide anything about
anyone's data, it only refuses to let the growth go out unmentioned.

The check is exercised on a tree built here. A test that writes probe files into the
project leaves debris when it fails, and on a filesystem where deletion is refused it
fails for a reason that has nothing to do with what it tests.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import support

TOOL = support.ROOT / "src" / "tools" / "check_published.py"

_PYPROJECT = '''[project]
name = "probe"

packages = ["src/probe"]

include = [
    "/src/probe",
    "/VERSION",
]
'''

_ENTRY = """# Changelog

## v1.1.0 — 18.09.2026

### What needs recomputing

%s

## v1.0.0 — 01.09.2026

Nothing.
"""


def _load(root: Path):
    spec = importlib.util.spec_from_file_location("check_published_catalogue", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = root
    mod.RECORD = root / "published.json"
    return mod


def _tree(positions: int, version: str = "1.1.0", note: str = "Nothing to recompute."):
    root = Path(tempfile.mkdtemp(prefix="pub_")).resolve()
    (root / "src" / "probe").mkdir(parents=True)
    (root / "src" / "scholion" / "knowledge").mkdir(parents=True)
    (root / "src" / "probe" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(_ENTRY % note, encoding="utf-8")
    (root / "src" / "scholion" / "knowledge" / "loci.json").write_text(json.dumps({
        "_meta": {"catalog_updated": "2026-09-18"},
        "loci": {f"rs{i}": {"chrom": "1", "pos": i} for i in range(positions)},
    }), encoding="utf-8")
    return root


@unittest.skipUnless(TOOL.exists(), "check_published.py is not part of this build")
class TestTheRecord(unittest.TestCase):

    def tree(self, *a, **kw):
        import shutil
        root = _tree(*a, **kw)
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def test_recording_a_version_writes_the_catalogue_beside_the_fingerprint(self):
        mod = _load(self.tree(141))
        self.assertEqual(0, mod.record())
        entry = json.loads(mod.RECORD.read_text(encoding="utf-8"))["1.1.0"]
        self.assertEqual(141, entry["catalogue"]["positions"])
        self.assertEqual("2026-09-18", entry["catalogue"]["updated"])
        self.assertTrue(entry["fingerprint"])

    def test_a_record_written_before_this_existed_is_read_and_not_rewritten(self):
        """Everything up to 0.5.4 recorded the fingerprint alone, as a string. Those
        entries are history: the size nobody measured then is not invented now."""
        mod = _load(self.tree(141))
        self.assertEqual({"fingerprint": "abc", "catalogue": None}, mod._entry("abc"))
        self.assertIsNone(mod._last_recorded_catalogue({"1.0.0": "abc"}, "1.1.0")[1])


@unittest.skipUnless(TOOL.exists(), "check_published.py is not part of this build")
class TestTheGuard(unittest.TestCase):

    def tree(self, *a, **kw):
        import shutil
        root = _tree(*a, **kw)
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def _with_previous(self, now, before, note):
        mod = _load(self.tree(now, note=note))
        mod.RECORD.write_text(json.dumps(
            {"1.0.0": {"fingerprint": "old", "catalogue": {"positions": before,
                                                           "updated": "2026-09-01"}}}), encoding="utf-8")
        return mod

    def test_a_grown_catalogue_with_no_word_about_it_is_refused(self):
        mod = self._with_previous(250, 141, "Nothing to recompute.")
        self.assertEqual(1, mod.catalogue_check("1.1.0", mod._record()))

    def test_a_grown_catalogue_the_entry_names_the_step_for_is_allowed(self):
        mod = self._with_previous(
            250, 141, "**Run `scholion genotype-sites`** — if a sites file was made earlier.")
        self.assertEqual(0, mod.catalogue_check("1.1.0", mod._record()))

    def test_an_unchanged_catalogue_asks_for_nothing(self):
        mod = self._with_previous(141, 141, "Nothing to recompute.")
        self.assertEqual(0, mod.catalogue_check("1.1.0", mod._record()))

    def test_with_nothing_to_compare_against_it_says_so_and_does_not_refuse(self):
        mod = _load(self.tree(250))
        self.assertEqual(0, mod.catalogue_check("1.1.0", {}))

    def test_the_comparison_is_against_the_newest_version_below_this_one(self):
        """Not the last line of the file, and not a later version somebody added by
        hand: `1.10.0` is above `1.9.0`, which string order gets backwards."""
        mod = _load(self.tree(250))
        data = {"1.9.0": {"fingerprint": "a", "catalogue": {"positions": 141, "updated": None}},
                "1.10.0": {"fingerprint": "b", "catalogue": {"positions": 200, "updated": None}},
                "2.0.0": {"fingerprint": "c", "catalogue": {"positions": 999, "updated": None}}}
        self.assertEqual(("1.10.0", 200),
                         (lambda v, c: (v, c["positions"]))(*mod._last_recorded_catalogue(data, "1.11.0")))


@unittest.skipUnless(TOOL.exists(), "check_published.py is not part of this build")
class TestTheBuildItself(unittest.TestCase):

    def test_this_tree_reads_its_own_catalogue(self):
        mod = _load(support.ROOT)
        cat = mod.catalogue()
        self.assertGreater(cat["positions"], 0)
        self.assertRegex(str(cat["updated"]), r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
