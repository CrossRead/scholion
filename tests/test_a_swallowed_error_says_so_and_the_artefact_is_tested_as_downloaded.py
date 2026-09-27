"""Two gates of 0.5.9's stabilisation, held by running them (tasks 209 and 210).

* A broad `except` that swallows an error must say why that is safe
  (`# quiet: …`), or stop being silent. Checked on invented files, so the rule is
  tested and not only obeyed, and on the tree itself.
* The in-package gate runs the suite in a copy WITHOUT `.git`, which is what a
  release archive unpacks into; the package folder the publisher builds is also
  a git working tree, and a test that depended on `.git` passed there and failed
  for an outside reviewer.
* A gene report that is a refusal is rendered as one — never as a count of zero
  variants. Two refusals were missing from the list the renderer used.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import support

TOOLS = support.ROOT / "src" / "tools"


def _load_checker():
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_quiet_excepts", TOOLS / "check_quiet_excepts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class TestASilentBroadHandlerMustSayWhy(unittest.TestCase):

    def setUp(self):
        self.q = _load_checker()
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scan(self, body: str):
        p = self.tmp / "m.py"
        p.write_text(textwrap.dedent(body), encoding="utf-8")
        return self.q.scan_file(p)

    def test_an_unexplained_one_is_named(self):
        broad, explained, unexplained = self._scan("""
            def f():
                try:
                    return read()
                except Exception:
                    return []
        """)
        self.assertEqual((1, [], [5]), (broad, explained, unexplained))

    def test_a_quiet_comment_on_the_except_or_the_body_line_explains_it(self):
        for src in ("""
            try:
                x = 1
            except Exception:  # quiet: a cache miss, the value is read again
                pass
        """, """
            try:
                x = 1
            except BaseException:
                pass  # quiet: cleanup only
        """):
            with self.subTest(src=src):
                self.assertEqual([], self._scan(src)[2])

    def test_a_bare_except_and_a_tuple_with_exception_are_broad(self):
        for head in ("except:", "except (OSError, Exception):"):
            with self.subTest(head=head):
                _, _, bad = self._scan(f"try:\n    x = 1\n{head}\n    continue_ = None\n")
                self.assertEqual([], bad, "an assignment is not silence")
                _, _, bad = self._scan(f"for i in []:\n    try:\n        x = 1\n    {head}\n        continue\n")
                self.assertEqual([4], bad)

    def test_a_narrow_handler_or_one_that_says_something_is_not_counted(self):
        broad, _, bad = self._scan("""
            try:
                x = 1
            except ValueError:
                pass
            try:
                y = 2
            except Exception as exc:
                raise RuntimeError("could not read") from exc
            try:
                z = 3
            except Exception:
                return {"status": "unreadable"}
        """.replace("return", "result ="))
        self.assertEqual((2, []), (broad, bad))

    def test_the_tree_has_none_unexplained(self):
        report = self.q.scan(support.ROOT)
        bad = [f"{f}:{n}" for f, v in report.items() for n in v["unexplained"]]
        self.assertEqual([], bad)


@unittest.skipUnless(shutil.which("bash") and shutil.which("tar"), "needs bash and tar")
class TestTheArtefactIsTestedWithoutGit(unittest.TestCase):

    SCRIPT = TOOLS / "test_the_artefact.sh"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.pkg = self.tmp / "Scholion-SHARE"
        (self.pkg / ".git").mkdir(parents=True)
        (self.pkg / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (self.pkg / "marker.txt").write_text("the package\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _suite(self, body: str) -> None:
        p = self.pkg / "run_tests.sh"
        p.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
        p.chmod(0o755)

    def _run(self):
        env = dict(os.environ, TMPDIR=str(self.tmp))
        return subprocess.run(["bash", str(self.SCRIPT), str(self.pkg)], capture_output=True,
                              text=True, env=env, timeout=60, stdin=subprocess.DEVNULL)

    def test_the_suite_sees_no_git_and_not_the_package_folder(self):
        self._suite(f'[ ! -e .git ] || exit 7\n[ "$(pwd -P)" != "{self.pkg}" ] || exit 8\n'
                    '[ -f marker.txt ] || exit 9\nexit 0')
        r = self._run()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertTrue((self.pkg / ".git").is_dir(), "the package itself is left as it was")
        self.assertEqual([], [p for p in self.tmp.iterdir() if p.name.startswith("scholion-artefact")],
                         "the temporary copy is removed")

    def test_a_red_suite_is_red(self):
        self._suite("exit 3")
        self.assertEqual(3, self._run().returncode)

    def test_no_suite_is_not_a_pass(self):
        r = self._run()
        self.assertEqual(5, r.returncode)
        self.assertIn("run_tests.sh is missing", r.stderr)

    @unittest.skipUnless(support.IN_SOURCE_REPO, "the publisher lives in the source repository only")
    def test_the_publisher_uses_it(self):
        text = (TOOLS / "publish_share.sh").read_text(encoding="utf-8")
        self.assertIn('test_the_artefact.sh" "$SHARE_DIR"', text)
        self.assertNotIn('( cd "$SHARE_DIR" && ./run_tests.sh )', text)


class TestAGeneReportRefusalIsNeverACount(unittest.TestCase):

    def test_every_refusal_prints_its_message(self):
        from scholion import format as _f  # noqa: F401  (the facade loads the screens)
        from scholion import format_genome as FG
        loc = {"gene": "BRCA1", "chrom": "17", "start": 1, "end": 2, "assembly": "GRCh38"}
        for status in ("assembly_mismatch", "contig_not_in_file", "needs_index",
                       "not_sequenced", "unreadable_file", "a_status_added_later"):
            with self.subTest(status=status):
                out = FG._gene_region_report({"status": status, "gene": "BRCA1", "location": loc,
                                              "message": "MESSAGE-" + status,
                                              "variants": [], "counts": {"total": 0}})
                self.assertIn("MESSAGE-" + status, out)
                self.assertNotIn(FG._t("gene.counts", total=0, coding=0, consequential=0), out)


class TestACachedNoCdsFromAFailedRequestIsAskedAgain(unittest.TestCase):

    def test_an_ensembl_entry_with_a_transcript_and_no_cds_is_not_trusted(self):
        from unittest import mock
        from scholion import genes
        stale = {"gene": "BRCA1", "chrom": "17", "start": 1, "end": 2, "strand": "-",
                 "transcript": "ENST00000357654", "cds": [], "source": "ensembl"}
        fresh = dict(stale, cds=[["17", 1, 2]])
        with mock.patch.object(genes, "_load_cache", return_value={"BRCA1": stale}), \
                mock.patch.object(genes, "_save_cache"), \
                mock.patch.object(genes, "gff3_candidates", return_value=[]), \
                mock.patch.object(genes, "from_ensembl", return_value=fresh):
            self.assertEqual([["17", 1, 2]], genes.resolve("BRCA1")["cds"])
        kept = dict(stale, transcript=None)
        with mock.patch.object(genes, "_load_cache", return_value={"BRCA1": kept}), \
                mock.patch.object(genes, "from_ensembl", side_effect=AssertionError("not asked")):
            self.assertEqual("cache", genes.resolve("BRCA1")["source"])


if __name__ == "__main__":
    unittest.main()
