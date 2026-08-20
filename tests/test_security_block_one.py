"""Security fixes from the colleagues' 0.1.3 audit, verified against the code.

Each test names the audit finding it pins and fails if the fix is reverted.
The web-facing XSS checks read the page source, because the defect lives in
client JavaScript there is no Python runtime to exercise; a source assertion
is enough to catch a reintroduction of the exact unescaped interpolation.
"""
from __future__ import annotations

import io
import os
import pathlib
import threading
import unittest

import support  # noqa: F401
from scholion import core, net, store

WEB = pathlib.Path(net.__file__).resolve().parent / "web" / "index.html"


class TestDiagnoseIsNotAnOpenProxy(unittest.TestCase):
    """Finding 21: /api/diag?url= was a blind SSRF and a file oracle."""

    def test_file_scheme_is_refused_without_a_fetch(self):
        r = net.diagnose("file:///etc/passwd")
        self.assertTrue(r.get("refused"))
        self.assertFalse(r.get("ok"))

    def test_a_foreign_host_is_refused(self):
        self.assertTrue(net.diagnose("https://evil.example.com/x").get("refused"))

    def test_http_downgrade_is_refused(self):
        self.assertFalse(net._diag_url_ok("http://rxnav.nlm.nih.gov/x"))

    def test_a_real_reference_host_passes_the_gate(self):
        self.assertTrue(net._diag_url_ok("https://rxnav.nlm.nih.gov/REST/version.json"))
        self.assertTrue(net._diag_url_ok("https://rest.ensembl.org/x"))


class TestTheWebEscaperClosesAttributes(unittest.TestCase):
    """Finding 20: esc() escaped only & < > — an attribute payload with a quote
    broke out. The trend dates and birth_year reached the DOM unescaped."""

    def setUp(self):
        self.src = WEB.read_text(encoding="utf-8")

    def test_esc_also_escapes_quotes_and_backtick(self):
        line = next(l for l in self.src.splitlines() if "const esc =" in l)
        for ch in ('&quot;', '&#39;', '&#96;'):
            self.assertIn(ch, line, f"esc() does not produce {ch}")

    def test_trend_dates_go_through_esc(self):
        self.assertIn("esc(m.trend.from_date)", self.src)
        self.assertIn("esc(m.trend.to_date)", self.src)
        self.assertNotIn("${m.trend.from_date}", self.src)

    def test_birth_year_goes_through_esc(self):
        self.assertIn("esc(p.birth_year", self.src)
        self.assertNotIn('value="${p.birth_year', self.src)


class TestServerBindsLoopbackOnly(unittest.TestCase):
    """Finding 22: serve --host accepted a non-loopback address silently."""

    def test_non_loopback_bind_is_refused_by_default(self):
        from scholion import server
        old = os.environ.pop("SCHOLION_ALLOW_REMOTE", None)
        try:
            with self.assertRaises(SystemExit):
                server.serve("0.0.0.0", 59991, open_browser=False)
        finally:
            if old is not None:
                os.environ["SCHOLION_ALLOW_REMOTE"] = old


class TestPrsServerHonoursOfflineAndPins(unittest.TestCase):
    """Finding 25: uvx bypassed SCHOLION_OFFLINE and ran an env-chosen package."""

    def test_a_shell_laden_package_spec_is_rejected(self):
        from scholion import prs
        old = os.environ.get("PRS_MCP_PKG")
        os.environ["PRS_MCP_PKG"] = "evil; rm -rf /@1.0"
        try:
            self.assertEqual(prs._prs_pkg(), prs._DEFAULT_PKG)
        finally:
            if old is None:
                os.environ.pop("PRS_MCP_PKG", None)
            else:
                os.environ["PRS_MCP_PKG"] = old

    def test_a_plain_name_at_version_is_kept(self):
        from scholion import prs
        old = os.environ.get("PRS_MCP_PKG")
        os.environ["PRS_MCP_PKG"] = "just-prs-mcp@0.2.0"
        try:
            self.assertEqual(prs._prs_pkg(), "just-prs-mcp@0.2.0")
        finally:
            if old is None:
                os.environ.pop("PRS_MCP_PKG", None)
            else:
                os.environ["PRS_MCP_PKG"] = old


class TestConcurrentWritesDoNotLoseEachOther(unittest.TestCase):
    """Finding 23: read-modify-write on the profile was not serialized."""

    def test_parallel_metric_writes_all_survive(self):
        import tempfile
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        core.write_json.__wrapped__ if hasattr(core.write_json, "__wrapped__") else None
        try:
            # clear any cache pinned to a previous dir
            if hasattr(core, "_JSON_CACHE"):
                core._JSON_CACHE.clear()
            errors = []

            def add(i):
                try:
                    store.add_metric_point("weight", f"2026-01-{i:02d}", 70.0 + i, unit="kg")
                except Exception as e:  # noqa
                    errors.append(e)

            ts = [threading.Thread(target=add, args=(i,)) for i in range(1, 13)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errors, [])
            metrics = core.read_profile_json(pathlib.Path(d) / "metrics.json") or {}
            series = (metrics.get("metrics", {}).get("weight", {}) or {}).get("series", [])
            dates = {p["date"] for p in series}
            self.assertEqual(len(dates), 12, f"lost updates: only {len(dates)}/12 survived")
        finally:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            if hasattr(core, "_JSON_CACHE"):
                core._JSON_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
