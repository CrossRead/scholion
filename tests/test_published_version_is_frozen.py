"""A published version cannot be rewritten, and the check knows the difference.

`skip-existing: true` in the publication workflow exists so that a tag moving
after a correction to the release notes does not leave a red mark where nothing
is wrong. It has a cost, and the cost is silence: the same setting turns «somebody
forgot to bump VERSION» into a quiet skip, after which the registry holds the old
artefact and the tag points at code nobody can install.

The check pays for that silence by asking the question the workflow no longer
asks. These tests hold the two halves it rests on: that «what travels» is read out
of the build configuration rather than listed twice, and that the fingerprint can
tell a change inside the package from a change outside it.

The fingerprint is exercised on a tree built here, not on the repository. A test
that writes probe files into the project leaves debris behind when it fails, and
on a filesystem where deletion is refused it fails for a reason that has nothing
to do with what it is testing.
"""
from __future__ import annotations

import importlib.util
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


def _load(root: Path | None = None):
    spec = importlib.util.spec_from_file_location("check_published", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if root is not None:
        mod.ROOT = root
        mod.RECORD = root / "published.json"
    return mod


@unittest.skipUnless(TOOL.exists(), "check_published.py is not part of this build")
class TestWhatTravelsIsRead(unittest.TestCase):
    """Read out of the build configuration. A second list drifts from the first,
    and the day it does, the check is about a package that no longer exists."""

    def setUp(self):
        self.mod = _load()

    def test_it_names_what_the_build_ships(self):
        paths = self.mod.packaged_paths()
        for expected in ("src/scholion", "tests", "VERSION"):
            with self.subTest(path=expected):
                self.assertIn(expected, paths)

    def test_what_does_not_travel_is_absent(self):
        """The case that raised the question: the Hub manifest lives in the
        repository, goes into a pull request, and never reaches the registry."""
        self.assertNotIn("ouroboros_plugin", self.mod.packaged_paths())

    def test_the_changelog_does_travel(self):
        """Worth asserting because it is counter-intuitive and it changes advice.

        The journal is in the sdist. So a correction to the release notes after
        publication is NOT a free re-publish: the artefact really would differ,
        the registry cannot accept it, and the right move is the release page and
        the repository — not a moved tag.
        """
        self.assertIn("CHANGELOG.md", self.mod.packaged_paths())


@unittest.skipUnless(TOOL.exists(), "check_published.py is not part of this build")
class TestTheFingerprintTellsThemApart(unittest.TestCase):
    """A gate that cannot fail is worse than no gate — so both directions."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
        (self.dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        pkg = self.dir / "src" / "probe"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("x = 1\n", encoding="utf-8")
        (self.dir / "outside").mkdir()
        (self.dir / "outside" / "notes.md").write_text("a\n", encoding="utf-8")
        self.mod = _load(self.dir)
        self.before = self.mod.fingerprint()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_new_file_inside_the_package_moves_it(self):
        (self.dir / "src" / "probe" / "extra.py").write_text("y = 2\n", encoding="utf-8")
        self.assertNotEqual(self.mod.fingerprint(), self.before,
                            "the check would pass a real change to the package")

    def test_an_edit_inside_the_package_moves_it(self):
        """Content, not only names: a file replaced in place is the ordinary case."""
        (self.dir / "src" / "probe" / "__init__.py").write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(self.mod.fingerprint(), self.before)

    def test_a_change_outside_it_does_not(self):
        (self.dir / "outside" / "notes.md").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.mod.fingerprint(), self.before,
                         "every documentation fix would then demand a new version")

    def test_the_verdicts_are_the_three_that_matter(self):
        """Published-and-same, published-and-changed, and not-published."""
        self.mod.published = lambda name, version: False
        self.assertEqual(self.mod.check(), 0, "a first publication was refused")

        self.mod.published = lambda name, version: True
        self.assertEqual(self.mod.record(), 0)
        self.assertEqual(self.mod.check(), 0, "an unchanged package was refused")

        (self.dir / "src" / "probe" / "__init__.py").write_text("x = 3\n", encoding="utf-8")
        self.assertEqual(self.mod.check(), 1,
                         "a changed package under a published number was allowed — "
                         "the upload would be skipped and the registry would keep "
                         "the old artefact")

    def test_it_refuses_rather_than_guesses_when_the_registry_is_silent(self):
        self.mod.published = lambda name, version: None
        self.assertEqual(self.mod.check(), 1)
        self.assertEqual(self.mod.check(allow_unverified=True), 0,
                         "there has to be a way through for somebody who has checked "
                         "by hand — it just has to be typed")


if __name__ == "__main__":
    unittest.main()
