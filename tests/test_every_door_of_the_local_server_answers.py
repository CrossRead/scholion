"""Every route of the local web interface is opened, and the writes are checked.

The web is not a view onto the CLI — the parity rule makes the two equal ways in,
and `contract.server_routes()` enumerates forty-six of them. `test_server_guard`
proves that a foreign page cannot use them; it opens four. The rest — every read
the page renders itself from, and every write that changes somebody's medical
profile — had no test that called them at all, and the module sat at 36.5%.

What that leaves undetected is not a crash. A crash in a route shows up as an
empty panel the moment anybody opens the page. It is the quieter shape: a route
that answers 200 with the wrong structure, a write that reports `ok` and stores
nothing, a refusal that arrives in the wrong language, an internal error whose
message carries the absolute path of somebody's home directory out in the body of
an HTTP response.

The sweep is driven from `contract.server_routes()` rather than from a list typed
here, so a route added tomorrow is opened tomorrow. Two are named as exceptions
and each says why.

The profile is a COPY of the fixture in a temporary directory, because these
tests write to it on purpose.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import support
from scholion import contract, server

#: Routes the sweep does not call, by name and with the reason.
#:
#: `/api/diag` goes out to the network on purpose — it is the connectivity check,
#: and the suite runs with SCHOLION_OFFLINE=1 precisely so that no result depends
#: on whether a reference database is answering today. Its refusal path is
#: checked below instead.
#:
#: `/api/pick-folder` with no path in the body opens the macOS folder dialog. A
#: test suite that puts a modal window on somebody's screen and waits for a click
#: is a test suite that hangs. It is called below WITH a path, which is the
#: branch that does not open anything.
SWEEP_EXCEPTIONS = {"GET /api/diag", "POST /api/pick-folder"}

#: Bodies for the POST routes. Every one writes into the temporary profile.
POST_BODIES = {
    "/api/labs": {"marker": "glucose", "date": "2026-05", "value": 5.1},
    "/api/metrics": {"metric": "weight", "date": "2026-05-01", "value": 78.4},
    "/api/medications": {"name": "test-drug", "dose": "1 tab", "note": "from a test"},
    "/api/medications/remove": {"name": "test-drug"},
    "/api/goal": {"keys": []},
    "/api/focus/log": {"date": "2026-05-01", "alcohol": "", "note": "a test entry"},
    "/api/metrics/profile": {"height_cm": 180},
    "/api/clear-folder": {"domain": "labs_docs"},
    "/api/wearable-primary": {"device": "garmin"},
    "/api/ingest-wearable": {"path": ""},
    "/api/ingest-garmin": {"path": ""},
    "/api/ingest-labs": {"path": ""},
    "/api/ingest-studies": {"path": ""},
    "/api/run-update": {},
    "/api/assistant/context": {},
    "/api/pick-folder": {"domain": "labs_docs", "path": "/tmp"},
}


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Live(unittest.TestCase):
    """A real server on loopback, over a copy of the fixture profile."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="scholion-routes-")
        cls._profile = Path(cls._tmp) / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, cls._profile)
        cls._was = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(cls._profile)
        cls.port = _free_port()
        cls.srv = server._Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(50):
            try:
                cls.call("/api/ping")
                break
            except Exception:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        if cls._was is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = cls._was
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def call(cls, path, data=None, headers=None, raw=None, method=None):
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(cls.base + path, data=body,
                                     method=method or ("POST" if body is not None else "GET"))
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def json_of(self, path, **kw):
        code, body = self.call(path, **kw)
        self.assertEqual(200, code, f"{path} answered {code}: {body[:200]}")
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:                    # pragma: no cover
            raise AssertionError(f"{path} did not answer JSON ({e}): {body[:200]}") from e


class TestEveryRouteAnswers(_Live):

    def test_every_get_route_answers_json(self):
        """A panel of the page each. An empty answer is legitimate — the fixture
        profile has no genome and no wearable — but an answer there must be."""
        opened = 0
        for route in contract.server_routes():
            if not route.startswith("GET ") or route in SWEEP_EXCEPTIONS:
                continue
            path = route.split(" ", 1)[1]
            with self.subTest(route=route):
                self.assertIsInstance(self.json_of(path), dict)
                opened += 1
        self.assertGreater(opened, 25, "the sweep opened almost nothing — it is reading "
                                       "an empty list of routes and proving nothing")

    def test_every_post_route_has_a_body_to_be_called_with(self):
        """The list above is written by hand, so it is compared against the
        contract: a write route added without one here would be swept past in
        silence, which is the failure this file exists to prevent."""
        declared = {r.split(" ", 1)[1] for r in contract.server_routes() if r.startswith("POST ")}
        self.assertEqual(set(), declared - set(POST_BODIES),
                         "these write routes have no body in this test and are never called")

    def test_every_post_route_answers_json(self):
        for path, body in sorted(POST_BODIES.items()):
            with self.subTest(route=path):
                code, text = self.call(path, body)
                self.assertEqual(200, code, f"{path} answered {code}: {text[:200]}")
                self.assertIsInstance(json.loads(text), dict)

    def test_an_unknown_route_is_a_404_both_ways(self):
        for method, data in (("GET", None), ("POST", {})):
            code, body = self.call("/api/no-such-thing", data)
            self.assertEqual(404, code)
            self.assertIn("unknown route", body)


class TestTheWritesReallyWrite(_Live):

    def profile_json(self, name):
        return json.loads((self._profile / name).read_text(encoding="utf-8"))

    def test_a_lab_point_reaches_the_file(self):
        self.call("/api/labs", {"marker": "glucose", "date": "2026-06", "value": 5.4})
        series = self.profile_json("labs.json")["markers"]["glucose"]["series"]
        self.assertIn(("2026-06", 5.4), [(p["date"], p["value"]) for p in series])

    def test_a_prescription_is_added_and_then_taken_away_again(self):
        self.call("/api/medications", {"name": "aspirin-test", "dose": "75 mg"})
        names = [m["name"] for m in self.json_of("/api/medications")["medications"]]
        self.assertIn("aspirin-test", names)
        self.call("/api/medications/remove", {"name": "aspirin-test"})
        names = [m["name"] for m in self.json_of("/api/medications")["medications"]]
        self.assertNotIn("aspirin-test", names)

    def test_a_metric_point_reaches_the_file(self):
        self.call("/api/metrics", {"metric": "weight", "date": "2026-06-01", "value": 77.0})
        series = self.profile_json("metrics.json")["metrics"]["weight"]["series"]
        self.assertIn(("2026-06-01", 77.0), [(p["date"], p["value"]) for p in series])

    def test_a_device_the_build_cannot_read_is_refused_by_name(self):
        """A typo must not quietly mean «nobody», which looks identical on screen
        to a device having been chosen."""
        got = self.json_of("/api/wearable-primary", data={"device": "grmin"})
        self.assertFalse(got.get("ok"))
        self.assertIn("grmin", json.dumps(got, ensure_ascii=False))

    def test_the_assistant_context_is_written_where_a_person_can_read_it_first(self):
        got = self.json_of("/api/assistant/context", data={})
        out = self._profile / "assistant_context.txt"
        self.assertTrue(out.exists(), "the bundle was not saved next to the profile")
        self.assertEqual(got["chars"], len(got["text"]))
        if os.name == "posix":
            mode = stat.S_IMODE(out.stat().st_mode)
            self.assertEqual(0o600, mode,
                             "a file of personal data was left readable by everybody")

    def test_a_folder_can_be_set_without_opening_a_dialog(self):
        got = self.json_of("/api/pick-folder", data={"domain": "labs_docs", "path": "/tmp"})
        self.assertTrue(got.get("ok"))
        self.assertIn("labs_docs", json.dumps(self.json_of("/api/source-config")))


class TestWhatThePageItselfIsServed(_Live):

    def test_the_page_and_its_assets_come_back(self):
        for path, kind in (("/", "text/html"), ("/index.html", "text/html"),
                           ("/icon.svg", "image/svg+xml"), ("/dna.svg", "image/svg+xml"),
                           ("/chart.min.js", "javascript"), ("/pico.min.css", "text/css")):
            with self.subTest(path=path):
                code, body = self.call(path)
                self.assertEqual(200, code, f"{path} answered {code}")
                self.assertTrue(body.strip(), f"{path} came back empty")

    def test_the_style_layer_is_served_from_here_and_not_from_the_internet(self):
        """Vendored on purpose: the interface has to keep working with no network
        reachable at all."""
        code, body = self.call("/pico.min.css")
        self.assertEqual(200, code)
        self.assertGreater(len(body), 1000, "pico.min.css is a stub")

    def test_an_asset_that_is_not_there_is_a_404_in_json(self):
        with mock.patch.object(server, "_WEB", Path(self._tmp) / "no-web"):
            code, body = self.call("/icon.svg")
        self.assertEqual(404, code)
        self.assertIn("not found", body)


class TestTheLanguageIsAPropertyOfTheRequest(_Live):

    def test_the_catalogue_comes_back_for_the_language_that_was_asked_for(self):
        en = self.json_of("/api/i18n?lang=en")
        ru = self.json_of("/api/i18n?lang=ru")
        self.assertEqual("en", en["lang"])
        self.assertEqual("ru", ru["lang"])
        self.assertTrue(en["messages"] and ru["messages"])
        self.assertNotEqual(en["messages"], ru["messages"])

    def test_a_language_nobody_has_means_english(self):
        self.assertEqual("en", self.json_of("/api/i18n?lang=kl")["lang"])

    def test_two_tabs_in_two_languages_do_not_disturb_each_other(self):
        """The language is fixed for the length of one request and remembered
        nowhere, so the same profile can be read in two languages at once."""
        ru = self.json_of("/api/i18n?lang=ru")["lang"]
        en = self.json_of("/api/i18n?lang=en")["lang"]
        self.assertEqual(("ru", "en"), (ru, en))

    def test_a_refusal_arrives_in_the_language_the_page_asked_for(self):
        _, en = self.call("/api/ping?lang=en", headers={"Host": "evil.example.com"})
        _, ru = self.call("/api/ping?lang=ru", headers={"Host": "evil.example.com"})
        self.assertNotEqual(en, ru, "the refusal is worded in one language whatever was asked")


class TestWhatAMalformedRequestGets(_Live):
    """Only what `test_server_guard` does not already own.

    The size limit, a `Content-Length` that is not a number, and the fact that an
    internal error does not carry a filesystem path out in the response are all
    tested there, and tested better — an oversized body is declared in the header
    rather than actually sent, so the client is not left writing into a socket
    the server has already answered on. Repeating them here would give this
    project two places to change when that contract moves.
    """

    def test_a_body_that_is_not_json_is_read_as_an_empty_one(self):
        """Not a 500. The route then answers about a request with no fields,
        which is a refusal it already knows how to word."""
        code, body = self.call("/api/medications", raw=b"{not json at all")
        self.assertEqual(200, code)
        self.assertIsInstance(json.loads(body), dict)

    def test_a_post_with_no_body_at_all_is_read_as_an_empty_one(self):
        code, body = self.call("/api/medications", raw=b"")
        self.assertEqual(200, code)
        self.assertIsInstance(json.loads(body), dict)


class TestTheBackgroundUpdate(_Live):

    def test_a_second_start_while_one_is_running_is_refused_rather_than_queued(self):
        server._UPD["running"] = True
        try:
            got = self.json_of("/api/run-update", data={})
            self.assertFalse(got["started"])
            self.assertTrue(got["busy"])
        finally:
            server._UPD["running"] = False

    def test_the_status_names_what_is_happening_in_words(self):
        got = self.json_of("/api/update-status")
        for field in ("running", "rc", "tail", "hint"):
            self.assertIn(field, got)

    def test_a_missing_update_script_is_reported_rather_than_run(self):
        """The worker names the script it could not find. Pointed at a directory
        with no script in it, nothing is executed at all — no subprocess starts
        during this test."""
        with tempfile.TemporaryDirectory() as empty:
            with mock.patch.object(server, "_INGEST", Path(empty)):
                server._run_update_bg()
                for _ in range(100):
                    if not server._UPD["running"]:
                        break
                    time.sleep(0.02)
        self.assertEqual(5, server._UPD["rc"])
        self.assertIn("not found", server._UPD["log"])


class TestTheNativeFolderDialog(unittest.TestCase):
    """The one piece of this server that talks to the desktop.

    `subprocess.run` is replaced throughout: a test that actually opened a modal
    window would wait for somebody to click it. What is checked is the reading of
    what osascript said, and that has real content — a cancelled dialog is
    reported by macOS in the language of the SYSTEM, so the Russian stem is a
    value this code compares against, and mistaking a cancellation for a failure
    puts an error on screen where the person simply changed their mind.
    """

    def setUp(self):
        """macOS, declared rather than assumed.

        `_choose_folder_native` returns «type the path in by hand» before it
        reaches osascript on anything but darwin — so on a Linux runner these
        tests exercised the guard and not the reading of what the dialog said.
        They were written on a Mac, passed there, and failed the moment they ran
        anywhere else. The platform belongs to the fixture: the branch under test
        is the macOS one, and the OTHER branch has its own test below.
        """
        self._as_macos = mock.patch.object(server.sys, "platform", "darwin")
        self._as_macos.start()
        self.addCleanup(self._as_macos.stop)

    @staticmethod
    def _result(code=0, out="", err=""):
        return mock.Mock(returncode=code, stdout=out, stderr=err)

    def test_a_chosen_folder_comes_back_as_a_path(self):
        with mock.patch.object(server.subprocess, "run",
                               return_value=self._result(out="/Users/x/Documents/labs\n")):
            got = server._choose_folder_native("pick a folder")
        self.assertTrue(got["ok"])
        self.assertEqual("/Users/x/Documents/labs", got["path"])

    def test_a_cancelled_dialog_is_a_cancellation_and_not_an_error(self):
        for said in ("User canceled.", "execution error: (-128)", "Пользователь отменил операцию"):
            with self.subTest(said=said):
                with mock.patch.object(server.subprocess, "run",
                                       return_value=self._result(code=1, err=said)):
                    got = server._choose_folder_native("pick a folder")
                self.assertTrue(got.get("canceled"), f"{said!r} was reported as a failure")
                self.assertNotIn("error", got)

    def test_a_real_failure_is_reported_as_one(self):
        with mock.patch.object(server.subprocess, "run",
                               return_value=self._result(code=1, err="osascript is not installed")):
            got = server._choose_folder_native("pick a folder")
        self.assertFalse(got["ok"])
        self.assertFalse(got.get("canceled"))
        self.assertIn("osascript", got["error"])

    def test_a_dialog_that_answered_nothing_is_not_an_empty_path(self):
        with mock.patch.object(server.subprocess, "run", return_value=self._result(out="  ")):
            got = server._choose_folder_native("pick a folder")
        self.assertFalse(got["ok"])
        self.assertTrue(got["error"])

    def test_a_quote_in_the_prompt_cannot_close_the_script(self):
        seen = {}

        def capture(cmd, **kw):
            seen["script"] = cmd[-1]
            return self._result(out="/tmp\n")

        with mock.patch.object(server.subprocess, "run", side_effect=capture):
            server._choose_folder_native('say "hello" now')
        self.assertNotIn('"hello"', seen["script"],
                         "a double quote from the prompt reached the AppleScript intact")

    def test_off_macos_it_asks_for_the_path_to_be_typed(self):
        with mock.patch.object(server.sys, "platform", "linux"):
            got = server._choose_folder_native("pick a folder")
        self.assertFalse(got["ok"])
        self.assertTrue(got["error"])


class TestTheUpdateWorkerReadsItsScript(unittest.TestCase):
    """The background ClinVar refresh, with the process replaced.

    Nothing is executed: `Popen` is a stub that yields lines and a return code.
    What is being tested is that the output reaches the status the page polls,
    and that the one return code with a meaning attached keeps it.
    """

    class _FakeProc:
        def __init__(self, lines, code):
            self.stdout = iter(lines)
            self._code = code
            self.returncode = None

        def wait(self):
            self.returncode = self._code
            return self._code

    def _run(self, lines, code):
        proc = self._FakeProc(lines, code)
        with mock.patch.object(server.subprocess, "Popen", return_value=proc):
            server._run_update_bg()
            for _ in range(200):
                if not server._UPD["running"]:
                    break
                time.sleep(0.02)
        return dict(server._UPD)

    def test_the_output_of_the_script_reaches_the_status(self):
        got = self._run(["downloading clinvar\n", "done\n"], 0)
        self.assertEqual(0, got["rc"])
        self.assertIn("downloading clinvar", got["log"])
        self.assertFalse(got["running"])

    def test_the_one_return_code_with_a_meaning_keeps_it(self):
        """3 means bcftools is missing, and the page turns that into a sentence
        about installing it rather than a number."""
        got = self._run(["no bcftools\n"], 3)
        self.assertEqual(3, got["rc"])
        self.assertEqual("server.update.no_bcftools", got["hint"],
                         "the hint is a catalogue key, so the tab that reads it chooses "
                         "the language, not the tab that started the run")

    def test_a_worker_that_throws_ends_rather_than_hanging(self):
        with mock.patch.object(server.subprocess, "Popen", side_effect=OSError("no bash")):
            server._run_update_bg()
            for _ in range(200):
                if not server._UPD["running"]:
                    break
                time.sleep(0.02)
        self.assertEqual(1, server._UPD["rc"])
        self.assertIn("no bash", server._UPD["log"])
        self.assertFalse(server._UPD["running"], "the status is stuck on «running» for ever")

    def tearDown(self):
        server._UPD.update({"running": False, "rc": None, "log": "", "hint": ""})


class TestBringingTheServerUp(unittest.TestCase):
    """`serve()` itself, without leaving anything listening."""

    def test_a_non_loopback_bind_is_refused_unless_it_was_meant(self):
        was = os.environ.pop("SCHOLION_ALLOW_REMOTE", None)
        try:
            with self.assertRaises(SystemExit) as caught:
                server.serve("0.0.0.0", _free_port(), open_browser=False)
            self.assertIn("0.0.0.0", str(caught.exception))
        finally:
            if was is not None:
                os.environ["SCHOLION_ALLOW_REMOTE"] = was

    def test_a_port_nobody_is_on_is_not_ours(self):
        self.assertFalse(server._already_ours("127.0.0.1", _free_port()))

    def test_our_own_instance_is_recognised(self):
        port = _free_port()
        srv = server._Server(("127.0.0.1", port), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for _ in range(50):
                if server._already_ours("127.0.0.1", port):
                    break
                time.sleep(0.05)
            self.assertTrue(server._already_ours("127.0.0.1", port),
                            "a running Scholion was not recognised, so a second one would "
                            "take another port and the person would have two")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_the_host_check_accepts_every_shape_of_loopback(self):
        for host in ("127.0.0.1", "localhost", "127.0.0.1:1521", "[::1]", "[::1]:1521"):
            with self.subTest(host=host):
                self.assertTrue(server._host_is_local(host))
        for host in ("evil.example.com", "192.168.1.10", "", None):
            with self.subTest(host=host):
                self.assertFalse(server._host_is_local(host))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
