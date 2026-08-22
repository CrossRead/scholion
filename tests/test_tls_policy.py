"""Certificate verification is never dropped on its own — checked against a real
server with a bad certificate, not against an invented shape of the error.

The first version of this test mocked `urlopen` raising a bare
`ssl.SSLCertVerificationError`, and the code caught exactly that class. Both were
wrong in the same way, so the tests passed: urllib wraps what the socket raised
into `urllib.error.URLError` and puts the original into `.reason`. The branch
never ran on a real request. Verification was never dropped — but the documented
escape hatch did nothing either, while the message kept telling the user to use
it.

Hence the shape of this file: the assumption about what urllib raises is checked
against a real TLS handshake, and only then is the policy exercised.
"""
import io
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import support  # noqa: F401  (puts src on the path)
from scholion import net


class _Env:
    """Environment restored whatever happens: these variables leak into other tests."""

    def __init__(self, **env):
        self.env, self.was = env, {}

    def __enter__(self):
        for k, v in self.env.items():
            self.was[k] = os.environ.get(k)
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return self

    def __exit__(self, *a):
        for k, v in self.was.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *a):
        pass


@unittest.skipUnless(shutil.which("openssl"), "openssl is needed to make a test certificate")
class TestAgainstARealBadCertificate(unittest.TestCase):
    """A local HTTPS server with a self-signed certificate. No outside network."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="scholion-tls-")
        cert, key = os.path.join(cls.tmp, "cert.pem"), os.path.join(cls.tmp, "key.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-keyout", key, "-out", cert, "-days", "1", "-nodes",
                        "-subj", "/CN=localhost"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2   # no reason for a test fixture to allow less
        ctx.load_cert_chain(cert, key)
        cls.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.srv.socket = ctx.wrap_socket(cls.srv.socket, server_side=True)
        cls.url = f"https://localhost:{cls.srv.server_address[1]}/"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_urllib_wraps_the_certificate_error(self):
        """The assumption the whole policy rests on. If a future Python stops
        wrapping, `_is_cert_error` has to learn the new shape — and this test is
        what says so out loud."""
        with self.assertRaises(Exception) as caught:
            urllib.request.urlopen(self.url, timeout=5).read()
        e = caught.exception
        self.assertTrue(net._is_cert_error(e),
                        f"a certificate failure was not recognised: {type(e).__name__}")

    def test_without_permission_the_request_stops(self):
        with _Env(SCHOLION_OFFLINE=None, SCHOLION_TLS_INSECURE=None):
            with self.assertRaises(RuntimeError) as caught:
                net._open(self.url, 5, None)
        self.assertIn("SCHOLION_TLS_INSECURE", str(caught.exception),
                      "the message does not say how to allow this deliberately")

    def test_with_permission_it_goes_through_and_says_so(self):
        with _Env(SCHOLION_OFFLINE=None, SCHOLION_TLS_INSECURE="1"):
            buf = io.StringIO()
            with redirect_stderr(buf):
                body = net._open(self.url, 5, None)
        self.assertEqual(body, b'{"ok": true}',
                         "the escape hatch does not work — the documented way out is dead")
        self.assertIn("SCHOLION_TLS_INSECURE", buf.getvalue(),
                      "the insecure mode kept quiet — that is what makes it dangerous")

    def test_get_json_reports_nothing_rather_than_a_wrong_answer(self):
        with _Env(SCHOLION_OFFLINE=None, SCHOLION_TLS_INSECURE=None):
            self.assertIsNone(net.get_json(self.url, timeout=5))


class TestOtherFailuresAreNotCertificateFailures(unittest.TestCase):
    """A timeout is not a certificate problem. Retrying it without a check was
    the widest part of the old defect."""

    def test_no_retry_on_anything_else(self):
        for err in (TimeoutError("timed out"),
                    urllib.error.URLError("name resolution failed"),
                    urllib.error.HTTPError("u", 500, "boom", {}, None)):
            with self.subTest(error=type(err).__name__):
                with _Env(SCHOLION_OFFLINE=None, SCHOLION_TLS_INSECURE="1"):
                    with mock.patch.object(net.urllib.request, "urlopen", side_effect=err) as m:
                        with self.assertRaises(Exception):
                            net._open("https://example.invalid/x", 5, None)
                    self.assertEqual(m.call_count, 1, "a retry happened where it must not")

    def test_offline_wins_over_permission(self):
        with _Env(SCHOLION_OFFLINE="1", SCHOLION_TLS_INSECURE="1"):
            with self.assertRaises(RuntimeError):
                net._open("https://example.invalid/x", 5, None)

    def test_the_recogniser_knows_both_shapes(self):
        """Wrapped is what urllib produces; bare is what a different client could
        raise. Recognising only one of them is how the previous version broke."""
        bare = ssl.SSLCertVerificationError(1, "certificate verify failed")
        self.assertTrue(net._is_cert_error(bare))
        self.assertTrue(net._is_cert_error(urllib.error.URLError(bare)))
        self.assertFalse(net._is_cert_error(urllib.error.URLError(TimeoutError())))
        self.assertFalse(net._is_cert_error(TimeoutError()))


if __name__ == "__main__":
    unittest.main()
