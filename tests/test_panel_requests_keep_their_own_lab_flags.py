"""Concurrent panels retain independent lab snapshots and readable failure states."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import subprocess
import threading
import unittest
from unittest import mock

import support
from scholion import core, i18n
from scholion.engine import labs
from scholion.format_system import _test_row


class TestPanelFlagSnapshots(unittest.TestCase):
    def test_overlapping_readings_never_share_or_clear_one_anothers_flags(self):
        rendezvous = threading.Barrier(2)
        local = threading.local()

        def read_labs():
            local.calls += 1
            return {"markers": [{"key": "synthetic", "flag": local.flag}]}

        def read(flag):
            local.flag, local.calls = flag, 0
            with core.reading_session():
                first = labs._flags_now()
                rendezvous.wait(timeout=5)
                second = labs._flags_now()
            return flag, first, second, local.calls

        with mock.patch.object(labs, "analyze_labs", side_effect=read_labs), ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=10) for future in [pool.submit(read, "high"), pool.submit(read, "low")]]
        for flag, first, second, calls in results:
            self.assertEqual({"synthetic": flag}, first)
            self.assertEqual(first, second)
            self.assertEqual(1, calls)
        with mock.patch.object(labs, "analyze_labs", return_value={"markers": [{"key": "synthetic", "flag": "low"}]}) as load:
            with core.reading_session():
                mutable = labs._flags_now()
                mutable["synthetic"] = "high"
                self.assertEqual({"synthetic": "low"}, labs._flags_now())
            self.assertEqual(1, load.call_count)
            labs._flags_now()
            self.assertEqual(2, load.call_count)

    def test_unassessed_proposal_keeps_json_diagnostics_without_printing_them(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(core, "test_rules", return_value={"rules": [{
                    "id": "internal_fixture_rule", "suggest": "Synthetic test", "when": {}}]}), \
                    mock.patch.object(labs, "_eval_condition", side_effect=ValueError("DEBUG_FIXTURE")):
                data = labs.suggest_tests()
            self.assertEqual(1, data["unresolved_count"])
            row = data["suggestions"][0]
            self.assertEqual("DEBUG_FIXTURE", row["error"])
            self.assertEqual("internal_fixture_rule", row["id"])
            text = _test_row(row)
            self.assertIn("Synthetic test", text)
            self.assertNotIn("DEBUG_FIXTURE", text)
            self.assertNotIn("internal_fixture_rule", text)

    @unittest.skipUnless(shutil.which("node"), "requires node for the web renderer")
    def test_web_error_row_shows_named_proposal_without_debug_details(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function testItem(s)")
        function = page[start:page.index("\n}\n", start)+2]
        for language in ("en", "ru"):
            script = "const assert=require('node:assert/strict');const el=x=>x,esc=x=>x;const messages=" + json.dumps(
                {k: i18n.CATALOGUES[language][k] for k in ("tests.rule_error", "tests.proposal_unavailable")}) + ";const t=(k,a)=>messages[k].replace('{name}',a?.name||'');\n" + function + r"""
const html=testItem({id:'INTERNAL_RULE',error:'DEBUG_FIXTURE',suggest:'Synthetic test'});
assert.ok(html.includes('Synthetic test'));assert.ok(!html.includes('DEBUG_FIXTURE'));
assert.ok(!html.includes('INTERNAL_RULE'));
"""
            result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
