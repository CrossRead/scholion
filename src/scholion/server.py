"""The local web server (standard library, without dependencies).

Serves the frontend (web/index.html) and a JSON API on top of the core. Reads and (on
request) writes profile/. Run with: python3 -m scholion serve  →  http://127.0.0.1:8765

Local only (bind 127.0.0.1). The data does not leave the machine.

The language of a reply is a property of the REQUEST, not of the server. The page
appends `?lang=xx` to every call, the handler hands that to `i18n.set_lang()` for
the duration of the request, and nothing is remembered afterwards: two browser
tabs may read the same profile in two languages at the same time, and neither
knows about the other. An absent or unknown value means English.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import engine, store, core, i18n
from .i18n import t as _t

# The request body limit. Everything the application accepts over POST is a lab point,
# a drug or a path to a folder: kilobytes. Without a limit, `rfile.read(n)` will allocate
# as much memory as the header asks for.
_MAX_BODY = 1 << 20        # 1 MiB

# The names under which the server may be addressed. The check is needed not against a
# «hacker on the network» — the socket is open on loopback only anyway — but against a
# foreign page in the browser: it cannot read our reply (CORS forbids that), but it can
# send a POST, and the profile would change. At the same time this is protection against
# DNS rebinding, where a foreign name resolves to 127.0.0.1.
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _host_is_local(raw: str) -> bool:
    """`Host:` without the port is in the list of local names."""
    h = (raw or "").strip()
    if not h:
        return False
    h = (h.split("]")[0] + "]") if h.startswith("[") else h.split(":")[0]
    return h in _LOCAL_HOSTS


_WEB = Path(__file__).resolve().parent / "web"
_INGEST = Path(__file__).resolve().parent.parent / "ingest"
VERSION = "2026-07-30 · radar dynamics + tab freshness"

# The state of the background check for database updates (ClinVar × genome).
# `hint` holds a catalogue KEY, not a phrase: the check is started by one browser
# tab and may be watched from another one set to a different language, so the
# wording is chosen when the status is read, not when it is written.
_UPD = {"running": False, "rc": None, "log": "", "hint": ""}


def _run_update_bg():
    """In the background: update ClinVar and re-check the genome (update_check.sh)."""
    import threading

    def worker():
        _UPD["running"] = True
        _UPD["rc"] = None
        _UPD["log"] = ""
        _UPD["hint"] = ""
        script = _INGEST / "update_check.sh"
        if not script.exists():
            # The log is the raw output of a shell script, so it is not a catalogue
            # phrase; the line the server adds itself stays in one language.
            _UPD["log"] = f"not found: {script}"
            _UPD["rc"] = 5
            _UPD["running"] = False
            return
        try:
            env = dict(os.environ)
            env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
            env["PROJECT_DIR"] = str(_INGEST.parent.parent)
            p = subprocess.Popen(["bash", str(script)], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, env=env, text=True, bufsize=1)
            for line in p.stdout:
                _UPD["log"] = (_UPD["log"] + line)[-4000:]
            p.wait()
            _UPD["rc"] = p.returncode
            if p.returncode == 3:
                _UPD["hint"] = "server.update.no_bcftools"
        except Exception as e:  # noqa
            _UPD["rc"] = 1
            _UPD["log"] += f"\n{e}"
        finally:
            _UPD["running"] = False

    threading.Thread(target=worker, daemon=True).start()

# The prompt of the native folder dialog, by data domain. Keys, not phrases: the
# dialog is opened for the browser tab that asked, in that tab's language.
_PICK_PROMPTS = {
    "labs": "server.pick.labs",
    "labs_docs": "server.pick.labs_docs",
    "medications": "server.pick.medications",
    "med_docs": "server.pick.med_docs",
    "metrics": "server.pick.metrics",
    "genome": "server.pick.genome",
}


def _choose_folder_native(prompt: str) -> dict:
    """Open the native folder-picking dialog (macOS). Returns a POSIX path.

    Works when the server is started inside the user's graphical session (via
    Scholion.command/.app). Off macOS it returns a hint to enter the path by hand."""
    if sys.platform != "darwin":
        return {"ok": False, "error": _t("server.pick.macos_only")}
    safe = prompt.replace('"', "'")
    script = (
        'tell application "System Events" to activate\n'
        f'set theFolder to choose folder with prompt "{safe}"\n'
        'return POSIX path of theFolder'
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if r.returncode != 0:
        err = r.stderr or ""
        # The words are macOS's, not ours: osascript reports a cancelled dialog in the
        # language of the system, so the Russian stem is a VALUE we compare against.
        if "-128" in err or "User canceled" in err or "отмен" in err.lower():
            return {"ok": False, "canceled": True}
        return {"ok": False, "error": err.strip() or _t("server.pick.failed")}
    path = r.stdout.strip()
    return {"ok": True, "path": path} if path else {"ok": False, "error": _t("server.pick.empty_path")}


def _marker_catalog():
    """The list of markers for the add forms. The implementation lives in the core, so that
    the web and the CLI (`markers`) answer with one and the same list, not two similar ones."""
    return core.marker_catalog()


class Handler(BaseHTTPRequestHandler):
    server_version = "Scholion/0.1"

    # ---- utilities ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, ctype: str):
        if not path.exists():
            self._json({"error": "not found"}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _lang(self, query: dict) -> str:
        """Fix the language of THIS request from `?lang=`, and answer with the code chosen.

        Called before anything else is done with the request, including the refusal
        checks, so that a refusal is worded in the language the page asked for. The
        choice is not stored anywhere: `set_lang` writes into thread-local state,
        and the thread ends together with the request.
        """
        return i18n.set_lang((query.get("lang") or [""])[0])

    def _deny(self, state_changing: bool):
        """The reason for refusal, or None. Checked before any work with the request."""
        if not _host_is_local(self.headers.get("Host", "")):
            return _t("server.deny.foreign_host")
        if state_changing:
            origin = (self.headers.get("Origin") or "").strip()
            # curl and the CLI have no Origin — they are not a browser, and there is
            # nothing to forge there. If it is present, it must be ours: a cross-site POST
            # from an attacker's page carries that page's own Origin.
            if origin and not _host_is_local(urlparse(origin).netloc):
                return _t("server.deny.cross_site")
        return None

    def _read_body(self):
        """The request body as an object. `None` — the body was rejected, a reply was already sent."""
        raw = self.headers.get("Content-Length", "")
        try:
            n = int(raw or 0)
        except ValueError:
            self._json({"error": _t("server.bad_content_length")}, 400)
            return None
        if n < 0:
            self._json({"error": _t("server.bad_content_length")}, 400)
            return None
        if n > _MAX_BODY:
            self._json({"error": _t("server.body_too_large", bytes=_MAX_BODY)}, 413)
            return None
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _fail(self, exc: BaseException):
        """An internal error: the details go to the owner's console, a generic one goes out.

        The `str(exc)` of a file error is an absolute path, that is, the home directory
        and the user name inside the body of an HTTP response. It should be read by the
        person who started the server, not by the one who sent the request.
        """
        traceback.print_exc()
        return self._json({"error": _t("server.internal_error")}, 500)

    def log_message(self, *a):  # quieter in the console
        pass

    # ---- routes ----
    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        chosen = self._lang(q)
        deny = self._deny(state_changing=False)
        if deny:
            return self._json({"error": deny}, 403)
        try:
            if p == "/api/ping":
                return self._json({"app": "Scholion", "ok": True, "version": VERSION})
            if p == "/api/i18n":
                # The whole catalogue in one reply: the page renders its own labels
                # from the same source the reports are rendered from, so a phrase
                # cannot exist in the interface and be missing from a report.
                return self._json({"lang": chosen, "available": list(i18n.available()),
                                   "messages": i18n.messages(chosen)})
            if p == "/api/diag":
                from . import net
                which = (q.get("url") or [""])[0]
                return self._json(net.diagnose(which) if which else net.diagnose())
            if p in ("/", "/index.html"):
                return self._file(_WEB / "index.html", "text/html; charset=utf-8")
            if p == "/icon.svg":
                return self._file(_WEB / "icon.svg", "image/svg+xml")
            if p == "/dna.svg":
                return self._file(_WEB / "dna.svg", "image/svg+xml")
            if p == "/chart.min.js":
                return self._file(_WEB / "chart.min.js", "application/javascript; charset=utf-8")
            if p == "/favicon.ico":
                return self._file(_WEB / "favicon.ico", "image/x-icon")
            if p in ("/favicon.png", "/favicon-32.png", "/favicon-16.png", "/apple-touch-icon.png"):
                return self._file(_WEB / p.lstrip("/"), "image/png")
            if p == "/api/overview":
                return self._json(engine.overview())
            if p == "/api/goal":
                return self._json(engine.goal_dashboard())
            if p == "/api/labs":
                return self._json(engine.analyze_labs())
            if p == "/api/drug":
                return self._json(engine.check_drug_gene((q.get("name") or [""])[0]))
            if p == "/api/suggest-tests":
                return self._json(engine.suggest_tests())
            if p == "/api/genome":
                return self._json(engine.genome_lookup(
                    rsid=(q.get("rsid") or [None])[0], gene=(q.get("gene") or [None])[0]))
            if p == "/api/genome-status":
                return self._json({**engine.genome_status(), "gaps": core.genome_gaps()})
            if p == "/api/second-opinion":
                return self._json(engine.second_opinion())
            if p == "/api/radar":
                return self._json(engine.health_radar())
            if p == "/api/prescription-check":
                return self._json(engine.check_new_prescription((q.get("name") or [""])[0]))
            if p == "/api/medications":
                return self._json({"medications": store.list_medications()})
            if p == "/api/limits":
                from . import limits as _lim
                return self._json(_lim.report())
            if p == "/api/markers":
                return self._json({"markers": _marker_catalog()})
            if p == "/api/metrics":
                return self._json(engine.metrics_summary())
            if p == "/api/focus":
                return self._json(engine.focus_dashboard())
            if p == "/api/lifestyle-brief":
                return self._json(engine.lifestyle_brief())
            if p == "/api/lifestyle":
                return self._json(engine.lifestyle())
            if p == "/api/clinvar":
                return self._json(engine.clinvar_findings())
            if p == "/api/prs":
                return self._json(engine.prs_findings())
            if p == "/api/longevity":
                return self._json(engine.longevity_findings())
            if p == "/api/genome-updates":
                return self._json({**engine.genome_updates(), "running": _UPD["running"]})
            if p == "/api/update-status":
                return self._json({"running": _UPD["running"], "rc": _UPD["rc"],
                                   "tail": _UPD["log"],
                                   "hint": _t(_UPD["hint"]) if _UPD["hint"] else ""})
            if p == "/api/sources":
                return self._json(engine.provenance())
            if p == "/api/source-config":
                return self._json({"folders": core.source_config()})
            if p == "/api/assistant":
                from . import assistant
                return self._json(assistant.status())
            return self._json({"error": "unknown route"}, 404)
        except Exception as e:
            return self._fail(e)

    def do_POST(self):
        u = urlparse(self.path)
        self._lang(parse_qs(u.query))
        deny = self._deny(state_changing=True)
        if deny:
            return self._json({"error": deny}, 403)
        body = self._read_body()
        if body is None:
            return None
        try:
            if u.path == "/api/labs":
                return self._json(store.add_lab_point(
                    body.get("marker", ""), body.get("date", ""), body.get("value"),
                    name=body.get("name"), unit=body.get("unit"),
                    ref_low=body.get("ref_low"), ref_high=body.get("ref_high"),
                    direction=body.get("direction")))
            if u.path == "/api/medications":
                return self._json(store.add_medication(
                    body.get("name", ""), body.get("dose", ""), body.get("note", "")))
            if u.path == "/api/medications/remove":
                return self._json(store.remove_medication(body.get("name", "")))
            if u.path == "/api/metrics":
                return self._json(store.add_metric_point(
                    body.get("metric", ""), body.get("date", ""), body.get("value"),
                    name=body.get("name"), unit=body.get("unit"),
                    ref_low=body.get("ref_low"), ref_high=body.get("ref_high"),
                    direction=body.get("direction")))
            if u.path == "/api/focus/log":
                return self._json(store.add_focus_entry(
                    body.get("date", ""), alcohol=body.get("alcohol") or "",
                    atenolol=bool(body.get("atenolol")), late_meal=bool(body.get("late_meal")),
                    note=body.get("note") or ""))
            if u.path == "/api/metrics/profile":
                return self._json(store.update_metric_profile(body))
            if u.path == "/api/pick-folder":
                domain = body.get("domain", "")
                # the path can be passed directly (manual entry), otherwise the native dialog
                if body.get("path"):
                    return self._json(store.set_source_folder(domain, body["path"]))
                res = _choose_folder_native(_t(_PICK_PROMPTS.get(domain, "server.pick.default")))
                if not res.get("ok"):
                    return self._json(res)
                saved = store.set_source_folder(domain, res["path"])
                return self._json({**saved, "path": res["path"]})
            if u.path == "/api/clear-folder":
                return self._json(store.clear_source_folder(body.get("domain", "")))
            if u.path == "/api/run-update":
                if _UPD["running"]:
                    return self._json({"started": False, "busy": True})
                _run_update_bg()
                return self._json({"started": True})
            if u.path == "/api/ingest-garmin":
                from . import garmin
                return self._json(garmin.reingest(body.get("path") or None))
            if u.path == "/api/ingest-studies":
                folder = body.get("path") or core.source_config().get("labs_docs")
                if not folder:
                    return self._json({"ok": False, "error": _t("server.no_studies_folder")})
                from . import ingest_studies
                return self._json(ingest_studies.ingest(folder, force=bool(body.get("force"))))
            if u.path == "/api/ingest-labs":
                folder = body.get("path") or core.source_config().get("labs_docs")
                if not folder:
                    return self._json({"ok": False, "error": _t("server.no_labs_folder")})
                from . import ingest_labs
                return self._json(ingest_labs.ingest(folder, force=bool(body.get("force"))))
            if u.path == "/api/assistant/context":
                # POST, not GET: the reply contains personal data, and a method that
                # changes or hands out state must not be callable by an image on a foreign
                # page. The file is written next to the profile so that the text can be
                # opened and read with one's own eyes before pasting it into a model.
                from . import assistant
                txt = assistant.context_bundle()
                out = Path(core.profile_dir()) / "assistant_context.txt"
                try:
                    out.write_text(txt, encoding="utf-8")
                    if os.name == "posix":
                        os.chmod(out, 0o600)   # the file contains personal data
                    saved = str(out)
                except OSError as e:
                    saved = _t("server.context_not_saved", error=e)
                return self._json({"ok": True, "text": txt, "chars": len(txt), "saved": saved})
            return self._json({"error": "unknown route"}, 404)
        except Exception as e:
            return self._fail(e)


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True   # reuse a socket in TIME_WAIT
    daemon_threads = True


def _already_ours(host: str, port: int) -> bool:
    """Is it OUR Scholion that is already sitting on the port?"""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/ping", timeout=1.5) as r:
            return b"Scholion" in r.read()
    except Exception:
        return False


def serve(host: str = "127.0.0.1", port: int = 1521, open_browser: bool = True, tries: int = 12) -> None:
    """Bring the server up. If the port is taken by OUR own older instance — open the browser on it.
    If it is taken by something else — take the next free port. The browser opens automatically."""
    import errno
    import threading
    import webbrowser

    # The lab integrity self-check at start-up (in the background, it does not block the server)
    def _selfcheck():
        try:
            from . import reconcile as _rec
            print(_rec.selfcheck_summary(_rec.reconcile()), flush=True)
        except Exception as _e:  # the check must not bring the application down
            print(_t("server.selfcheck_skipped", error=_e), flush=True)
    threading.Thread(target=_selfcheck, daemon=True).start()

    # 1) our instance is already running on the requested port → open the browser
    if _already_ours(host, port):
        url = f"http://{host}:{port}"
        print(_t("server.already_running", url=url))
        if open_browser:
            webbrowser.open(url)
        return

    # 2) find a free port (the requested one or the next)
    httpd = None
    chosen = None
    for p in range(port, port + tries):
        try:
            httpd = _Server((host, p), Handler)
            chosen = p
            break
        except OSError as e:
            if e.errno in (errno.EADDRINUSE, 48, 98):
                continue
            raise
    if httpd is None:
        print(_t("server.no_free_port", first=port, last=port + tries - 1))
        return

    url = f"http://{host}:{chosen}"
    if chosen != port:
        print(_t("server.port_busy", wanted=port, chosen=chosen))
    print(_t("server.listening", url=url))
    print(_t("server.profile", path=core.profile_dir()))
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n" + _t("server.stopped"))
        httpd.shutdown()
