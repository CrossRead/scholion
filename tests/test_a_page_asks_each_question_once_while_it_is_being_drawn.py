"""A page asks each question once while it is being drawn, and never remembers past a change.

The radar tab took about a minute to open on a real profile (14.09.2026). The
list of systems and each card asked the same things hundreds of times: whether
the genome is available (891 calls, each a fresh search of the genome folder),
which vendor wrote each file there (23 576 content probes), what bcftools
returns at a position (637 processes, the same positions for the list and again
for every card). The fixes are three memories, and each has a boundary held here:

* inside one reading, a function marked for it is computed once per arguments
  and handed out as a copy; outside a reading nothing is remembered, so a test
  or a writer that changes something between two calls sees the change;
* what a file's content says is remembered by the file's identity — path, size,
  modification time — so a rewritten file is read again;
* rows bcftools returned are remembered by the identity of the file AND of its
  index, and a failed run is not remembered.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import array_genome, core, genome


class TestOneReading(unittest.TestCase):

    def test_inside_a_reading_once_and_a_copy_outside_every_time(self):
        calls = []

        @core.memo_in_reading
        def answer(x):
            calls.append(x)
            return {"value": [x]}

        answer(1)
        answer(1)
        self.assertEqual([1, 1], calls, "outside a reading nothing is remembered")
        calls.clear()
        with core.reading_session():
            first = answer(1)
            first["value"].append("changed by a caller")
            second = answer(1)
            answer(2)
        self.assertEqual([1, 2], calls, "inside a reading each argument is computed once")
        self.assertEqual({"value": [1]}, second, "a caller's change does not reach the next caller")
        answer(1)
        self.assertEqual([1, 2, 1], calls, "the memory ends with the reading")

    def test_nested_readings_share_one_memory_until_the_outermost_ends(self):
        calls = []

        @core.memo_in_reading
        def answer():
            calls.append(1)
            return 1

        @core.in_reading
        def inner():
            return answer()

        with core.reading_session():
            answer()
            inner()
        self.assertEqual([1], calls)
        inner()
        self.assertEqual([1, 1], calls)


class TestTheServerPreparesOnlyBoundedPositions(unittest.TestCase):

    def test_warm_up_does_not_compute_invisible_panels_and_keeps_failure_optional(self):
        from scholion import engine, genome, server
        with mock.patch.object(engine, "systems", side_effect=AssertionError("eager hidden panels")), \
                mock.patch.object(genome, "_prefetch_catalogue_rows") as prepare, \
                mock.patch.dict(genome._REGION_CACHE, {("synthetic",): ()}, clear=True):
            self.assertEqual(1, server.warm_up())
            prepare.assert_called_once_with()
        with mock.patch.object(genome, "_prefetch_catalogue_rows", side_effect=RuntimeError("cold disk")):
            self.assertEqual(0, server.warm_up())

    def test_startup_integrity_uses_the_same_package_and_pinned_profile_in_a_child(self):
        import subprocess
        import sys
        from scholion import server
        profile = support.FIXTURE_PROFILE.resolve()
        repo = support.ROOT.resolve()
        completed = subprocess.CompletedProcess([], 0, 'Synthetic integrity summary\n', '')
        with mock.patch.object(server.subprocess, 'run', return_value=completed) as run, \
                mock.patch('builtins.print') as output:
            server._startup_selfcheck(profile, repo)
        args, kwargs = run.call_args
        self.assertEqual([sys.executable, '-c'], args[0][:2])
        self.assertIn('reconcile.selfcheck_summary(reconcile.reconcile())', args[0][2])
        self.assertEqual(str(profile), kwargs['env']['SCHOLION_PROFILE_DIR'])
        self.assertEqual(str(repo), kwargs['env']['SCHOLION_REPO_DIR'])
        self.assertEqual(str(Path(server.__file__).resolve().parent.parent), kwargs['env']['PYTHONPATH'])
        self.assertEqual(300, kwargs['timeout'])
        self.assertNotIn('shell', kwargs)
        output.assert_called_once_with('Synthetic integrity summary', flush=True)

    def test_failed_integrity_child_is_named_instead_of_printing_a_success(self):
        import subprocess
        from scholion import server, i18n
        for result in (subprocess.CompletedProcess([], 1, '', 'Synthetic failure'),
                       subprocess.TimeoutExpired('synthetic child', 300)):
            with self.subTest(result=type(result).__name__), \
                    mock.patch.object(server.subprocess, 'run') as run, \
                    mock.patch('builtins.print') as output:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                server._startup_selfcheck(support.FIXTURE_PROFILE, support.ROOT)
                self.assertTrue(output.called)
                error = str(result) if isinstance(result, Exception) else 'Synthetic failure'
                self.assertEqual(i18n.t('server.selfcheck_skipped', error=error),
                                 output.call_args.args[0])


class _Folder(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="reading_")).resolve()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def touch_later(self, path: Path, text: str) -> None:
        """Rewrite with a different size and a later modification time."""
        path.write_text(text, encoding="utf-8")
        later = time.time() + 5
        os.utime(path, (later, later))


class TestAFileIsReadAgainOnceItChanges(_Folder):

    def test_the_vendor_is_asked_again_after_a_rewrite(self):
        f = self.dir / "export.txt"
        f.write_text("# a file\n", encoding="utf-8")
        with mock.patch.object(array_genome, "_sniff_vendor_uncached", side_effect=["23andMe", None]) as sniff:
            self.assertEqual("23andMe", array_genome._sniff_vendor(f))
            self.assertEqual("23andMe", array_genome._sniff_vendor(f))
            self.assertEqual(1, sniff.call_count, "an unchanged file is not read twice")
            self.touch_later(f, "# another file, longer\n")
            self.assertIsNone(array_genome._sniff_vendor(f))
            self.assertEqual(2, sniff.call_count)

    def test_a_file_that_cannot_be_stat_ed_is_sniffed_without_being_remembered(self):
        missing = self.dir / "gone.txt"
        with mock.patch.object(array_genome, "_sniff_vendor_uncached", return_value=None) as sniff:
            self.assertIsNone(array_genome._sniff_vendor(missing))
            self.assertIsNone(array_genome._sniff_vendor(missing))
            self.assertEqual(2, sniff.call_count, "nothing is remembered about a file that is not there")

    def test_the_memory_is_bounded(self):
        array_genome._SNIFF_CACHE.clear()
        array_genome._SNIFF_CACHE.update({("x%d" % i, 0, 0): None for i in range(4097)})
        f = self.dir / "one.txt"
        f.write_text("# a file\n", encoding="utf-8")
        with mock.patch.object(array_genome, "_sniff_vendor_uncached", return_value="23andMe"):
            self.assertEqual("23andMe", array_genome._sniff_vendor(f))
        self.assertEqual(1, len(array_genome._SNIFF_CACHE), "an overfull memory is emptied before it grows")

    def test_the_kind_of_a_file_is_asked_again_after_a_rewrite(self):
        f = self.dir / "table.txt"
        f.write_text("x\n", encoding="utf-8")
        with mock.patch.object(genome, "_sniff_kind_uncached", side_effect=["variant_table", None]) as sniff:
            self.assertEqual("variant_table", genome._sniff_kind(str(f)))
            self.assertEqual("variant_table", genome._sniff_kind(str(f)))
            self.touch_later(f, "a different table\n")
            self.assertIsNone(genome._sniff_kind(str(f)))
            self.assertEqual(2, sniff.call_count)


class TestTheCoverageTableIsParsedOncePerVersionOfTheFile(_Folder):

    HEAD = "gene\tpanel\tmean_depth\trel_to_panel\tpct_10x\tpct_20x\n"

    def test_parsed_once_read_again_after_a_rewrite_and_a_copy_each_time(self):
        from scholion import limits
        table = self.dir / "callability.tsv"
        table.write_text(self.HEAD + "APOE\tp\t30\t1\t99\t95\n", encoding="utf-8")
        with mock.patch.object(core, "profile_dir", return_value=self.dir), \
                mock.patch.object(limits, "_read_callability", wraps=limits._read_callability) as parse:
            first = limits.callability()
            first.pop("APOE")
            second = limits.callability()
            self.assertIn("APOE", second, "a caller's change does not reach the next caller")
            self.assertEqual(1, parse.call_count, "an unchanged table is parsed once")
            self.touch_later(table, self.HEAD + "APOE\tp\t30\t1\t99\t95\nLDLR\tp\t25\t1\t98\t90\n")
            self.assertIn("LDLR", limits.callability())
            self.assertEqual(2, parse.call_count)
            table.unlink()
            self.assertEqual({}, limits.callability())


class TestARegionIsAskedAgainOnceTheFileOrItsIndexChanges(_Folder):

    def setUp(self):
        super().setUp()
        self.vcf = self.dir / "me.vcf.gz"
        self.vcf.write_bytes(b"vcf")
        (self.dir / "me.vcf.gz.tbi").write_bytes(b"tbi")

    def query(self, run):
        with mock.patch.object(genome, "engine_pin", return_value=None), \
                mock.patch.object(genome, "_index_usable", return_value=True), \
                mock.patch.object(genome, "_have_bcftools", return_value=True), \
                mock.patch.object(genome, "_chr_prefix", return_value="chr"), \
                mock.patch.object(genome.subprocess, "run", side_effect=run) as spawned:
            rows = genome._query_region(str(self.vcf), "19", 44908684)
        return rows, spawned.call_count

    @staticmethod
    def answering(line: str, code: int = 0):
        return lambda *a, **k: mock.Mock(stdout=line, returncode=code)

    def test_the_same_region_of_the_same_file_runs_once(self):
        rows, n = self.query(self.answering("chr19\t44908684\t.\tT\tC\n"))
        self.assertEqual((1, [["chr19", "44908684", ".", "T", "C"]]), (n, rows))
        rows, n = self.query(self.answering("never asked\n"))
        self.assertEqual((0, [["chr19", "44908684", ".", "T", "C"]]), (n, rows))
        rows[0][4] = "changed by a caller"
        rows, _ = self.query(self.answering("never asked\n"))
        self.assertEqual("C", rows[0][4], "a caller's change does not reach the memory")

    def test_a_rewritten_index_or_file_is_asked_again(self):
        self.query(self.answering("chr19\t44908684\t.\tT\tC\n"))
        self.touch_later(self.dir / "me.vcf.gz.tbi", "a new index")
        _, n = self.query(self.answering(""))
        self.assertEqual(1, n, "a new index is a new answer")
        self.touch_later(self.vcf, "a new file")
        _, n = self.query(self.answering(""))
        self.assertEqual(1, n, "a new file is a new answer")

    def test_a_failed_run_is_not_remembered(self):
        """A failed run raises — it is a failed read, not an empty position
        (see test_a_failed_read_is_never_the_reference) — and is not cached."""
        from scholion import linear
        with self.assertRaises(linear.Unreadable):
            self.query(self.answering("", code=1))
        _, n = self.query(self.answering("chr19\t44908684\t.\tT\tC\n"))
        self.assertEqual(1, n)


if __name__ == "__main__":
    unittest.main()
