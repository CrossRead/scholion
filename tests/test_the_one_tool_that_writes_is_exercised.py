"""The single tool a model may use to write, driven through the tool door.

`sch_focus_log` records what the person just said happened — a glass of wine, a
dose taken as needed, a late meal. It is the only handler in the tools module
that changes the profile, and `contract.DICTATED` explains at length why it is
allowed to: what it writes is testimony, not an inference.

It arrived with no test of its own. The suite covered `store.add_focus_entry`
underneath it and the `focus-log` command beside it, so nothing was red — but
the handler in between, the one an actual model calls, ran in no test at all.
That is the shape this file exists to prevent: the writing path being the
uncovered one.

The reach ratchet should have said so on the day the tool landed and did not —
the run that accepted it skipped the reach step. A number that is only checked
when somebody remembers to check it is not a ratchet, so the gap is closed here
with tests rather than by accepting the lower number.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import support

if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))


class FocusLogCase(unittest.TestCase):
    def setUp(self):
        # Resolved: on macOS TMPDIR is under a symlink and the code returns the
        # resolved form, so an unresolved path here fails only on this platform.
        self.root = Path(tempfile.mkdtemp()).resolve() / "data"
        self._env = dict(os.environ)
        os.environ["SCHOLION_REPO_DIR"] = str(self.root)
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        os.environ["SCHOLION_OFFLINE"] = "1"
        os.environ["SCHOLION_LANG"] = "en"
        from scholion import core, store
        core.reset_cache()
        store.init_profile()
        self.core = core

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.core.reset_cache()

    def call(self, **args) -> str:
        from scholion import ouroboros_tools
        entry = next(e for e in ouroboros_tools.get_tools() if e.name == "sch_focus_log")
        ctx = ouroboros_tools.ToolContext()
        ctx.args = args
        return entry.handler(ctx)

    def journal(self) -> dict:
        p = self.core.profile_dir() / "focus_log.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


class TestItWritesWhatItWasTold(FocusLogCase):

    def test_it_is_offered_to_a_model_at_all(self):
        from scholion import ouroboros_tools
        self.assertIn("sch_focus_log", [e.name for e in ouroboros_tools.get_tools()])

    def test_a_day_the_person_described_reaches_the_journal(self):
        out = self.call(date="2026-08-20", alcohol="a glass of dry red",
                        late_meal=True, note="dinner at eleven")
        self.assertIn("2026-08-20", out)
        entries = self.journal().get("entries") or []
        self.assertEqual(1, len(entries))
        said = entries[0]
        self.assertEqual("a glass of dry red", said.get("alcohol"))
        self.assertTrue(said.get("late_meal"))
        self.assertEqual("dinner at eleven", said.get("note"))

    def test_it_writes_into_the_profile_it_was_pointed_at(self):
        """A write that lands somewhere else is worse than a write that fails."""
        self.call(date="2026-08-20", note="anything")
        self.assertTrue((self.root / "profile" / "focus_log.json").exists())

    def test_the_same_day_twice_is_one_entry_not_two(self):
        self.call(date="2026-08-20", alcohol="a beer")
        self.call(date="2026-08-20", alcohol="two beers")
        entries = self.journal().get("entries") or []
        self.assertEqual(1, len(entries))
        self.assertEqual("two beers", entries[0].get("alcohol"))

    def test_an_empty_entry_undoes_the_day(self):
        """How an accidental tick is taken back — documented, and now checked."""
        self.call(date="2026-08-20", atenolol=True)
        self.assertEqual(1, len(self.journal().get("entries") or []))
        self.call(date="2026-08-20")
        self.assertEqual([], self.journal().get("entries") or [])


class TestItRefusesRatherThanGuesses(FocusLogCase):

    def test_a_day_without_a_date_is_refused_and_says_so(self):
        """There is no sensible default here.

        Writing «today» for a model that did not say a date would put the
        person's evening on whatever day the container thinks it is.
        """
        out = self.call(note="something happened")
        self.assertIn("⚠", out)
        self.assertEqual([], self.journal().get("entries") or [])

    def test_a_blank_date_is_refused_the_same_way(self):
        self.assertIn("⚠", self.call(date="   ", note="something"))


if __name__ == "__main__":
    unittest.main()
