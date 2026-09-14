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


class TestTheServerWarmsTheCardsAfterBinding(unittest.TestCase):

    def test_the_warm_up_reads_every_system_once_and_swallows_a_failure(self):
        from scholion import engine, server
        from scholion.engine import system_panels as SP
        n = server.warm_up()
        self.assertEqual(len(SP.domains()), n)
        # The warm-up reads through the engine facade, so that is where a
        # failure is planted.
        with mock.patch.object(engine, "systems", side_effect=RuntimeError("cold disk")):
            self.assertEqual(0, server.warm_up())


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
        self.query(self.answering("", code=1))
        _, n = self.query(self.answering("chr19\t44908684\t.\tT\tC\n"))
        self.assertEqual(1, n)


if __name__ == "__main__":
    unittest.main()
