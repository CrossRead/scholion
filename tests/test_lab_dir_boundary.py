"""The automatic search for lab forms does not leave the data directory.

Written after a real incident rather than from imagination. A package was built,
audited clean, and three minutes later held 570 KB of one person's lab history —
surname, source filenames, values, draw dates — written inside itself. Nothing
escaped: the build audit was re-run afterwards for an unrelated reason and caught
it. That "unrelated reason" is the only thing that stood between the file and an
archive somebody hands to a colleague.

Two mistakes met:

* `reconcile._default_lab_dir` searched `repo_dir().parent` — one directory
  ABOVE the project. Harmless while the delivery had a container level, whose
  parent held nothing but the delivery; live the moment v2.6.0 removed that level
  and the package moved up next to everything else the owner keeps.
* `reconcile` wrote its provenance to `repo_dir()/profile/`, a path built from
  where the CODE is. So `SCHOLION_PROFILE_DIR` — the single mechanism the whole
  test suite relies on for isolation — did not apply to it.

Both are checked here on the layout that actually failed: a data directory with a
decoy folder of forms as its SIBLING, exactly where an unpacked package sits.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

TEMPLATE_META = {"purpose": "ШАБЛОН. A shipped template.", "synthetic": True}
REAL_META = {"purpose": "A working profile", "synthetic": True}


class _Layout:
    """`<root>/pkg/` — the data directory; `<root>/Лабораторные исследования/` — the decoy."""

    def __init__(self, filled: bool):
        # .resolve() is not cosmetic: on macOS TMPDIR sits under /var, which is a
        # symlink to /private/var, and core.py resolves the paths it is handed
        # through the environment — that resolution is the point of this boundary
        # check. Comparing a resolved answer against an unresolved expectation
        # fails on macOS and passes on Linux, which is the worst of both.
        self.root = Path(tempfile.mkdtemp(prefix="labdir_")).resolve()
        self.data = self.root / "pkg"
        (self.data / "profile").mkdir(parents=True)
        meta = REAL_META if filled else TEMPLATE_META
        markers = ({"cholesterol_total": {"2025-12": 6.13}} if filled else {})
        (self.data / "profile" / "labs.json").write_text(
            json.dumps({"meta": meta, "markers": markers}, ensure_ascii=False), encoding="utf-8")
        (self.data / "profile" / "pharmacogenomics.json").write_text(
            json.dumps({"meta": meta, "genotypes": []}, ensure_ascii=False), encoding="utf-8")

        self.decoy = self.root / "Лабораторные исследования"
        self.decoy.mkdir()
        (self.decoy / "Somebody A A - 9690093678 (Biochemistry).pdf").write_bytes(b"%PDF-1.4 decoy")

    def env(self):
        e = dict(os.environ)
        e["PYTHONPATH"] = str(support.SRC) + os.pathsep + e.get("PYTHONPATH", "")
        e["SCHOLION_REPO_DIR"] = str(self.data)
        e["SCHOLION_PROFILE_DIR"] = str(self.data / "profile")
        e["SCHOLION_OFFLINE"] = "1"
        e["SCHOLION_LANG"] = "en"
        e.pop("SCHOLION_LABS_DIR", None)
        for slot in ("RAW", "GENOME", "WORK"):
            e.pop(f"SCHOLION_{slot}_DIR", None)
        return e

    def resolved_lab_dir(self):
        """What the code would search, asked through a subprocess so the env applies."""
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import reconcile;"
                "d = reconcile._default_lab_dir();"
                "print(d if d else '')" % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], env=self.env(),
                           capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestAFreshPackageDoesNotReachOutside(unittest.TestCase):
    """The incident, reduced to its layout."""

    def setUp(self):
        self.L = _Layout(filled=False)

    def tearDown(self):
        self.L.close()

    def test_a_sibling_folder_of_forms_is_not_picked_up(self):
        """An unpacked package standing next to somebody's documents reads none.

        This is what a recipient's machine looks like, and what the owner's own
        machine looked like when the delivery was built one level higher than
        before.
        """
        self.assertEqual(
            self.L.resolved_lab_dir(), "",
            "the automatic search left the data directory and found the forms next to it")

    def test_nothing_is_written_outside_the_profile(self):
        """The provenance file must not appear anywhere but the profile."""
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import reconcile; reconcile.reconcile()" % str(support.SRC))
        subprocess.run([sys.executable, "-c", code], env=self.L.env(),
                       capture_output=True, text=True, timeout=120)
        stray = [str(p.relative_to(self.L.root))
                 for p in self.L.root.rglob("labs_coverage.json")
                 if p.parent != self.L.data / "profile"]
        self.assertEqual(stray, [], "the provenance was written outside the profile directory")


class TestAFilledProfileDoesNotEarnTheRightEither(unittest.TestCase):
    """The second failure, which is the instructive one.

    The first repair allowed the outside search for a profile that already held
    real data, on the reasoning that such a person had chosen this layout. The
    very next run leaked again — into `demo/profile/`, because the demo profile
    is synthetic AND filled, so the condition said yes. The fault was never which
    condition; it was having one. A guess about somebody's disk that ends in
    reading medical documents cannot be made safe by making it cleverer.
    """

    def setUp(self):
        self.L = _Layout(filled=True)

    def tearDown(self):
        self.L.close()

    def test_data_in_the_profile_does_not_unlock_the_search(self):
        self.assertEqual(
            self.L.resolved_lab_dir(), "",
            "a filled profile still unlocks the search outside the data directory")

    def test_the_visible_folder_is_named_rather_than_read(self):
        """What replaces the convenience: a sentence, not a path that gets opened."""
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import reconcile;"
                "print(json.dumps(reconcile.reconcile()))" % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], env=self.L.env(),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("candidate"), str(self.L.decoy),
                         "the folder next door is not even mentioned to the reader")
        self.assertIn("SCHOLION_LABS_DIR", res.get("candidate_hint") or "",
                      "the hint does not say how to name it")


class TestAnExplicitAnswerIsStillHonoured(unittest.TestCase):
    """The reverse test: the guard must not make the feature unusable."""

    def setUp(self):
        self.L = _Layout(filled=True)

    def tearDown(self):
        self.L.close()

    def test_the_declared_slot_is_used(self):
        """`raw/lab/` is where the data layout says forms live."""
        slot = self.L.data / "raw" / "lab"
        slot.mkdir(parents=True)
        (slot / "form.pdf").write_bytes(b"%PDF-1.4 x")
        self.assertEqual(self.L.resolved_lab_dir(), str(slot))

    def test_the_persons_own_setting_is_honoured(self):
        """`set-folder labs_docs` has to reach `reconcile`, or the refusal has no answer.

        The setting already existed and was already honoured by `ingest-labs`;
        the first version of the repair did not consult it here, which left the
        two commands that leaked with no way of being told anything at all.
        """
        import json as _json
        (self.L.data / "profile" / "sources.json").write_text(
            _json.dumps({"folders": {"labs_docs": str(self.L.decoy)}}), encoding="utf-8")
        self.assertEqual(self.L.resolved_lab_dir(), str(self.L.decoy))

    def test_the_environment_variable_outranks_everything(self):
        """`SCHOLION_LABS_DIR` is a decision, and decisions are honoured."""
        other = self.L.root / "elsewhere"
        other.mkdir()
        env = self.L.env()
        env["SCHOLION_LABS_DIR"] = str(other)
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import reconcile; print(reconcile._default_lab_dir())"
                % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.stdout.strip(), str(other), p.stderr)


class TestTheProfileVariableGovernsTheWrite(unittest.TestCase):
    """`SCHOLION_PROFILE_DIR` is the isolation mechanism; it has to cover this too."""

    def setUp(self):
        self.L = _Layout(filled=True)

    def tearDown(self):
        self.L.close()

    def test_the_provenance_follows_the_profile_not_the_code(self):
        """Pointed away from the code tree, the write goes with the profile.

        While the path was built from `repo_dir()`, a test could point the profile
        at a fixture and the file would still land in the source tree — which is
        precisely how the suite failed to notice any of this.
        """
        away = self.L.root / "profile_elsewhere"
        away.mkdir()
        shutil.copy(self.L.data / "profile" / "labs.json", away / "labs.json")
        shutil.copy(self.L.data / "profile" / "pharmacogenomics.json",
                    away / "pharmacogenomics.json")
        env = self.L.env()
        env["SCHOLION_PROFILE_DIR"] = str(away)
        env["SCHOLION_LABS_DIR"] = str(self.L.decoy)
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import reconcile; reconcile.reconcile()" % str(support.SRC))
        subprocess.run([sys.executable, "-c", code], env=env,
                       capture_output=True, text=True, timeout=120)
        self.assertFalse((self.L.data / "profile" / "labs_coverage.json").exists(),
                         "the provenance was written next to the code, not next to the profile")


class TestTheSameRuleCoversTheWearableExport(unittest.TestCase):
    """The second door of the same class, found by looking for it.

    Fixing one place and assuming the class is closed is a mistake this project
    has already made — the assistant-rules block leaked into the package through
    a second path after the first was sealed. So after the lab folder, every
    automatic search in the shipped core was checked, and `garmin.find_export`
    turned out to carry the same defect reaching one level FURTHER: it walked
    `base`, `base.parent` and `base.parent.parent`. From a delivered package that
    is the folder it was unpacked into and the folder above that.

    Years of somebody's sleep and heart rate are not less private than a lab
    form.
    """

    def setUp(self):
        self.L = _Layout(filled=True)
        # a real-looking export two levels up, where the owner's actually sat
        self.away = self.L.root / "garmin_export" / "DI_CONNECT"
        self.away.mkdir(parents=True)
        (self.away / "DI-Connect-Aggregator").mkdir()

    def tearDown(self):
        self.L.close()

    def _found(self):
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import garmin;"
                "d = garmin.find_export(); print(d if d else '')" % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], env=self.L.env(),
                           capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()

    def test_an_export_outside_the_data_directory_is_not_picked_up(self):
        self.assertEqual(self._found(), "",
                         "the wearable search still reaches outside the data directory")

    def test_the_declared_slot_is_used(self):
        slot = self.L.data / "raw" / "wearables" / "DI_CONNECT"
        slot.mkdir(parents=True)
        (slot / "DI-Connect-Aggregator").mkdir()
        self.assertTrue(self._found().startswith(str(self.L.data)),
                        "the declared raw/wearables slot is not searched")

    def test_the_visible_export_is_named_rather_than_read(self):
        code = ("import sys, json; sys.path.insert(0, %r);"
                "from scholion import garmin; print(json.dumps(garmin.reingest()))"
                % str(support.SRC))
        p = subprocess.run([sys.executable, "-c", code], env=self.L.env(),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertFalse(res.get("ok"))
        self.assertTrue(res.get("candidate"), "the export next door is not mentioned at all")


class TestNoAutomaticSearchLeavesTheDataDirectory(unittest.TestCase):
    """A guard on the class rather than on the two known instances.

    Both leaks were one expression: a path built by walking UP from where the
    code is. The check is crude on purpose — it reads the source — because the
    alternative is remembering, and remembering is what failed twice.
    """

    ALLOWED = {
        # names a candidate for a person to read, never opens it
        "reconcile.py": 1,
        "garmin.py": 1,
    }

    def test_no_new_upward_search_appears_in_the_core(self):
        """Parsed, not grepped — a docstring explaining the defect is not the defect."""
        import ast
        offenders = {}
        for p in sorted((support.ROOT / "src" / "scholion").glob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            hits = 0
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Attribute) and node.attr == "parent"):
                    continue
                inner = node.value
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                        and inner.func.id in ("repo_dir", "profile_dir")):
                    hits += 1
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr in ("repo_dir", "profile_dir")):
                    hits += 1
            if hits > self.ALLOWED.get(p.name, 0):
                offenders[p.name] = hits
        self.assertEqual(
            offenders, {},
            "a module walks up out of the data directory: " + repr(offenders)
            + " — if it only names a candidate without opening it, add it to ALLOWED "
              "with that reason")


if __name__ == "__main__":
    unittest.main()
