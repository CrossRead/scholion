"""Backward compatibility: a public project must not change its interface silently.

The baseline lives in `tests/contracts/public_contract.json` and is updated only
deliberately — `python3 src/tools/check_compat.py --accept`. The test checks
exactly one rule: **adding is allowed, removing is not**. A new command or a new
field breaks nobody; a field that disappeared breaks parsing for the assistant, a
command that disappeared breaks the shortcut and the skill for the person.
"""
import importlib.util
import unittest

import support

_spec = importlib.util.spec_from_file_location(
    "check_compat", support.ROOT / "src" / "tools" / "check_compat.py")
check_compat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_compat)


class TestCompatibility(unittest.TestCase):

    def test_baseline_is_in_place(self):
        self.assertTrue(check_compat.BASELINE.exists(),
                        "there is no contract baseline — take one: "
                        "python3 src/tools/check_compat.py --accept")

    def test_nothing_went_missing(self):
        import json
        base = json.loads(check_compat.BASELINE.read_text(encoding="utf-8"))
        cur = check_compat.collect()
        problems = check_compat.compare(base, cur)
        self.assertEqual(problems, [], "\n".join(
            ["The public contract has narrowed — that is an incompatible change:", *problems,
             "", "If this is deliberate: python3 src/tools/check_compat.py --accept "
                 "and an entry in the CHANGELOG."]))

    def test_snapshots_were_taken_without_errors(self):
        cur = check_compat.collect()
        broken = {k: v for k, v in cur["json_fields"].items() if isinstance(v, dict)}
        self.assertEqual(broken, {}, f"commands did not return valid JSON: {broken}")


if __name__ == "__main__":
    unittest.main()
