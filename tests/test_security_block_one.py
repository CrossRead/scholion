"""Security fixes from the colleagues' 0.1.3 audit, verified against the code.

Each test names the audit finding it pins and fails if the fix is reverted.
The web-facing XSS checks read the page source, because the defect lives in
client JavaScript there is no Python runtime to exercise; a source assertion
is enough to catch a reintroduction of the exact unescaped interpolation.
"""
from __future__ import annotations

import http.server
import io
import os
import pathlib
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

import support  # noqa: F401
from scholion import core, net, store

WEB = pathlib.Path(net.__file__).resolve().parent / "web" / "index.html"


class TestDiagnoseIsNotAnOpenProxy(unittest.TestCase):
    """Finding 21: /api/diag?url= was a blind SSRF and a file oracle.

    The first repair validated the address the caller handed in. It closed the
    hole and left the shape: a check over a string somebody else composed is a
    race with whoever composes it, and an approved HOST still took any path and
    any query. The check now takes a NAME out of a fixed table and never an
    address, so there is nothing left to validate — what leaves the machine is
    a constant from the source.
    """

    def test_an_address_is_not_a_target_however_harmless_it_looks(self):
        for address in ("file:///etc/passwd",
                        "https://evil.example.com/x",
                        # The RIGHT address, refused for being an address: this is
                        # the whole rule in one assertion.
                        "https://rxnav.nlm.nih.gov/REST/version.json"):
            with self.subTest(address=address):
                r = net.diagnose(address)
                self.assertTrue(r.get("refused"), r)
                self.assertFalse(r.get("ok"), r)

    def test_an_unknown_name_names_what_it_would_accept(self):
        r = net.diagnose("nonsuch")
        self.assertTrue(r.get("refused"))
        for name in net.DIAG_TARGETS:
            self.assertIn(name, r.get("error", ""))

    def test_http_downgrade_is_refused(self):
        self.assertFalse(net._diag_url_ok("http://rxnav.nlm.nih.gov/x"))

    def test_every_address_in_the_table_passes_the_second_gate(self):
        # The table is walked rather than sampled: an entry added by hand with a
        # plain-http address would otherwise sit there until somebody read it.
        self.assertTrue(net.DIAG_TARGETS, "the table is empty — nothing can be probed")
        for name, url in net.DIAG_TARGETS.items():
            with self.subTest(name=name):
                self.assertTrue(net._diag_url_ok(url), f"{name} → {url}")

    def test_a_redirect_from_an_allowed_host_is_not_followed(self):
        """The allowlist checks scheme and host, not path or query — and `urlopen`
        follows redirects by default, so an allowed host redirecting elsewhere
        would land the request on a host that was never checked. A local HTTPS
        server standing in for an allowed host, answering only with a redirect,
        proves the request stops there rather than continuing."""
        if not shutil.which("openssl"):
            self.skipTest("openssl is needed to make a test certificate")

        tmp = tempfile.mkdtemp(prefix="scholion-diag-redirect-")
        cert, key = os.path.join(tmp, "cert.pem"), os.path.join(tmp, "key.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-keyout", key, "-out", cert, "-days", "1", "-nodes",
                        "-subj", "/CN=localhost"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL)

        class _Redirector(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "https://internal.example.invalid/pwned")
                self.end_headers()

            def log_message(self, *a):
                pass

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # The floor is named here as it is in every other context this project
        # builds. This server lives for one test on the loopback, so nothing was
        # ever at risk — but the alert that asked for it elsewhere was closed one
        # file away, and a rule kept in one place out of two is not a rule.
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Redirector)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        old_hosts, old_targets = net._DIAG_HOSTS, net.DIAG_TARGETS
        old_offline = os.environ.pop("SCHOLION_OFFLINE", None)
        # The probe is named, so the stand-in is added to the table by name —
        # which is also the only way a caller could ever reach it.
        net.DIAG_TARGETS = {**old_targets, "loopback": f"https://127.0.0.1:{port}/"}
        net._DIAG_HOSTS = old_hosts | {"127.0.0.1"}
        try:
            r = net.diagnose("loopback")
        finally:
            net._DIAG_HOSTS, net.DIAG_TARGETS = old_hosts, old_targets
            if old_offline is not None:
                os.environ["SCHOLION_OFFLINE"] = old_offline
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(tmp, ignore_errors=True)

        self.assertFalse(r.get("ok"), r)
        self.assertIn("redirect", r.get("error", "").lower(), r)


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

    def test_every_value_attribute_goes_through_esc(self):
        """A rule with no exceptions, because the exception was the defect.

        This began as a test about the birth year by name, and it held: that one
        field went through `esc()`. It said nothing about the other four fields of
        the same form, and the height had been going into the attribute raw the
        whole time — a profile is a file on disk, and a face that writes one of
        its fields straight into an attribute trusts whatever is in it.

        Checking the SHAPE rather than the spelling also survives the code being
        rearranged: the birth-year box is now filled from `birth_year` or from the
        year of a stored `birth_date`, and a test pinned to the old expression
        would have failed for a change that kept the property exactly.
        """
        import re as _re
        raw = _re.findall(r'value="\$\{(?!esc\()[^}]{0,60}', self.src)
        self.assertEqual([], raw,
                         "these put a value into an attribute without escaping it: "
                         + ", ".join(raw))

    def test_the_birth_year_box_still_escapes_what_it_shows(self):
        """Named separately because it is the field the original finding was
        about, and because it is now filled from two different profile fields."""
        self.assertIn("esc(byear)", self.src)
        self.assertNotIn('value="${p.birth_year', self.src)
        self.assertNotIn('value="${p.birth_date', self.src)


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
