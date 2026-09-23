"""A write the store refuses is a command that failed.

The 0.5.7 review: `scholion add-lab glucose 2024-03-14 95 --unit furlongs`
printed the refusal and exited 0, so a script adding a column of values could
not tell which of them never arrived.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import support


class TestExitCode(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scholion-refused-")
        self.profile = Path(self.tmp) / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, self.profile)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_refused_unit_exits_non_zero(self):
        code, _out, _err = support.run(["add-lab", "glucose", "2024-03-14", "95",
                                        "--unit", "furlongs"], self.profile)
        self.assertEqual(1, code)

    def test_an_accepted_write_still_exits_zero(self):
        code, _out, err = support.run(["add-lab", "glucose", "2024-03-14", "5.4",
                                       "--unit", "mmol/L"], self.profile)
        self.assertEqual(0, code, err)


if __name__ == "__main__":
    unittest.main()
