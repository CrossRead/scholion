"""Network requests to public databases (RxNorm, Ensembl, ClinVar, translators).

A key detail on macOS: Python.framework often does NOT have the root certificates installed
(«Install Certificates.command» has to be run once), because of which any HTTPS through
urllib fails with CERTIFICATE_VERIFY_FAILED — and then «nothing can be found». That is why a
certificate verification error is retried here with a non-strict SSL context. These are public
read-only APIs (no patient data is transmitted), so it is acceptable for a local tool.
"""
from __future__ import annotations
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
import urllib.parse
from typing import Any, Dict, Optional

from .i18n import t as _t

_UNVERIFIED: Optional[ssl.SSLContext] = None
_UA = {"User-Agent": "scholion", "Accept": "application/json"}

#: What the connectivity check may probe: a NAME, and the exact address behind
#: it. The caller chooses the name; it never supplies an address.
#:
#: The first version took a url and validated its scheme and host against a list.
#: That closed the hole it was written for — `file:///etc/passwd` came back
#: `ok: true`, and any page in the origin could make this server fetch anything —
#: and it left a smaller one open by construction: an allowed HOST still accepts
#: any path and any query, so the address could still carry a payload outward.
#: Checking a string the caller composed is always a race between the check and
#: the imagination of whoever writes the string. Not accepting a string at all
#: ends it: what leaves this machine is a constant from this file.
DIAG_TARGETS = {
    "default": "https://rxnav.nlm.nih.gov/REST/version.json",
}

# Kept as a second gate over the RESOLVED address rather than as the first gate
# over the caller's: cheap, and it keeps the rule true if somebody later adds a
# target by hand. Derived from the table above, so the two cannot disagree.
_DIAG_HOSTS = frozenset(
    h for h in (urllib.parse.urlsplit(u).hostname for u in DIAG_TARGETS.values()) if h
)


def _diag_url_ok(url: str) -> bool:
    """A diagnostic target must be https to one of the product's own hosts.

    Rejects file://, ftp://, http:// downgrade, and every host the tool does not
    itself use — before a request is made, so a rejected url is never fetched.

    This checks scheme and host, not path or query: it was never meant to pin an
    exact endpoint, only the six hosts the product itself ever talks to. Which is
    exactly why a redirect must never be followed past this point — see
    `_NoRedirect` below. A host on this list responding with its own redirect is
    not this function's problem to solve; not chasing it is.
    """
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return u.scheme == "https" and u.hostname in _DIAG_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect. `_diag_url_ok` approves a host, not a request
    chain — `urlopen` follows 3xx by default, and a checked host redirecting
    elsewhere would land the request on a host that was never checked at all."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _diag_opener(ctx: Optional[ssl.SSLContext]) -> "urllib.request.OpenerDirector":
    """An opener for `diagnose()` alone: never redirects, optionally unverified."""
    handlers = [_NoRedirect()]
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def offline() -> bool:
    """The «no network» mode: SCHOLION_OFFLINE=1 forbids any outgoing requests.

    It is needed for two reasons. Tests have to be deterministic: the result cannot
    depend on whether RxNav is answering today, and on a machine without internet
    waiting out a timeout looks like a hung program. And the user must have a way
    to say «do not go anywhere» with a single environment variable, without working
    out which reference sources exactly are being queried.

    Everything requested over the network is a public reference source; patient
    data never leaves the machine, in any mode.
    """
    return os.environ.get("SCHOLION_OFFLINE", "").strip() in ("1", "true", "yes")


def insecure_allowed() -> bool:
    """Has the user explicitly permitted skipping certificate verification?

    SCHOLION_TLS_INSECURE=1 is the only way to get there. It used to happen by
    itself, on any failure, and silently — see the comment on _open().
    """
    return os.environ.get("SCHOLION_TLS_INSECURE", "").strip() in ("1", "true", "yes")


def _unverified() -> ssl.SSLContext:
    global _UNVERIFIED
    if _UNVERIFIED is None:
        _UNVERIFIED = ssl._create_unverified_context()
    return _UNVERIFIED


def _is_cert_error(e: BaseException) -> bool:
    """Is this a certificate verification failure, and nothing else?

    Catching `ssl.SSLCertVerificationError` directly does not work: urllib wraps
    what the socket raised into `urllib.error.URLError` and puts the original in
    `.reason`. Verified against a local server with a self-signed certificate —
    `urlopen` raises `URLError`, and `isinstance(e, ssl.SSLCertVerificationError)`
    is False.

    That mattered: a version of this file caught the bare class, so the branch
    never ran on a real request. Verification was never dropped — but neither did
    SCHOLION_TLS_INSECURE do anything, and the message telling the user to set it
    was untrue. The unit tests passed because they raised the bare class, a shape
    the real path does not produce.
    """
    if isinstance(e, ssl.SSLCertVerificationError):
        return True
    reason = getattr(e, "reason", None)
    return isinstance(reason, ssl.SSLCertVerificationError)


def certificate_fallback(e: BaseException) -> ssl.SSLContext:
    """The one way, anywhere in this project, to retry a request unverified.

    A caller hands over the exception it caught. This answers with a context only
    when all three of the following hold, and raises otherwise:

    * the failure really was certificate verification — decided by the TYPE of
      the exception, never by looking for «SSL» in its text;
    * the person allowed it out loud, in the environment;
    * the attempt announces itself, every time it is made.

    It exists because that rule had been fixed in `_open` and nowhere else. This
    is the module that talks to the network, but it was never the only file that
    does: `src/ingest/build_longevitymap.py` and
    `src/ingest/build_longevity_sites.py` each carried their own copy of the
    fallback `_open` used to have, and both copies still had the two faults it
    was rewritten to remove — they decided from the text of the error, and they
    asked nobody. A message that merely mentions SSL (a protocol mismatch, a
    proxy refusing CONNECT) bought an unverified retry there.

    What those two scripts build is `knowledge/longevitymap.json` and the list of
    longevity positions — a catalogue that then travels to every reader, not a
    number on one person's screen. So the fallback stops being a habit each file
    repeats and becomes a function each file calls.
    """
    if not _is_cert_error(e):
        raise e                        # a timeout, DNS, a 5xx — not our business here
    if not insecure_allowed():
        raise RuntimeError(f"{_t('net.tls_verify_failed')} {_t('net.certificates_hint')}") from e
    # The warning is printed on EVERY request, not once per run: a quiet
    # insecure mode is bad precisely because it is forgotten.
    print(_t("net.tls_insecure_warning"), file=sys.stderr, flush=True)
    return _unverified()


def _open(url: str, timeout: int, headers: Optional[Dict[str, str]]) -> bytes:
    """Fetch a public reference source. Certificate verification is NOT dropped
    on its own.

    What used to be here: `except Exception` around the request and a retry with
    an unverified context. Two faults in three lines. The catch was not narrowed
    to a certificate error, so a DNS failure, a timeout, a reset connection or an
    HTTP error all dropped verification too. And it was silent — nothing in the
    output said the answer had arrived over an unchecked channel.

    The risk is not the request but the ANSWER. Only a drug name goes out; what
    comes back is the drug class from RxNorm and the gene↔drug pair from CPIC,
    and those feed the second opinion on a prescription. A substituted answer is
    not a leak, it is a wrong conclusion about a medicine, stated with full
    confidence.

    So: the certificate error is caught by its own type, the way round it exists
    only with explicit permission, and every request made that way says so. All
    three of those now live in `certificate_fallback`, because this was not the
    only file that needed them — see its own note.
    """
    if offline():
        raise RuntimeError(_t("net.offline"))
    req = urllib.request.Request(url, headers=headers or _UA)
    try:
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:
        return urllib.request.urlopen(
            req, timeout=timeout, context=certificate_fallback(e)).read()


def get_json(url: str, timeout: int = 15, headers: Optional[Dict[str, str]] = None) -> Optional[Any]:
    try:
        return json.loads(_open(url, timeout, headers).decode("utf-8"))
    except Exception:
        return None


def get_text(url: str, timeout: int = 15, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    try:
        return _open(url, timeout, headers).decode("utf-8", "replace")
    except Exception:
        return None


def diagnose(target: str = "default") -> Dict[str, Any]:
    """Check internet access from this Python. Returns the mode (verified/unverified) and the error.

    `target` is a NAME from `DIAG_TARGETS`, never an address: this function runs
    behind a loopback HTTP route that any page in the browser can reach, and a
    caller who can name an address can make this machine fetch it. A name that is
    not in the table is refused and nothing is opened. Redirects are refused too,
    for the same reason — an approved address that answers 3xx would otherwise
    lead the request to one nobody approved (see `_NoRedirect`).
    """
    url = DIAG_TARGETS.get((target or "").strip())
    if not url or not _diag_url_ok(url):
        return {"ok": False, "target": target,
                "error": _t("net.diag_target_unknown", value=str(target),
                            accepted=", ".join(sorted(DIAG_TARGETS))),
                "refused": True}
    if offline():
        return {"ok": False, "offline": True, "url": url,
                "error": _t("net.offline_deliberate"),
                "hint": _t("net.offline_hint")}
    req = urllib.request.Request(url, headers={"User-Agent": "scholion"})
    last = ""
    for label, ctx in (("verified", None), ("unverified", _unverified())):
        try:
            resp = _diag_opener(ctx).open(req, timeout=10)
            return {"ok": True, "mode": label, "status": getattr(resp, "status", 200), "url": url}
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                last = f"redirect refused ({e.code} → {e.headers.get('Location', '?')})"
            else:
                last = f"{type(e).__name__}: {e}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
    hint = ""
    if "CERTIFICATE" in last.upper() or "SSL" in last.upper():
        hint = _t("net.certificates_hint")
    return {"ok": False, "error": last, "hint": hint, "url": url}
