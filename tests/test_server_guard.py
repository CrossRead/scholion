"""The local server: someone else's page must not change the profile.

The socket is open on loopback only — but that protects against the NETWORK, not
against the browser. A page the person has opened on another site can send a POST
to 127.0.0.1: it will not read the response (CORS forbids that), but the write
will go through. So four things are checked: a foreign name in Host, a cross-site
Origin, the size of the body, and the fact that the details of an internal error
do not leave in the response.
"""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import support
from scholion import server


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestRequestGuard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # The profile is a COPY of the fixture in a temporary directory. Some of
        # the routes being checked write files (collecting the assistant context
        # puts assistant_context.txt next to it), and a test that changes the very
        # thing it checks against spoils the next run.
        cls._tmp = tempfile.mkdtemp(prefix="scholion-guard-")
        cls._profile = os.path.join(cls._tmp, "profile")
        shutil.copytree(support.FIXTURE_PROFILE, cls._profile)
        cls._env_was = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = cls._profile

        cls.port = _free_port()
        cls.srv = server._Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(50):                    # wait for readiness
            try:
                cls._call("/api/ping")
                break
            except Exception:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        if cls._env_was is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = cls._env_was
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def _call(cls, path, data=None, headers=None, raw=None):
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(cls.base + path, data=body,
                                     method="POST" if body is not None else "GET")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read(2000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read(2000).decode("utf-8", "replace")

    def test_our_own_request_passes(self):
        code, _ = self._call("/api/ping")
        self.assertEqual(code, 200)

    def test_a_foreign_name_in_host_is_rejected(self):
        """Protection against DNS rebinding: a foreign name resolved to 127.0.0.1."""
        code, _ = self._call("/api/ping", headers={"Host": "evil.example.com"})
        self.assertEqual(code, 403)

    def test_a_cross_site_origin_does_not_write_to_the_profile(self):
        code, _ = self._call("/api/medications", {"name": "fly-agaric jam", "dose": "1"},
                             {"Origin": "https://evil.example.com"})
        self.assertEqual(code, 403, "a cross-site POST was accepted")

    def test_a_request_without_origin_works(self):
        """curl and the CLI do not send an Origin — there is nothing and no reason to break them."""
        code, _ = self._call("/api/assistant/context", {})
        self.assertEqual(code, 200)

    def test_a_huge_body_is_rejected_before_being_read(self):
        code, txt = self._call("/api/labs", raw=b"x" * 10,
                               headers={"Content-Length": str(server._MAX_BODY + 1)})
        self.assertEqual(code, 413, txt[:200])

    def test_a_malformed_content_length(self):
        code, _ = self._call("/api/labs", raw=b"{}", headers={"Content-Length": "not-a-number"})
        self.assertEqual(code, 400)

    def test_the_details_of_an_error_do_not_leave_outward(self):
        """The `str(e)` of a file error is an absolute path, that is, the user's
        name and the structure of their directories in the body of an HTTP
        response."""
        from scholion import store as _store
        original = _store.add_medication

        def boom(*a, **k):
            raise FileNotFoundError(2, "No such file", "/Users/кто-то/profile/labs.json")

        _store.add_medication = boom
        try:
            code, txt = self._call("/api/medications", {"name": "x", "dose": "1"})
        finally:
            _store.add_medication = original
        self.assertEqual(code, 500)
        self.assertNotIn("/Users/", txt, "the path leaked into the HTTP response")
        self.assertNotIn("кто-то", txt)


class TestHostNameParsing(unittest.TestCase):

    def test_local_names(self):
        for h in ("127.0.0.1", "127.0.0.1:1521", "localhost", "localhost:1521", "[::1]:1521"):
            with self.subTest(host=h):
                self.assertTrue(server._host_is_local(h))

    def test_foreign_names(self):
        for h in ("", "evil.example.com", "evil.example.com:1521", "127.0.0.1.evil.com",
                  "192.168.1.10:1521"):
            with self.subTest(host=h):
                self.assertFalse(server._host_is_local(h))


if __name__ == "__main__":
    unittest.main()
