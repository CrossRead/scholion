"""A journal's yes/no factors are declared by the person, not named by the build (task 176).

`focus-log --atenolol` put one person's prescription into a public command, a
tool schema and the page, while the skill's instruction promised factors taken
from `profile/focus.json`. The factors are now read from the journal's own
yes/no fields; `--atenolol` stays as a synonym of `--factor atenolol` for
anybody who scripted it, and is no longer listed.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import support
from scholion import cli, core, store


def _focus(fields):
    return {"_meta": {}, "focus": {"id": "x", "title": "x", "journal": {"fields": fields}}}


class _Profile(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="focus_")).resolve()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(self.d)})
        p.start(); self.addCleanup(p.stop)
        core.reset_cache(); self.addCleanup(core.reset_cache)

    def declare(self, fields):
        (self.d / "focus.json").write_text(json.dumps(_focus(fields)), encoding="utf-8")
        core.reset_cache()

    def entries(self):
        return json.loads((self.d / "focus_log.json").read_text(encoding="utf-8"))["entries"]


class TestTheFactors(_Profile):

    def test_they_are_the_journals_yes_no_fields_in_either_spelling(self):
        self.declare([{"key": "alcohol", "type": "choice"}, {"key": "beta_blocker", "type": "bool", "label": "BB"},
                      {"id": "late_meal", "kind": "bool"}, {"key": "note", "type": "text"}])
        self.assertEqual([{"key": "beta_blocker", "label": "BB"}, {"key": "late_meal", "label": "late_meal"}],
                         core.focus_factors())

    def test_a_journal_that_declares_none_keeps_what_it_had(self):
        self.assertEqual(["atenolol", "late_meal"], [f["key"] for f in core.focus_factors()])

    def test_a_named_factor_is_written_and_an_undeclared_one_refused(self):
        self.declare([{"key": "beta_blocker", "type": "bool"}])
        self.assertTrue(store.add_focus_entry("2026-09-20", factors=["beta_blocker"])["ok"])
        self.assertTrue(self.entries()[0]["beta_blocker"])
        r = store.add_focus_entry("2026-09-21", factors=["aspirin"])
        self.assertFalse(r["ok"])
        self.assertIn("beta_blocker", r["error"])


class TestTheFaces(_Profile):

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            cli.main(list(argv))
        return out.getvalue()

    def test_the_command_line_takes_factor_and_keeps_the_old_flag_as_a_synonym(self):
        self.declare([{"key": "atenolol", "type": "bool"}, {"key": "late_meal", "type": "bool"}])
        self.run_cli("focus-log", "2026-09-20", "--factor", "late_meal")
        self.run_cli("focus-log", "2026-09-21", "--atenolol")
        by = {e["date"]: e for e in self.entries()}
        self.assertEqual((True, False), (by["2026-09-20"]["late_meal"], by["2026-09-20"]["atenolol"]))
        self.assertTrue(by["2026-09-21"]["atenolol"])

    def test_the_old_flag_is_not_listed(self):
        parser = cli.build_parser()
        sub = next(a for a in parser._actions if getattr(a, "choices", None) and "focus-log" in a.choices)
        text = sub.choices["focus-log"].format_help()
        self.assertIn("--factor", text)
        self.assertNotIn("--atenolol", text)

    def test_the_tool_carries_factors(self):
        self.declare([{"key": "beta_blocker", "type": "bool"}])
        from scholion import ouroboros_tools as ot
        tools = {t.name: t for t in ot.get_tools()}
        self.assertIn("factors", tools["sch_focus_log"].schema["parameters"]["properties"])
        with mock.patch("scholion.upgrade.session_note", return_value=""):
            tools["sch_focus_log"].handler(ot.ToolContext(), date="2026-09-20", factors="beta_blocker")
        self.assertTrue(self.entries()[0]["beta_blocker"])

    def test_the_page_draws_the_declared_factors_and_names_no_drug(self):
        page = (support.SRC / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("f.journal.factors", page)
        self.assertNotIn("fc-aten", page)
        self.assertNotIn("web.focus.atenolol", page)


if __name__ == "__main__":
    unittest.main()
