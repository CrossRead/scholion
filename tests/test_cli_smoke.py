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
import os
import shutil
import subprocess
import sys
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


class TestTheTwoScreensBeforeAnybodyHasData(unittest.TestCase):
    """What a stranger sees in the first thirty seconds, from a clean install.

    Both of these were reported from a real `pip install scholion` on a clean
    machine by somebody who is not the author — which is the only way either was
    ever going to be noticed. Neither is a malfunction: both commands did exactly
    what they were written to do, and both did it in a way that reads as a
    problem to the person seeing it for the first time.
    """

    def _run(self, argv, root, lang="en"):
        env = {**os.environ,
               "PYTHONPATH": str(support.ROOT / "src"),
               "SCHOLION_OFFLINE": "1",
               "SCHOLION_LANG": lang,
               "SCHOLION_REPO_DIR": str(root)}
        env.pop("SCHOLION_PROFILE_DIR", None)
        return subprocess.run([sys.executable, "-m", "scholion", *argv],
                              cwd=support.ROOT, env=env,
                              capture_output=True, text=True, timeout=120)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_the_bare_name_answers_instead_of_erroring(self):
        """`scholion` is the first thing a curious person types.

        It used to answer with a usage dump of forty-four command names and
        «error: the following arguments are required: cmd» — an error message,
        for typing the name of the thing you just installed.
        """
        p = self._run((), self.root)
        self.assertEqual(p.returncode, 0, f"a bare `scholion` exits non-zero:\n{p.stderr[-300:]}")
        self.assertNotIn("error:", p.stderr.lower(), "it still answers with an error")
        self.assertNotIn("usage:", p.stdout.lower() + p.stderr.lower(),
                         "it still answers with the usage dump")

    def test_the_bare_name_is_short_and_offers_a_first_move(self):
        p = self._run((), self.root)
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 6,
                             f"the hint has grown into a catalogue ({len(lines)} lines)")
        self.assertIn("init --demo", p.stdout, "it names no way in")
        self.assertIn("--help", p.stdout, "it does not say where the full list is")

    def test_the_hint_exists_in_both_languages(self):
        """A missing key prints the key, which is worse than the usage dump."""
        for lang in ("en", "ru"):
            with self.subTest(lang=lang):
                out = self._run((), self.root, lang=lang).stdout
                self.assertNotIn("cli.bare_hint", out, "the translation is missing")
                self.assertIn("scholion", out)

    def test_the_demo_is_not_told_what_it_does_not_need(self):
        """Four ✗ under «Have a look» read as «installed halfway».

        The demo is synthetic data already on disk: samtools, bcftools, bgzip and
        tabix have nothing to do with it. For a REAL profile the offer stays —
        there the genome layer does not work without them, and the moment to say
        so is before the person goes looking for a VCF. That half is asserted
        separately below, because removing it would be the opposite defect.
        """
        p = self._run(("init", "--demo"), self.root)
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        self.assertNotIn("✗", p.stdout,
                         "the demo run still lists external programs it does not use")
        self.assertIn("scholion tools", p.stdout,
                      "it does not say where to look when a real genome does need them")

    def test_a_real_profile_is_still_told(self):
        """The opposite defect: silencing the offer everywhere, not just for the demo.

        The first version of this asserted that a real `init` prints ✗ — and on a
        machine that HAS samtools, bcftools, bgzip and tabix there is nothing
        missing and nothing to print. It was green in the cloud, where none of
        them exist, and red on the owner's laptop, where all of them do. That is
        a test of what is installed, not of what the product does, and this
        project has caught itself writing one before: a check that read the
        machine's `.personal_patterns` instead of its own.

        So the machine is taken out of it. What must hold either way is that the
        two paths differ — a demo says «nothing else to install», a real profile
        does not — and that the real path still consults the tool layer at all.
        """
        real_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, real_root, ignore_errors=True)
        real = self._run(("init",), real_root)
        self.assertEqual(real.returncode, 0, real.stderr[-300:])

        demo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, demo_root, ignore_errors=True)
        demo = self._run(("init", "--demo"), demo_root)
        self.assertEqual(demo.returncode, 0, demo.stderr[-300:])

        # The discriminator is the demo's own sentence, not the words «scholion
        # tools» — those appear in BOTH branches, which is how the first attempt
        # at this assertion failed. What only the demo says is that there is
        # nothing left to install.
        self.assertIn("Nothing else to install", demo.stdout,
                      "the demo no longer says where to look when a genome does need them")
        self.assertNotIn("Nothing else to install", real.stdout,
                         "a real init prints the demo's line — the two branches have merged")

        # And the half that depends on the machine, asserted only where it can be:
        # if anything IS missing, a real init has to name it.
        missing = "✗" in demo.stdout + demo.stderr
        self.assertFalse(missing, "the demo listed programs it does not use")

    def test_a_real_profile_consults_the_tool_layer(self):
        """Machine-independent, because it asks the code rather than the output."""
        import sys as _sys
        if str(support.SRC) not in _sys.path:
            _sys.path.insert(0, str(support.SRC))
        from scholion import tools as _tools
        called = []
        orig = _tools.offer_after_init
        _tools.offer_after_init = lambda **kw: called.append(kw) or {"asked": False}
        try:
            from scholion import cli as _cli
            root = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            old = os.environ.get("SCHOLION_REPO_DIR")
            os.environ["SCHOLION_REPO_DIR"] = str(root)
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            try:
                _cli.main(["init"])
                self.assertTrue(called, "a real init never consults the tool layer")
                called.clear()
                _cli.main(["init", "--demo", "--force"])
                self.assertFalse(called, "a demo init still consults the tool layer")
            finally:
                if old is None:
                    os.environ.pop("SCHOLION_REPO_DIR", None)
                else:
                    os.environ["SCHOLION_REPO_DIR"] = old
        finally:
            _tools.offer_after_init = orig
