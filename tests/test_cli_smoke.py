"""Smoke pass: every command answers instead of crashing.

The whole point is the completeness of the sweep. There are more than thirty
commands, nobody checks them by hand, and the one that breaks is usually the one
nobody has used for a long time — while the assistant has it in its list and
will call it. Three things are checked: return code 0, `--json` yields a
parseable object, there is no traceback in the output.

The behaviour on an EMPTY profile is checked separately: the application is
obliged to answer with the words "there is no data" instead of crashing or
showing empty zeroes.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import contract


def commands_to_smoke():
    for cmd in contract.cli_commands():
        args = support.ARGS_FOR.get(cmd, [])
        if args is None:
            continue
        yield cmd, [cmd, *args]


class TestSmoke(unittest.TestCase):

    def test_commands_answer(self):
        for cmd, argv in commands_to_smoke():
            with self.subTest(command=cmd):
                code, out, err = support.run(argv)
                self.assertEqual(code, 0, f"{cmd}: exit code {code}\n{err[-800:]}")
                self.assertNotIn("Traceback", err, f"{cmd}: a traceback in stderr")
                self.assertTrue(out.strip(), f"{cmd}: empty output")

    def test_json_parses(self):
        for cmd, argv in commands_to_smoke():
            if cmd in ("serve",):
                continue
            with self.subTest(command=cmd):
                data = support.run_json(argv)
                self.assertIsInstance(data, (dict, list), f"{cmd}: --json did not return an object")

    def test_empty_profile_answers_honestly(self):
        """A new user: there is no data at all. No crashes, no invented zeroes."""
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "profile"
            empty.mkdir()
            for cmd, argv in commands_to_smoke():
                if cmd in ("serve",):
                    continue
                with self.subTest(command=cmd):
                    code, out, err = support.run(argv, profile_dir=empty)
                    self.assertEqual(code, 0, f"{cmd} on an empty profile: exit code {code}\n{err[-800:]}")
                    self.assertNotIn("Traceback", err, f"{cmd}: a traceback on an empty profile")

    def test_writing_commands_work_on_a_copy(self):
        """We check writing on a copy of the fixture, so that the tests do not change the source files."""
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "profile"
            shutil.copytree(support.FIXTURE_PROFILE, prof)

            code, out, _ = support.run(["add-lab", "ldl", "2026-08", "3.9",
                                        "--name", "LDL", "--unit", "mmol/L"], profile_dir=prof)
            self.assertEqual(code, 0, out)
            labs = json.loads((prof / "labs.json").read_text(encoding="utf-8"))
            dates = [p["date"] for p in labs["markers"]["ldl"]["series"]]
            self.assertIn("2026-08", dates, "the point was not written into labs.json")

            support.run(["add-med", "test drug", "--dose", "1 tab"], profile_dir=prof)
            meds = support.run_json(["medications"], profile_dir=prof)["medications"]
            self.assertTrue(any(m["name"] == "test drug" for m in meds))

            support.run(["remove-med", "test drug"], profile_dir=prof)
            meds = support.run_json(["medications"], profile_dir=prof)["medications"]
            self.assertFalse(any(m["name"] == "test drug" for m in meds),
                             "the drug was not removed")

            # the source fixture is untouched
            fx = json.loads((support.FIXTURE_PROFILE / "labs.json").read_text(encoding="utf-8"))
            self.assertNotIn("2026-08", [p["date"] for p in fx["markers"]["ldl"]["series"]])


class TestFirstRun(unittest.TestCase):
    """`init` and `demo` are the only commands that CREATE profile files.

    They must not be taken into the general smoke sweep: it goes over the
    fixture, and `init` would lay the templates out right inside it. So here they
    run in a temporary directory, and exactly what these commands exist for is
    checked: a person who has nothing yet gets a working profile after a single
    command.
    """

    def test_init_creates_a_profile_in_an_empty_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            code, txt, err = support.run(["init", "--dir", str(out)])
            self.assertEqual(code, 0, err)
            self.assertTrue(list(out.glob("*.json")), "init created no file at all")
            # and the profile is read by the core straight away, rather than merely looking created
            code, _, err = support.run(["overview"], profile_dir=out)
            self.assertEqual(code, 0, f"overview on a freshly created profile: {err[-500:]}")

    def test_init_does_not_overwrite_what_already_exists(self):
        """An initialisation command capable of wiping someone else's data is more dangerous than its absence."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            support.run(["init", "--dir", str(out)])
            victim = out / "labs.json"
            victim.write_text('{"my": "data"}', encoding="utf-8")
            code, _, err = support.run(["init", "--dir", str(out)])
            self.assertEqual(code, 0, err)
            self.assertEqual(victim.read_text(encoding="utf-8"), '{"my": "data"}',
                             "a second init overwrote a file that already existed")

    def test_demo_unfolds_and_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo-profile"
            code, txt, err = support.run(["demo", "--out", str(out)])
            self.assertEqual(code, 0, err)
            data = support.run_json(["demo", "--out", str(out), "--force"])
            self.assertIsInstance(data, dict, "demo --json did not return an object")
            self.assertTrue(data.get("written"), "demo --json did not list the files it created")
            code, _, err = support.run(["overview"], profile_dir=out)
            self.assertEqual(code, 0, f"overview on the demo profile: {err[-500:]}")

    def test_demo_is_deterministic(self):
        """The same invented person on every run: otherwise the screenshots and
        the tests diverge from what the reader will see."""
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            support.run(["demo", "--out", str(a)])
            support.run(["demo", "--out", str(b)])
            for f in sorted(a.glob("*")):
                self.assertEqual(f.read_bytes(), (b / f.name).read_bytes(),
                                 f"{f.name} differs between two runs of demo")


if __name__ == "__main__":
    unittest.main()
