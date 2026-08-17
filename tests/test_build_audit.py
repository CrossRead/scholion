"""The build audit, on trees built for the purpose.

The audit is the last gate before anything reaches another person, and it is
fail-closed: any violation and the package is not handed over. That makes its
false alarms as dangerous as its misses. A gate that cries wolf on every run is
one people learn to read past, and it fails open the day it is right.

Both of the cases here were found by running a build on the owner's machine,
where the filesystem refuses `unlink`:

* the previous build could not be deleted, so it was renamed aside — and then
  audited, and its demo profile reported as real data. Three violations that had
  nothing to do with what was being shipped. The skip for quarantined directories
  existed and was applied at three of the four checks;
* the synthetic VCF the tests need was refused by file extension, with no way for
  a file to say what it is.
"""
from __future__ import annotations

import base64
import gzip
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import support

TOOL = support.ROOT / "src" / "tools" / "make_shareable.py"

try:
    _spec = importlib.util.spec_from_file_location("make_shareable", TOOL)
    ms = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(ms)
except Exception:                                                 # noqa: BLE001
    ms = None


def _audit(root: Path):
    """Run the audit quietly and return (violations, what it printed)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        n = ms.audit(root)
    return n, buf.getvalue()


def _labs(points: int) -> str:
    return json.dumps({"markers": {"hgb": {"series": [{"date": f"2024-01-{i+1:02d}",
                                                       "value": 140 + i}
                                                      for i in range(points)]}}})


@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestQuarantinedBuildsAreNotAudited(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_a_profile_inside_a_quarantined_directory_is_not_reported(self):
        self._write("demo._stale/profile/labs.json", _labs(40))
        n, out = _audit(self.root)
        self.assertEqual(n, 0,
                         "the audit reported a version nobody is shipping:\n" + out)

    def test_the_same_file_in_the_package_itself_is_reported(self):
        """The reverse, so that the skip cannot be widened into a blind spot."""
        self._write("demo/profile/labs.json", _labs(40))
        n, out = _audit(self.root)
        self.assertGreaterEqual(n, 1, "a full lab history in the package went unreported")
        self.assertIn("labs.json", out)


class TestAShippedToolTakesItsImportsWithIt(unittest.TestCase):
    """A tool in the package that cannot import is worse than one left out.

    Left out, it announces itself: the tests that need it say "not part of this
    build" and skip. Shipped without its dependency, `check_staged.py` raised
    ImportError at load — and whether the recipient saw an error or a green run
    with a silent skip came down to which exception type the test file happened to
    catch. The package's privacy check is not something to leave to that.
    """

    def test_every_tool_the_build_copies_can_import_what_it_needs(self):
        src = TOOL.read_text(encoding="utf-8")
        tools_dir = support.ROOT / "src" / "tools"
        shipped = set(re.findall(r'shared / "src" / "tools" / "([A-Za-z0-9_]+\.py)"', src))
        self.assertIn("check_staged.py", shipped, "the build no longer ships the privacy check")
        missing = []
        for name in sorted(shipped):
            p = tools_dir / name
            if not p.exists():
                continue
            for mod in re.findall(r"(?m)^\s*(?:import|from)\s+([A-Za-z0-9_]+)", p.read_text(encoding="utf-8")):
                if (tools_dir / f"{mod}.py").exists() and f"{mod}.py" not in shipped:
                    missing.append(f"{name} imports {mod}, which the build does not copy")
        self.assertEqual(missing, [], "; ".join(missing))


@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestTheGenomeFixtureIsTheOnlyGenomeFileAllowed(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.gen = self.root / "tests" / "fixtures" / "genome"
        self.gen.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _vcf(self, name: str, declared: bool):
        p = self.gen / name
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write("##fileformat=VCFv4.2\n")
            if declared:
                fh.write("##source=SYNTHETIC test fixture\n")
            fh.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n")
            fh.write("6\t18143724\trs1800462\tC\tG\t60\tPASS\tDP=32\tGT:DP\t0/1:32\n")
        return p

    def test_the_declared_fixture_passes(self):
        self._vcf("tiny.vcf.gz", declared=True)
        n, out = _audit(self.root)
        self.assertEqual(n, 0, out)

    def test_an_undeclared_vcf_in_the_same_place_does_not(self):
        self._vcf("tiny.vcf.gz", declared=False)
        n, out = _audit(self.root)
        self.assertEqual(n, 1, out)
        self.assertIn("declare", out,
                      "the refusal must say WHICH rule was broken — a flat ban on a file "
                      "somebody put there on purpose reads as a bug in the check")

    def test_a_vcf_in_a_data_slot_is_refused(self):
        p = self.root / "genome" / "personal.vcf.gz"
        p.parent.mkdir(parents=True)
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write("##fileformat=VCFv4.2\n##source=SYNTHETIC\n")
        n, out = _audit(self.root)
        self.assertGreaterEqual(n, 1, "a genome outside the fixture directory passed the audit")


@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestAQuarantinedBuildIsIgnoredByGitToo(unittest.TestCase):
    """The rules that keep the recipient's data out of git are anchored by name.

    `make_shareable.py` cannot always delete the previous build — iCloud, a network
    volume, the bridge to the owner's machine all refuse unlink — so it renames it
    to `Scholion-SHARE._stale3` and starts on an empty directory. That part is
    sound and the build refuses to call itself ready while one is lying there.

    What was not sound: every ignore rule it writes names the delivery folder —
    `/Scholion-SHARE/profile/*` — and a quarantined copy carries a different name.
    A recipient who had already filled the templates in, and whose build could not
    delete the old directory, had `Scholion-SHARE._stale3/profile/labs.json`
    excluded by nothing at all. Ninety-one such directories were sitting in the
    delivery root when this was found.

    Checked by running git rather than by matching the text of the rules: what
    matters is what git does with them.
    """

    DELIVERY = "Scholion-SHARE"

    def _ignored(self, ignore_text, paths):
        """Which of `paths` git would refuse to add under these rules."""
        import subprocess
        d = Path(tempfile.mkdtemp(prefix="ignore_"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        env = {"GIT_OPTIONAL_LOCKS": "0", "PATH": "/usr/bin:/bin:/usr/local/bin",
               "HOME": str(d), "GIT_CONFIG_GLOBAL": str(d / "nonexistent")}
        if subprocess.run(["git", "init", "-q", str(d)], capture_output=True,
                          env=env).returncode != 0:
            self.skipTest("git is not available")
        (d / ".gitignore").write_text(ignore_text, encoding="utf-8")
        out = set()
        for p in paths:
            (d / p).parent.mkdir(parents=True, exist_ok=True)
            (d / p).write_text("x", encoding="utf-8")
            r = subprocess.run(["git", "check-ignore", "-q", p], cwd=str(d),
                               capture_output=True, env=env)
            if r.returncode == 0:
                out.add(p)
        return out

    def _root_rules(self):
        """The ignore text the builder writes at the delivery root, without building."""
        d = Path(tempfile.mkdtemp(prefix="rules_"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        shared = d / self.DELIVERY
        return ("# generated\n"
                f"/{shared.name}/profile/*\n!/{shared.name}/profile/*.md\n"
                f"/{shared.name}/genome/*\n!/{shared.name}/genome/README.md\n"
                f"/{shared.name}/raw/\n/{shared.name}/work/\n/{shared.name}/archive/\n"
                "*._stale*/\n*.vcf*\n*.bam\n*.pdf\n")

    def test_the_builder_still_writes_the_rule(self):
        """Read out of the source, so the test fails if the line is dropped there."""
        self.assertIn('"*._stale*/', TOOL.read_text(encoding="utf-8"),
                      "the builder no longer writes a rule for quarantined directories")

    def test_a_quarantined_profile_is_excluded(self):
        paths = [f"{self.DELIVERY}/profile/labs.json",
                 f"{self.DELIVERY}._stale3/profile/labs.json",
                 f"{self.DELIVERY}._stale/genome/variants.txt"]
        ignored = self._ignored(self._root_rules(), paths)
        self.assertEqual(sorted(ignored), sorted(paths),
                         "a previous build's copy of the recipient's data is not excluded: "
                         + ", ".join(sorted(set(paths) - ignored)))
        # The control, in the same test: the rules WITHOUT that one line leave the
        # quarantined copies exposed. Without this the check would pass on any set
        # of rules broad enough, and it would never be seen failing.
        before = self._ignored(self._root_rules().replace("*._stale*/\n", ""), paths)
        self.assertEqual(before, {paths[0]},
                         "the fixture no longer distinguishes the delivery folder from a "
                         "quarantined copy of it, so the check proves nothing")

    def test_the_repository_ignores_them_as_well(self):
        rules = (support.ROOT / ".gitignore")
        if not rules.exists():
            self.skipTest("no .gitignore in this build")
        self.assertIn("*._stale*/", rules.read_text(encoding="utf-8"),
                      "a quarantined build inside the project folder would be added by `git add -A`")

    def test_an_ordinary_directory_is_not_swept_up(self):
        """The pattern has to be narrow enough not to hide real work."""
        ignored = self._ignored("*._stale*/\n", ["src/scholion/core.py", "docs/VERSIONING.md"])
        self.assertEqual(ignored, set())

@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestAnUndeletableBuildIsMovedOutOfThePackage(unittest.TestCase):
    """Where a leftover lands decides whether the package is still a package.

    The quarantine solved the first half of the problem — after it, a build could
    not confuse an old file with a new one. It created the second half: the
    previous package was moved aside *inside the delivery folder*, so zipping that
    folder shipped two versions, and every ignore rule the builder writes is
    anchored to the delivery folder's own name — `profile._stale3/`, holding the
    recipient's filled-in templates, matched none of them.

    The build then refused to declare itself ready, which was the right call and
    the wrong remedy: the person cleaned up by hand, the next build made more, and
    ninety-one directories accumulated. Moving them outside makes the package
    correct the moment the audit passes, and lets the next build drain the pile
    instead of adding to it.

    An unlinkable directory is simulated the way the real filesystem behaves:
    `rmtree(ignore_errors=True)` returns quietly and the directory is still there.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="quarantine_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.out = self.tmp / "Scholion-SHARE"
        (self.out / "profile").mkdir(parents=True)
        (self.out / "profile" / "labs.json").write_text("{}", encoding="utf-8")
        ms._QUARANTINED.clear()
        self.addCleanup(ms._QUARANTINED.clear)

    def _with_unlink_refused(self):
        """Make rmtree a no-op, as it is on a filesystem that forbids unlink."""
        real = ms.shutil.rmtree
        ms.shutil.rmtree = lambda *a, **kw: None
        self.addCleanup(setattr, ms.shutil, "rmtree", real)

    def _quarantine(self, d, qroot):
        """The builder narrates what it moved; a test run should not."""
        with redirect_stdout(io.StringIO()):
            ms._clear_or_quarantine(d, qroot)

    def test_the_leftover_lands_beside_the_package_not_inside_it(self):
        self._with_unlink_refused()
        qroot = ms.quarantine_root(self.out)
        self._quarantine(self.out / "profile", qroot)
        inside = [p.name for p in self.out.iterdir()]
        self.assertEqual(inside, [], "a copy of the previous build is still inside the "
                                     "delivery folder: " + ", ".join(inside))
        self.assertTrue(qroot.exists(), "nothing was quarantined at all")
        self.assertNotIn(self.out, qroot.parents,
                         "the quarantine directory is under the package it was meant to leave")
        self.assertTrue((qroot / "profile" / "labs.json").exists(),
                        "the leftover was lost rather than moved — it has to stay readable, "
                        "it may be the only copy of something")

    def test_the_next_build_drains_what_the_last_one_could_not_remove(self):
        """The pile does not grow while the refusal lasts, and clears when it lifts."""
        qroot = ms.quarantine_root(self.out)
        (qroot / "profile").mkdir(parents=True)
        (qroot / "profile" / "labs.json").write_text("{}", encoding="utf-8")
        self.assertEqual(ms.drain_quarantine(qroot), 0, "a deletable quarantine was not deleted")
        self.assertFalse(qroot.exists())

    def test_a_quarantine_that_cannot_be_removed_is_counted_rather_than_hidden(self):
        qroot = ms.quarantine_root(self.out)
        (qroot / "profile").mkdir(parents=True)
        self._with_unlink_refused()
        self.assertEqual(ms.drain_quarantine(qroot), 1,
                         "leftovers that survived the drain are reported as zero")

    def test_repeated_quarantines_do_not_collide(self):
        self._with_unlink_refused()
        qroot = ms.quarantine_root(self.out)
        for _ in range(3):
            (self.out / "profile").mkdir(parents=True, exist_ok=True)
            (self.out / "profile" / "labs.json").write_text("{}", encoding="utf-8")
            self._quarantine(self.out / "profile", qroot)
        self.assertEqual(sorted(p.name for p in qroot.iterdir()),
                         ["profile", "profile-2", "profile-3"])




@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestTheBuilderCarriesNoOwnerIdentifiers(unittest.TestCase):
    """The script that removes personal data must not contain any.

    `make_shareable.py` ships inside the package — it has to, it IS the build
    procedure and a recipient who cannot rebuild cannot verify. For a long time it
    also held eleven of the owner's identifiers: surname in two alphabets, an
    e-mail handle, a date of birth, a sample number, a GitHub account, a home
    path. They were base64-encoded, and the comment beside them said why — so
    that the script "holds no owner identifiers and does not fail its own audit".

    That is not passing an audit. The audit compares substrings; an encoded string
    is a substring of nothing, so the check reported clean on a file carrying the
    exact data it exists to stop. One line of Python reverses it. An outside
    reviewer decoded the list and read it back to us.

    The remedy is not to document the trace but not to have one: the list is read
    at build time from `.personal_patterns`, which is in `.gitignore` and never
    ships. What remains in the package is the copyright line Apache-2.0 requires,
    and that has its own signature-guarded exception.
    """

    SOURCE = support.ROOT / "src" / "tools" / "make_shareable.py"

    def _patterns(self):
        f = support.ROOT / ".personal_patterns"
        if not f.exists():
            self.skipTest("no .personal_patterns on this machine — nothing to check against")
        out = []
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("warn:"):
                line = line[5:].strip()
            if line.startswith("re:"):
                continue                      # a shape, not a value
            if line.startswith("sub:"):
                line = line[4:].split("=>")[0].strip()
            if line:
                out.append(line.lower())
        return out

    @staticmethod
    def _encodings(value: str):
        """base64 of the value at all three alignments — as it looks embedded in text."""
        b = value.encode()
        for pad in range(3):
            s = base64.b64encode(b" " * pad + b).decode()
            yield s[(pad * 4) // 3:].rstrip("=").lower()

    def test_the_source_holds_no_identifier_in_plain_text(self):
        text = self.SOURCE.read_text(encoding="utf-8").lower()
        found = [i + 1 for i, v in enumerate(self._patterns()) if v in text]
        self.assertEqual(found, [], "the builder names owner identifiers outright; positions in "
                                    ".personal_patterns: " + ", ".join(map(str, found)))

    def test_the_source_holds_no_identifier_in_an_encoded_form(self):
        """The exact defect: encoded, so the substring audit could not see it."""
        text = self.SOURCE.read_text(encoding="utf-8").lower()
        found = []
        for i, v in enumerate(self._patterns()):
            if any(len(e) >= 8 and e in text for e in self._encodings(v)):
                found.append(i + 1)
        self.assertEqual(found, [], "an owner identifier is back in the builder in encoded form; "
                                    "positions in .personal_patterns: " + ", ".join(map(str, found)))

    def test_the_list_is_read_from_the_file_rather_than_compiled_in(self):
        text = self.SOURCE.read_text(encoding="utf-8")
        self.assertIn(".personal_patterns", text)
        self.assertIn("def load_personal", text)
        self.assertNotIn("_SUBSRC", text, "the compiled-in substitution table is back")

    def test_a_build_without_the_file_refuses_to_report_a_clean_package(self):
        """Fail closed: a check that could not run may not look like one that passed."""
        d = Path(tempfile.mkdtemp(prefix="nopatterns_"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        with self.assertRaises(SystemExit) as e:
            with redirect_stdout(io.StringIO()):
                ms.load_personal(d, required=True)
        self.assertIn(".personal_patterns", str(e.exception))

    def test_a_fork_may_say_so_and_is_told_that_it_did(self):
        d = Path(tempfile.mkdtemp(prefix="fork_"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ms.load_personal(d, required=False)
        self.addCleanup(ms.load_personal, support.ROOT, False)
        self.assertIn("NOT checked", buf.getvalue(),
                      "an unchecked build reads exactly like a checked one")


@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestTheAuditReadsWhatWasEncoded(unittest.TestCase):
    """A substring check that only sees plain text is a check with a known bypass.

    This is the general form of the defect above, and it is worth having as its
    own rule: the next person to encode an identifier will do it for the same
    well-meant reason — to get a file past its own check — and the audit has to
    see through that without anybody remembering to look.
    """

    def setUp(self):
        f = support.ROOT / ".personal_patterns"
        if not f.exists():
            self.skipTest("no .personal_patterns on this machine")
        with redirect_stdout(io.StringIO()):
            ms.load_personal(support.ROOT, required=True)
        self.addCleanup(lambda: (setattr(ms, "DENY", []), setattr(ms, "SUBSTITUTIONS", [])))
        self.token = next((d for d in ms.DENY if isinstance(d, str)), None)
        self.assertTrue(self.token, "the denylist holds no plain-string entry to test with")
        self.root = Path(tempfile.mkdtemp(prefix="audit_b64_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _audit(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            n = ms.audit(self.root)
        return n, buf.getvalue()

    def test_a_plainly_written_identifier_is_caught(self):
        (self.root / "note.md").write_text(f"see {self.token}\n", encoding="utf-8")
        n, _ = self._audit()
        self.assertGreaterEqual(n, 1)

    def test_the_same_identifier_base64_encoded_is_caught_too(self):
        enc = base64.b64encode(self.token.encode()).decode()
        (self.root / "note.md").write_text(f"see {enc}\n", encoding="utf-8")
        n, out = self._audit()
        self.assertGreaterEqual(n, 1, "an encoded identifier passes the audit — the bypass that "
                                      "let the builder's own denylist ship for months")
        self.assertIn("note.md", out)

    def test_the_report_does_not_print_the_identifier_it_found(self):
        """Reporting a leak by quoting it repeats the leak one layer up."""
        (self.root / "note.md").write_text(f"see {self.token}\n", encoding="utf-8")
        _, out = self._audit()
        self.assertNotIn(self.token.lower(), out.lower(),
                         "the build log quotes the identifier verbatim")
        self.assertIn(".personal_patterns", out, "the report gives no way to look the entry up")

    def test_an_ordinary_base64_blob_is_not_a_violation(self):
        """Decoding everything must not make the audit cry wolf on real data."""
        (self.root / "icon.md").write_text(
            "data:image/png;base64," + base64.b64encode(bytes(range(256)) * 4).decode() + "\n",
            encoding="utf-8")
        n, _ = self._audit()
        self.assertEqual(n, 0, "a binary blob decoded to nonsense was reported as an identifier")

@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
class TestTheEditionOfTheSkillThatShipped(unittest.TestCase):
    """One line of build() decides which of two editions the recipient gets, and
    until 17.08.2026 nothing checked its work.

    The owner's edition cannot simply be put on the private list: the package
    needs a file at `src/skill/SKILL.md`, so omitting it is not a possible
    outcome — substitution is. And the identifier audit is blind to it on
    purpose: those 116 KB hold diplotypes, phenotypes and per-drug caveats, and
    not one name, e-mail or sample number. Every guard the builder had looks for
    a person, and this file names no one.

    So the check is on what separates the editions instead: the heading
    sync_rules.py writes above the owner's qualifications, plus the demand that
    the three copies in the package be one edition and not three.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="audit_skill_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.paths = []
        for rel in ("src/skill", "src/scholion/skill", "scholion-skill"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
            self.paths.append(self.root / rel / "SKILL.md")

    def _write(self, *texts):
        for q, s in zip(self.paths, texts):
            q.write_text(s, encoding="utf-8")

    def test_the_shared_edition_in_all_three_places_is_clean(self):
        shared = "# Scholion\n\nWhat is true for any user.\n"
        self._write(shared, shared, shared)
        n, out = _audit(self.root)
        self.assertEqual(n, 0, "a correct package was refused:\n" + out)

    def test_the_owner_edition_shipping_is_caught(self):
        owner = "# Scholion\n\n## " + ms.OWNER_BLOCK_MARK + "\n\nCYP2C19 *1/*17.\n"
        self._write(owner, owner, owner)
        n, out = _audit(self.root)
        self.assertGreaterEqual(n, 1, "the owner's clinical key shipped and the audit "
                                      "said nothing — it holds no identifier to catch")
        self.assertIn("OWNER", out.upper())

    def test_one_copy_left_behind_is_caught(self):
        """The failure that actually threatens: the substitution works at two of
        the three paths. Byte-identity is what notices this, not the marker."""
        shared = "# Scholion\n\nWhat is true for any user.\n"
        self._write(shared, shared, shared + "one stale line\n")
        n, out = _audit(self.root)
        self.assertGreaterEqual(n, 1, "three paths carried two editions and the audit passed")
        self.assertIn("SKILL.md", out)

    def test_the_marker_is_the_one_the_edition_tests_use(self):
        """A constant that drifted from the canon would leave both sides green
        while checking nothing in common."""
        canon = support.ROOT / "tests" / "test_skill_editions.py"
        if not canon.exists():
            self.skipTest("the edition tests are not part of this build")
        self.assertIn(ms.OWNER_BLOCK_MARK, canon.read_text(encoding="utf-8"))


class TestTheZipCarriesExecuteBits(unittest.TestCase):
    """A zip is not the only way to lose the `+x` bit — writing one badly is.

    An empirical review deployed v2.19.0 from a zip and found `bin/crossread`,
    `run_tests.sh` and `src/tools/nof1_quick_log.sh` all non-executable. The
    build itself was innocent: `_fix_exec_bits` had already set the bit on disk.
    Nothing in the project turned the built folder into the `.zip` that was
    actually handed over, so a person or another tool did it by hand — and one
    common way of writing a zip in Python (`ZipFile.writestr` with a bare
    `ZipInfo`, as opposed to `ZipFile.write` or `shutil.make_archive`, both of
    which read `os.stat()`) drops every permission bit silently.

    `--zip` closes that gap by owning the last step instead of leaving it to
    whoever needs a file to attach. This class proves it two ways: the archive
    `--zip` actually writes has the bits, AND `_verify_zip_exec_bits` — the
    function guarding it — would have caught the exact failure the review
    reported, on a zip built the way that failure happens.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scholion-zip-"))
        self.out = self.tmp / "Scholion-SHARE"
        (self.out / "src" / "tools").mkdir(parents=True)
        (self.out / "bin").mkdir()
        self.scripts = ("run_tests.sh", "bin/crossread", "src/tools/nof1_quick_log.sh")
        for rel in self.scripts:
            f = self.out / rel
            f.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
            f.chmod(0o755)
        # a file the audit must not mistake for a script that needs +x
        (self.out / "README.md").write_text("hello\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bits_in_zip(self, zip_path: Path) -> dict:
        with zipfile.ZipFile(zip_path) as z:
            return {i.filename: (i.external_attr >> 16) & 0o777 for i in z.infolist()}

    def test_the_candidate_list_has_no_duplicate(self):
        """`run_tests.sh` matches `rglob('*.sh')` on its own; an earlier version of
        this function also appended it explicitly and listed it twice."""
        rels = [p.relative_to(self.out).as_posix() for p in ms._exec_bit_candidates(self.out)]
        self.assertEqual(len(rels), len(set(rels)), f"a script is listed twice: {rels}")
        self.assertEqual(set(rels), set(self.scripts))

    def test_write_zip_preserves_the_bit_for_every_script(self):
        zp = ms._write_zip(self.out)
        self.addCleanup(lambda: zp.unlink(missing_ok=True))
        bits = self._bits_in_zip(zp)
        for rel in self.scripts:
            key = f"{self.out.name}/{rel}"
            with self.subTest(file=rel):
                self.assertIn(key, bits, "the script did not make it into the archive at all")
                self.assertTrue(bits[key] & 0o111,
                                f"{rel}: no execute bit inside the zip ({oct(bits[key])})")

    def test_write_zip_lands_next_to_out_not_inside_it(self):
        """`.zip` is itself in FORBIDDEN_SUFFIXES: one inside the audited folder
        would fail the very audit that is supposed to wave the package through."""
        zp = ms._write_zip(self.out)
        self.addCleanup(lambda: zp.unlink(missing_ok=True))
        self.assertEqual(zp.parent, self.out.parent)
        self.assertNotIn(zp, list(self.out.rglob("*")))

    def test_verify_passes_on_the_zip_write_zip_actually_produces(self):
        zp = ms._write_zip(self.out)
        self.addCleanup(lambda: zp.unlink(missing_ok=True))
        self.assertEqual(ms._verify_zip_exec_bits(zp, self.out), [])

    def test_verify_catches_the_exact_failure_the_review_reported(self):
        """Reproduces the reported defect directly: read bytes into memory, write
        them with a bare ZipInfo. Run against the OLD `_write_zip` (before this
        fix) this is what the recipient's archive actually contained."""
        bad = self.tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            for p in ms._exec_bit_candidates(self.out):
                rel = p.relative_to(self.out.parent).as_posix()
                z.writestr(zipfile.ZipInfo(rel), p.read_bytes())   # no os.stat() involved
        lost = ms._verify_zip_exec_bits(bad, self.out)
        self.assertEqual(set(lost), {f"{self.out.name}/{s}" for s in self.scripts},
                         "the check must name every script that lost its bit, not just one")

    def test_verify_reports_a_script_missing_from_the_archive(self):
        zp = ms._write_zip(self.out)
        self.addCleanup(lambda: zp.unlink(missing_ok=True))
        # a zip missing an expected entry entirely — not just missing the bit
        trimmed = self.tmp / "trimmed.zip"
        with zipfile.ZipFile(zp) as src, zipfile.ZipFile(trimmed, "w") as dst:
            for item in src.infolist():
                if item.filename.endswith("run_tests.sh"):
                    continue
                dst.writestr(item, src.read(item.filename))
        lost = ms._verify_zip_exec_bits(trimmed, self.out)
        self.assertTrue(any("run_tests.sh" in l and "missing" in l for l in lost), lost)


class TestAReachIntoTheBuilderIsGuarded(unittest.TestCase):
    """The guard has to be attached to the next one of these too.

    Twice now a test called the builder while running INSIDE the package, where
    `share/` does not exist and build() exits on its first line. Both times the
    suite was red on the public runner and publish.yml — which runs
    ./run_tests.sh before publishing — could not publish. Both times the
    guard was added to the one test that had failed.

    This checks the property instead of the instance: a module that reaches into
    the builder must also name the predicate that says whether reaching is
    possible here. It is a coarse check on purpose — it costs nothing and it
    fires on the next author, who will not have read this docstring.
    """

    def test_a_module_that_builds_also_asks_where_it_is(self):
        for mod in sorted((support.ROOT / "tests").glob("test_*.py")):
            src = mod.read_text(encoding="utf-8")
            if "ms.main(" not in src and "ms.build(" not in src:
                continue
            self.assertIn("IN_SOURCE_REPO", src,
                          f"{mod.name} calls the builder but never asks whether this "
                          f"tree can build: inside the package it cannot, and the "
                          f"publish workflow runs the suite before it publishes")


@unittest.skipIf(ms is None, "make_shareable.py is not part of this build")
@unittest.skipUnless(support.IN_SOURCE_REPO,
                     "this tree is a package, not the repository it was built from")
class TestTheMainEntryPointRefusesToHandOverABrokenZip(unittest.TestCase):
    """`main(["--zip"])`, end to end, against a real repository tree — not the
    synthetic fixture above. The synthetic case proves the mechanism; this one
    proves the mechanism is actually wired into the command a person runs."""

    def test_zip_flag_produces_a_verified_archive(self):
        """Built the way a PUBLIC runner builds it — `--no-personal-patterns`.

        Not a convenience. This test invokes `main()`, and `main()` refuses to
        report a clean package when `.personal_patterns` is absent — deliberately,
        since a build that cannot check must not look like one that passed. On a
        clean CI checkout that file is absent by design (it is in `.gitignore`),
        so without this flag the test aborts, `run_tests.sh` exits non-zero, and
        the publish workflow never reaches the registry. Two correct decisions —
        the fail-closed audit and this end-to-end zip check — combined into a
        release that could not ship.

        The flag costs nothing here: what is under test is the archive machinery
        and the execute bits inside it, not the identifier denylist, and the
        public build is exactly the mode a recipient's copy is produced in.
        """
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "Scholion-SHARE"
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = ms.main([str(out), "--zip", "--no-personal-patterns"])
            self.assertEqual(code, 0, buf.getvalue()[-1000:])
            zp = out.with_name(out.name + ".zip")
            self.assertTrue(zp.exists(), "main() reported success but wrote no archive")
            with zipfile.ZipFile(zp) as z:
                bits = {i.filename: (i.external_attr >> 16) for i in z.infolist()}
            for rel in ("run_tests.sh", "bin/crossread", "src/tools/nof1_quick_log.sh"):
                key = f"{out.name}/{rel}"
                with self.subTest(file=rel):
                    self.assertIn(key, bits)
                    self.assertTrue(bits[key] & 0o111, f"{rel} lost +x in the real build's zip")
            self.assertIn("verified INSIDE the archive", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
