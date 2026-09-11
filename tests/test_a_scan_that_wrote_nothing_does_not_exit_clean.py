"""`scholion acmg-scan` exits non-zero when it refused to write the table.

The first version returned 0 on every status, on the reasoning that a refusal
is a result and the command had done its job by printing it. Two things
argued the other way. `acmg-scan && acmg` then ran the second command over a
table the first had refused to write, and the shell had no way to tell that
from a scan that finished — the same shape as `ingest-labs` with errors, which
already exits non-zero for exactly that reason (task 124). And the source-tree
wrapper the quarterly script runs returns its own code on the same statuses
— 0 written, 2 refused, 1 crashed — so one outcome carried two exit codes
depending on which door it came through.

The command uses the wrapper's table. The message is still printed in full,
in both shapes; `--json` prints the structure AND carries the code, as `init`
does. An empty table is not a refusal: `ok` with nothing found is 0.
"""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import cli


def run(status, *extra):
    res = {"status": status, "message": f"the screen says: {status}", "scanned": 0,
           "clinvar_scanned": 0}
    out = io.StringIO()
    with mock.patch("scholion.acmg_scan.scan", return_value=res), redirect_stdout(out):
        code = cli.main(["acmg-scan", *extra])
    return code, out.getvalue()


class TestTheExitCodeSaysWhetherTheTableWasWritten(unittest.TestCase):

    def test_a_refusal_is_not_a_clean_exit(self):
        code, out = run("clinvar_missing")
        self.assertEqual(2, code)
        self.assertIn("clinvar_missing", out, "the refusal stopped being printed")

    def test_a_scan_that_ran_exits_clean_even_with_nothing_found(self):
        code, _ = run("ok")
        self.assertEqual(0, code)

    def test_the_json_shape_carries_the_same_code(self):
        code, out = run("assembly_mismatch", "--json")
        self.assertEqual(2, code)
        self.assertEqual("assembly_mismatch", json.loads(out)["status"])

    def test_the_wrapper_in_the_source_tree_agrees(self):
        """One outcome, one code, whichever door it came through — read from
        the wrapper's own named constant, so that the two cannot drift apart
        without this line noticing."""
        if not support.IN_SOURCE_REPO:
            self.skipTest("the wrapper travels only in the source archive")
        import importlib.util
        src = support.ROOT / "src" / "ingest" / "acmg_sf_scan.py"
        spec = importlib.util.spec_from_file_location("acmg_sf_scan_under_test", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch("scholion.acmg_scan.scan",
                        return_value={"status": "clinvar_missing", "message": "m"}), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(mod.EXIT_REFUSED, mod.main(["x"]))
        self.assertEqual(2, mod.EXIT_REFUSED, "the command's code above follows this one")


if __name__ == "__main__":
    unittest.main()
