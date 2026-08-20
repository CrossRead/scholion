"""The one genome file allowed into the project, and what keeps it the only one.

The test suite needs a VCF. Not a large one — two positions is enough to show
that a position with no row in the file is not the same as a position read as the
reference — but a VCF, in a project whose whole safety posture is that genomic
formats never enter the repository and never enter the package. Four gates say
so: `.gitignore`, the pre-commit check, the build audit, and the `.gitignore`
the build writes for the recipient.

So the exception exists, and this file is what makes it an exception rather than
a hole. Two things are checked, and the second matters more than the first:

* the fixture really does get through all four gates — otherwise the regression
  it guards is covered on the owner's machine and nowhere else;
* nothing else does. A real call set renamed `tiny.vcf.gz` and dropped into the
  fixture directory is still refused, by size, by row count and by the absence of
  a declaration.

The first would be noticed by anybody running the tests. The second would be
noticed by nobody — which is why it is written down.
"""
from __future__ import annotations

import gzip
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

ROOT = support.ROOT
TOOLS = ROOT / "src" / "tools"
FIXTURE = ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz"


def _load(name):
    path = TOOLS / f"{name}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sf = _load("synthetic_fixture")


def _write_vcf(path: Path, header_extra: str = "", rows: int = 1) -> Path:
    lines = ["##fileformat=VCFv4.2"]
    if header_extra:
        lines.append(header_extra)
    lines.append("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE1")
    for i in range(rows):
        lines.append(f"1\t{10000 + i}\trs{i}\tC\tG\t60\tPASS\tDP=30\tGT:DP\t0/1:30")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


@unittest.skipIf(sf is None, "synthetic_fixture.py is not part of this build")
class TestTheFixtureQualifies(unittest.TestCase):

    def test_the_shipped_fixture_passes_the_gate(self):
        ok, why = sf.check(FIXTURE)
        self.assertTrue(ok, f"the project's own fixture is refused: {why}")

    def test_its_index_passes_with_it(self):
        ok, why = sf.check(Path(str(FIXTURE) + ".tbi"))
        self.assertTrue(ok, why)

    def test_it_is_small_enough_to_be_obviously_invented(self):
        self.assertLess(FIXTURE.stat().st_size, sf.MAX_BYTES)

    def test_it_says_so_in_its_own_header(self):
        text = gzip.open(FIXTURE, "rt", encoding="utf-8").read()
        header = " ".join(l for l in text.splitlines() if l.startswith("##")).upper()
        self.assertTrue(any(w in header for w in ("SYNTHETIC", "FIXTURE")),
                        "the fixture no longer declares itself invented — the gate "
                        "would refuse it, and rightly")


@unittest.skipIf(sf is None, "synthetic_fixture.py is not part of this build")
class TestNothingElseGetsThrough(unittest.TestCase):
    """Each of these is the exception being used as a way in, and refused."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = self.tmp / "tests" / "fixtures" / "genome"
        self.dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_vcf_that_does_not_declare_itself_is_refused(self):
        p = _write_vcf(self.dir / "real.vcf.gz")
        ok, why = sf.check(p)
        self.assertFalse(ok)
        self.assertIn("declare", why)

    def test_the_ceiling_is_low_enough_to_mean_something(self):
        """Read the number, not just the comparison.

        A test that writes `MAX_ROWS + 1` rows and expects a refusal passes for
        any ceiling whatsoever, including one raised to a million — it would only
        take longer to run. The value itself is therefore asserted: a fixture is a
        handful of positions, and anything that needs hundreds is not a fixture.
        """
        self.assertLessEqual(sf.MAX_ROWS, 200)
        self.assertLessEqual(sf.MAX_BYTES, 1024 * 1024)

    def test_a_declared_vcf_over_the_row_ceiling_is_refused(self):
        p = _write_vcf(self.dir / "big.vcf.gz", "##source=SYNTHETIC",
                       rows=min(sf.MAX_ROWS, 500) + 1)
        ok, why = sf.check(p)
        self.assertFalse(ok, "a declaration does not raise the ceiling — that is the point "
                             "of having a ceiling as well as a declaration")
        self.assertIn("positions", why)

    def test_a_declared_vcf_over_the_size_ceiling_is_refused(self):
        p = self.dir / "huge.vcf.gz"
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write("##fileformat=VCFv4.2\n##source=SYNTHETIC\n")
            fh.write("#CHROM\tPOS\tID\tREF\tALT\n")
        # padded past the ceiling without adding rows: size is judged on its own
        with open(p, "ab") as fh:
            fh.write(b"\0" * (sf.MAX_BYTES + 1))
        ok, why = sf.check(p)
        self.assertFalse(ok)
        self.assertIn("ceiling", why)

    def test_the_same_file_outside_the_fixture_directory_is_refused(self):
        p = _write_vcf(self.tmp / "tiny.vcf.gz", "##source=SYNTHETIC test fixture")
        ok, why = sf.check(p)
        self.assertFalse(ok, "the directory is part of the rule: a declared fixture in a "
                             "data slot is a genome in a data slot")

    def test_an_index_without_its_vcf_is_refused(self):
        p = self.dir / "orphan.vcf.gz.tbi"
        p.write_bytes(b"\0" * 20)
        self.assertFalse(sf.check(p)[0])

    def test_a_bam_is_still_a_bam(self):
        p = self.dir / "tiny.bam"
        p.write_bytes(b"BAM\1")
        self.assertFalse(sf.check(p)[0])


cs = _load("check_staged")


@unittest.skipIf(cs is None or sf is None, "check_staged.py is not part of this build")
class TestTheCommitGateJudgesByContentToo(unittest.TestCase):
    """The pre-commit check is where the exception is most tempting to widen.

    `.gitignore` had to name a directory, because git cannot read a file. Nothing
    forces this check to do the same — and if it did, the directory name would be
    the whole rule, and a real call set copied into it would be committed. So the
    gate is asked the questions directly.
    """

    # The check reads `ROOT / <repo-relative path>`, so the temptation is to put a
    # test file into the real fixture directory and delete it afterwards. That was
    # done once and the deletion did not happen: on the owner's filesystem `unlink`
    # is forbidden, `tearDown` swallowed the error, and the next `check_staged
    # --all` stopped on a file the tests had left there. A test that relies on
    # being able to delete does not belong in a project that cannot.
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = self.tmp / "tests" / "fixtures" / "genome"
        self.dir.mkdir(parents=True)
        self._root = cs.ROOT
        cs.ROOT = self.tmp

    def tearDown(self):
        cs.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, name, declared):
        p = self.dir / name
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write("##fileformat=VCFv4.2\n")
            if declared:
                fh.write("##source=SYNTHETIC test fixture\n")
            fh.write("#CHROM\tPOS\tID\tREF\tALT\n1\t1\trs1\tC\tG\n")
        return f"tests/fixtures/genome/{name}"

    def test_the_real_fixture_is_allowed(self):
        rel = "tests/fixtures/genome/tiny.vcf.gz"
        cs.ROOT = self._root                      # the shipped file, read and not written
        self.assertEqual(cs.check_paths([rel]), [])

    def test_an_undeclared_vcf_in_the_fixture_directory_is_blocked(self):
        rel = self._make("smuggled.vcf.gz", declared=False)
        bad = cs.check_paths([rel])
        self.assertEqual(len(bad), 1, "the fixture directory became a way in")
        self.assertEqual(bad[0][2], "block")

    def test_a_vcf_anywhere_else_is_blocked(self):
        self.assertEqual(len(cs.check_paths(["genome/personal.vcf.gz"])), 1)

    def test_a_bam_in_the_fixture_directory_is_blocked(self):
        self.assertEqual(len(cs.check_paths(["tests/fixtures/genome/tiny.bam"])), 1)


class TestGitDoesNotIgnoreTheFixture(unittest.TestCase):
    """The gate may allow the file and git may still drop it silently.

    This is not hypothetical: `.gitignore` banned `*.vcf.gz` and `*.tbi` outright,
    so the first version of the fixture was invisible to `git add`. The test that
    depends on it would have gone into the package alone, and the failure mode is
    the quiet one — the suite passes, having skipped the case it exists for.
    """

    def test_the_fixture_is_not_ignored(self):
        if not (ROOT / ".git").exists():
            self.skipTest("not a git working tree")
        if not shutil.which("git"):
            self.skipTest("git is not installed")
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
        for name in ("tiny.vcf.gz", "tiny.vcf.gz.tbi"):
            rel = f"tests/fixtures/genome/{name}"
            r = subprocess.run(["git", "check-ignore", "-q", rel],
                               cwd=ROOT, env=env, capture_output=True, stdin=subprocess.DEVNULL)
            self.assertNotEqual(r.returncode, 0,
                                f"{rel} is ignored by git — it would never be committed, "
                                f"and the test that needs it would ship without it")

    def test_the_negation_covers_only_the_fixture_directory(self):
        """An exception that widened would be worse than no exception at all."""
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        negations = [l.strip() for l in text.splitlines()
                     if l.strip().startswith("!") and (".vcf" in l or ".tbi" in l)]
        self.assertTrue(negations, ".gitignore no longer re-includes the fixture")
        for line in negations:
            self.assertIn("tests/fixtures/genome/", line,
                          f"the genome ban is lifted outside the fixture directory: {line}")


if __name__ == "__main__":
    unittest.main()
