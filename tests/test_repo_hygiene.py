"""Code and data do not mix.

The disorder in the project folder kept growing not because the folder was badly
looked after, but because the repository was SIMULTANEOUSLY a data directory. As
long as that is so, any tidy-up lasts exactly until the next week: the cache, the
backups, the logs, the intermediate files and the forms people send arrive in the
same place where the code lies, and by eye they are indistinguishable from it.

What is checked here is the separation itself, not its consequences:

  1. there is not a single file with personal data under version control — neither
     by path nor by type;
  2. "for later" directories (`inbox/`, `_to_delete/`, `tmp/`) are not under
     version control at all: once created, they accumulate, because there is
     nobody to delete them;
  3. **all data paths lead into the data directory.** This is the key one: if the
     data root is specified from outside, not a single path has the right to end
     up inside the code tree. As long as that holds, the repository physically
     cannot get cluttered — wherever the application writes, it does not write
     here.

The layout of the data directory is described in `docs/DATA-LAYOUT.md`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

import support

# Extensions that almost always mean somebody's personal data. The list is
# deliberately crude: it is better to forbid too much and to create an exception
# deliberately than to miss a form with a surname because it arrived in an
# unexpected format.
PERSONAL_TYPES = {".pdf", ".docx", ".xlsx", ".doc", ".vcf", ".bam", ".cram",
                  ".bai", ".tbi", ".fastq", ".fq", ".log"}

# Data directories: their content belongs to the person, not to the project.
DATA_DIRECTORIES = {"profile", "genome", "raw", "work", "archive", "reports", "_backups"}

# "I will sort it out later" directories. A separate list, because the reason is
# different: these are not personal data but deferred decisions. A file that has
# done its job is deleted at once — otherwise it stays forever, and in a month
# nobody remembers whether it is needed.
LATER_DIRECTORIES = {"inbox", "_to_delete", "tmp", "temp", "old", "trash"}


def _under_git() -> list:
    out = subprocess.run(["git", "ls-files"], cwd=str(support.ROOT),
                         capture_output=True, text=True,
                         env={"GIT_OPTIONAL_LOCKS": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    if out.returncode != 0:
        return []
    return [Path(p) for p in out.stdout.splitlines() if p.strip()]


def _synthetic_fixture_ok(path) -> bool:
    """Is this the declared, size-capped genome fixture? False if the rule is absent."""
    try:
        spec = importlib.util.spec_from_file_location(
            "synthetic_fixture", support.ROOT / "src" / "tools" / "synthetic_fixture.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:                                             # noqa: BLE001
        return False
    return mod.allowed(path)


class TestDataBoundary(unittest.TestCase):

    def setUp(self):
        self.files = _under_git()
        if not self.files:
            self.skipTest("not a git repository (a built package) — nothing to check")

    def test_there_are_no_personal_directories(self):
        # We compare only the TOP level. The nested `templates/profile/` and
        # `tests/fixtures/profile/` are synthetic templates and a fixture, they
        # are obliged to be under version control: without them the package does
        # not build and the tests do not run.
        offenders = [str(f) for f in self.files if f.parts[0] in DATA_DIRECTORIES]
        self.assertEqual(offenders, [], "user data ended up under version control: "
                                        + ", ".join(offenders[:10]))

    def test_there_are_no_for_later_directories(self):
        offenders = [str(f) for f in self.files if f.parts[0] in LATER_DIRECTORIES]
        self.assertEqual(offenders, [], "a directory of deferred decisions has appeared: "
                                        + ", ".join(offenders[:10]))

    def test_there_are_no_personal_file_types(self):
        # There is exactly one exception and it is named explicitly: the product
        # presentation is HTML with screenshots of the synthetic demo, not
        # somebody's document.
        #
        # …and one judged by content rather than by name: the synthetic genome
        # fixture, cleared by the same predicate the pre-commit check and the build
        # audit use (src/tools/synthetic_fixture.py). This was the FIFTH gate the
        # fixture had to pass, and the only one that runs solely inside a git
        # working tree — so it stayed silent in the cloud and in the built package
        # and spoke up only on the owner's machine. An exception written out five
        # times would by now disagree with itself in at least one of them; this is
        # why it is a function and not a list of paths.
        offenders = [str(f) for f in self.files
                     if f.suffix.lower() in PERSONAL_TYPES
                     and not _synthetic_fixture_ok(support.ROOT / f)]
        self.assertEqual(offenders, [], "a file of a personal type is under version control: "
                                        + ", ".join(offenders[:10]))


class TestPathsLeadIntoTheDataDirectory(unittest.TestCase):
    """Not a single data path should lead inside the code tree.

    What is checked is not "it is clean right now" but a property: with the data
    root specified from outside, the application is obliged to write only there.
    A test that compared lists of files before and after a run would catch the
    same thing — but would fail because of any stray file accidentally created
    nearby.
    """

    PROBE_PROGRAM = (
        "import json, os\n"
        "from scholion import core\n"
        "cache = os.environ.get('SCHOLION_CACHE_DIR') or str(core.repo_dir() / '.cache')\n"
        "print(json.dumps({\n"
        "    'root':    str(core.repo_dir()),\n"
        "    'profile': str(core.profile_dir()),\n"
        "    'genome':  str(core.genome_dir()),\n"
        "    'cache':   str(cache),\n"
        "}, ensure_ascii=False))\n"
    )

    def test_all_paths_are_inside_the_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            data_root.mkdir()
            env = support.env()
            env["SCHOLION_REPO_DIR"] = str(data_root)
            # We drop the explicit pointers to the profile and the genome: we are
            # checking exactly what is derived FROM the data root, not what was
            # set by hand.
            for k in ("SCHOLION_PROFILE_DIR", "SCHOLION_GENOME_DIR", "SCHOLION_CACHE_DIR"):
                env.pop(k, None)
            p = subprocess.run([sys.executable, "-c", self.PROBE_PROGRAM],
                               cwd=str(support.ROOT), env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr[-800:])
            paths = json.loads(p.stdout)

        code_tree = support.ROOT.resolve()
        escaped = []
        for name, path in paths.items():
            try:
                Path(path).resolve().relative_to(data_root.resolve())
            except ValueError:
                # Inside the code tree — this is exactly what cluttering the repository is.
                inside_code = str(Path(path).resolve()).startswith(str(code_tree))
                escaped.append(f"{name} → {path}" + (" (INSIDE THE CODE TREE)" if inside_code else ""))
        self.assertEqual(escaped, [],
                         "a data path went outside the data directory:\n  " + "\n  ".join(escaped))


class TestLayout(unittest.TestCase):
    """`init` lays out the data directory in full and explains every folder.

    An empty folder named `work` is an invitation to put anything at all in it: in
    a month it is already impossible to say which of that is recomputable and
    which is the only copy. A note in each folder costs one line of code and
    settles the question for everybody, including whoever opens the directory a
    year from now.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "data"
        env = support.env()
        env["SCHOLION_REPO_DIR"] = str(self.root)
        for k in ("SCHOLION_PROFILE_DIR", "SCHOLION_GENOME_DIR", "SCHOLION_CACHE_DIR"):
            env.pop(k, None)
        p = subprocess.run([sys.executable, "-m", "scholion", "init"],
                           cwd=str(support.ROOT), env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-800:])

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_slots_are_created(self):
        from scholion import core
        for slot in core.DATA_SLOTS:
            with self.subTest(slot=slot):
                self.assertTrue((self.root / slot).is_dir(),
                                f"init did not create the directory «{slot}»")
        for kind in core.RAW_KINDS:
            with self.subTest(source=kind):
                self.assertTrue((self.root / "raw" / kind).is_dir(),
                                f"init did not create raw/{kind}")

    def test_every_folder_is_explained(self):
        unexplained = [d.name for d in (self.root / "raw").iterdir()
                       if d.is_dir() and not (d / "README.md").exists()]
        for slot in ("raw", "work", "archive"):
            if not (self.root / slot / "README.md").exists():
                unexplained.append(slot)
        self.assertEqual(unexplained, [], "a directory with no note saying «what goes here»: "
                                          + ", ".join(unexplained))

    def test_the_directories_are_closed_to_outsiders(self):
        """0700, not 0755: inside are the profile, the genome and derivatives of the same data."""
        if os.name != "posix":
            self.skipTest("POSIX permissions only")
        offenders = []
        for slot in ("profile", "genome", "raw", "work", "archive"):
            mode = (self.root / slot).stat().st_mode & 0o777
            if mode != 0o700:
                offenders.append(f"{slot}={oct(mode)}")
        self.assertEqual(offenders, [], "a data directory is open to the other users of the machine: "
                                        + ", ".join(offenders))

    def test_an_external_slot_is_not_replaced_by_an_empty_folder(self):
        """If a source has been moved to another disk and the disk is detached,
        `init` must NOT create a stub at that path.

        An empty folder in place of a detached disk quietly turns "the source is
        not connected" into "there is no data". These are different answers: on
        the first one the person goes and connects the disk, on the second one
        they draw a conclusion about their health.
        """
        with tempfile.TemporaryDirectory() as tmp2:
            data_root = Path(tmp2) / "data"
            external = Path(tmp2) / "removable-disk" / "raw"
            data_root.mkdir(parents=True)
            (data_root / "profile").mkdir()
            (data_root / "profile" / "sources.json").write_text(
                json.dumps({"folders": {"raw": str(external)}}, ensure_ascii=False),
                encoding="utf-8")
            env = support.env()
            env["SCHOLION_REPO_DIR"] = str(data_root)
            for k in ("SCHOLION_PROFILE_DIR", "SCHOLION_GENOME_DIR", "SCHOLION_CACHE_DIR"):
                env.pop(k, None)
            p = subprocess.run([sys.executable, "-m", "scholion", "init"],
                               cwd=str(support.ROOT), env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr[-800:])
            self.assertFalse(external.exists(),
                             "init created a stub where a detached external source belongs")
            self.assertFalse((data_root / "raw").exists(),
                             "init created raw/ in the data directory even though the slot lives outside")




class TestTheNumberingBeforePublicationStaysInItsOwnNamespace(unittest.TestCase):
    """A version number identifies a release. Two releases cannot share one.

    This project was built to `2.24.0` before anybody outside had run it, and the
    numbering was reset to `0.1.0` at publication. That leaves 32 tags naming
    versions that will be named again — `v2.24.0` will exist a second time, on a
    different commit, meaning something different — and a tag is exactly what a
    person reaches for when they want to reproduce a state. Two commits under one
    name is not cosmetic: `git checkout v2.24.0` would silently give whichever of
    them the ref happens to hold.

    The fix is that git refs are paths. The pre-publication tags were moved to
    `pre-0.1.0/v2.24.0`, which is `refs/tags/pre-0.1.0/v2.24.0` and cannot collide
    with `refs/tags/v2.24.0` however far the published numbering climbs. Nothing
    was rewritten; the commits are untouched.

    What this checks is the one way it can come undone: a bare `vX.Y.Z` tag placed
    on a commit that predates publication. It can only fail on the actual mistake —
    a legitimate future `v2.24.0` sits after `v0.1.0` and passes.
    """

    ROOT_TAG = "v0.1.0"
    BARE = re.compile(r"^v\d+\.\d+\.\d+$")

    def setUp(self):
        self.env = {"GIT_OPTIONAL_LOCKS": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"}
        if not self._git("rev-parse", "--git-dir"):
            self.skipTest("not a git repository (a built package) — there are no tags")

    def _git(self, *args):
        out = subprocess.run(["git", *args], cwd=str(support.ROOT),
                             capture_output=True, text=True, env=self.env)
        return out.stdout.strip() if out.returncode == 0 else ""

    def test_no_plain_version_tag_points_before_the_first_public_release(self):
        if not self._git("rev-parse", "--verify", "--quiet", self.ROOT_TAG + "^{commit}"):
            self.skipTest(f"{self.ROOT_TAG} is not tagged yet — publication has not happened")
        tags = [t.strip() for t in self._git("tag", "--list").splitlines()
                if self.BARE.match(t.strip())]
        self.assertIn(self.ROOT_TAG, tags)
        stray = []
        for tag in tags:
            if tag == self.ROOT_TAG:
                continue
            ok = subprocess.run(
                ["git", "merge-base", "--is-ancestor", self.ROOT_TAG, tag + "^{commit}"],
                cwd=str(support.ROOT), capture_output=True, text=True, env=self.env)
            if ok.returncode != 0:
                stray.append(tag)
        self.assertEqual(stray, [], "a version tag points at a commit from before the first "
                                    "public release, so one number now names two states: "
                                    + ", ".join(stray) + " — pre-publication versions belong "
                                    "under pre-0.1.0/")

    def test_the_namespace_is_never_taken_by_a_bare_tag_of_its_own_name(self):
        """`refs/tags/pre-0.1.0` as a file would make the directory unwritable.

        Git cannot hold a ref that is both a file and a directory. One such tag
        and no `pre-0.1.0/...` could be created again — including by whoever tries
        to repeat this migration later.
        """
        self.assertNotIn("pre-0.1.0", self._git("tag", "--list").splitlines(),
                         "a bare `pre-0.1.0` tag blocks the whole namespace beneath it")

    def test_the_pre_publication_journal_is_not_published(self):
        """Not secret — a different numbering. Shipped beside the published
        changelog it puts a larger number next to the current one, and a larger
        number reads as newer."""
        journal = support.ROOT / "CHANGELOG.pre-0.1.0.md"
        if not journal.exists():
            self.skipTest("no pre-publication journal in this tree")
        spec = importlib.util.spec_from_file_location(
            "make_shareable_private_list",
            support.ROOT / "src" / "tools" / "make_shareable.py")
        if spec is None or spec.loader is None:
            self.skipTest("the builder is not part of this tree")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("CHANGELOG.pre-0.1.0.md", set(mod.PRIVATE_DEFAULT),
                      "the pre-publication journal is not on the builder's private list, so it "
                      "travels into the package")


if __name__ == "__main__":
    unittest.main()
