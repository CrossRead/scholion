"""Nowhere in this project does a file decide, on its own, to stop checking a
certificate.

`net._open` was rewritten for exactly this: verification used to be dropped on
ANY failure, silently, and the repair narrowed it to a certificate error, put it
behind `SCHOLION_TLS_INSECURE`, and made every such request announce itself. That
repair was written into one function.

It was not a property of one function. Two build scripts —
`src/ingest/build_longevitymap.py` and `src/ingest/build_longevity_sites.py` —
each carried their own copy of the fallback `_open` used to have, and both copies
still had both faults: they asked whether the word «SSL» appeared in the text of
the exception (a protocol mismatch and a proxy refusing CONNECT both say yes),
and having decided yes they asked nobody for permission. What those two scripts
download becomes `knowledge/longevitymap.json` and the list of longevity
positions — a catalogue that ships to every reader, and a set of coordinates
somebody's genotypes are then read at.

So the rule is stated here for the whole tree rather than for the file where it
was noticed. This is the fourth time in this project that a repaired instance
turned out to be a class, and the sibling of this test
(`test_a_tls_context_names_its_floor.py`) is the third.

THE RULE. Where code disables verification — `ssl._create_unverified_context()`,
`verify_mode = ssl.CERT_NONE`, `check_hostname = False` — the same function must
consult an explicit permission: `net.certificate_fallback`, `insecure_allowed()`,
`SCHOLION_TLS_INSECURE`, or a parameter of its own named `insecure`. Reading the
text of an exception is not a permission; it is a guess about the cause.

THE ONE EXEMPTION, by name and with its reason. `net._unverified` builds the
object and does not decide to use it — that is its two callers' job, and they
differ: `certificate_fallback` gates the decision, while `diagnose` is the report
that says WHICH mode answered, over a constant address, which it cannot produce
without trying the unverified one. Exempting the constructor keeps the decision
in one place instead of spreading a gate into a factory.
"""
from __future__ import annotations

import ast
import io
import os
import pathlib
import ssl
import unittest
import urllib.error
from contextlib import redirect_stderr

import support  # noqa: F401  — puts src/ on the import path
from scholion import net

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("src", "tests")

#: Exempt by name, with the reason in this module's docstring. A path, not a
#: bare function name: a second `_unverified` elsewhere is a new question, not
#: an answered one.
EXEMPT = {("src/scholion/net.py", "_unverified")}

#: What counts as saying so out loud.
GATES = {"certificate_fallback", "insecure_allowed", "SCHOLION_TLS_INSECURE", "insecure"}


def _disables_verification(node: ast.AST) -> bool:
    """One statement that takes verification off, in any of its three spellings."""
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        return name == "_create_unverified_context"
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr == "verify_mode":
                v = node.value
                if isinstance(v, ast.Attribute) and v.attr == "CERT_NONE":
                    return True
            if target.attr == "check_hostname":
                v = node.value
                if isinstance(v, ast.Constant) and v.value is False:
                    return True
    return False


def _consults_a_gate(scope: ast.AST) -> bool:
    """Does this scope ask anybody's permission, by any of the accepted names?"""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = scope.args
        for a in (list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs)):
            if a.arg in GATES:
                return True
    for node in ast.walk(scope):
        if isinstance(node, ast.Name) and node.id in GATES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in GATES:
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and "SCHOLION_TLS_INSECURE" in node.value:
            return True
    return False


def _owning_scope(tree: ast.AST, node: ast.AST):
    """The innermost function containing `node`, or the module itself.

    Innermost, not first: a nested helper is where the decision actually lives,
    and reporting the outer function would name a scope that may well hold the
    gate while the inner one does not.
    """
    owner = None
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(n is node for n in ast.walk(fn)):
            if owner is None or fn.lineno > owner.lineno:
                owner = fn
    return (owner or tree), (owner.name if owner else None)


class TestVerificationIsDroppedOnlyWithPermission(unittest.TestCase):

    def test_no_file_decides_on_its_own(self):
        bad, seen = [], 0
        for base in SCANNED:
            for p in sorted((ROOT / base).rglob("*.py")):
                if "__pycache__" in p.parts:
                    continue
                try:
                    tree = ast.parse(p.read_text(encoding="utf-8"))
                except SyntaxError:                          # pragma: no cover
                    continue
                rel = p.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if not _disables_verification(node):
                        continue
                    seen += 1
                    scope, fname = _owning_scope(tree, node)
                    if (rel, fname) in EXEMPT:
                        continue
                    if not _consults_a_gate(scope):
                        bad.append(f"{rel}:{node.lineno} in {fname or '<module>'}()")
        self.assertEqual([], bad,
                         "these switch off certificate verification without asking anybody: "
                         + ", ".join(bad))
        self.assertGreater(seen, 0,
                           "not one place that disables verification was found — the walk is "
                           "scanning nothing, and a clean result produced by a broken scan is "
                           "the failure this file exists to prevent")

    def test_the_exemption_is_still_about_something_real(self):
        """An exemption for a function that no longer exists is a hole with a
        polite name on it."""
        for rel, fname in EXEMPT:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            names = {n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            self.assertIn(fname, names, f"{rel} no longer has {fname}() — remove the exemption")

    def test_the_rule_can_fire(self):
        """The shape this file was written against, verbatim in its essentials.

        A rule that cannot report a violation reports none, which reads exactly
        like compliance.
        """
        offender = ("import ssl, urllib.request\n"
                    "def _download(req):\n"
                    "    try:\n"
                    "        return urllib.request.urlopen(req).read()\n"
                    "    except Exception as e:\n"
                    "        if 'SSL' not in str(e).upper():\n"
                    "            raise\n"
                    "        ctx = ssl._create_unverified_context()\n"
                    "        return urllib.request.urlopen(req, context=ctx).read()\n")
        repaired = ("import urllib.request\n"
                    "from scholion import net\n"
                    "def _download(req):\n"
                    "    try:\n"
                    "        return urllib.request.urlopen(req).read()\n"
                    "    except Exception as e:\n"
                    "        ctx = net.certificate_fallback(e)\n"
                    "        return urllib.request.urlopen(req, context=ctx).read()\n")
        tree = ast.parse(offender)
        hits = [n for n in ast.walk(tree) if _disables_verification(n)]
        self.assertEqual(1, len(hits), "the detector no longer sees the original defect")
        scope, name = _owning_scope(tree, hits[0])
        self.assertEqual("_download", name)
        self.assertFalse(_consults_a_gate(scope), "the offender passed — the gate check is too loose")

        tree = ast.parse(repaired)
        self.assertEqual([], [n for n in ast.walk(tree) if _disables_verification(n)])
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        self.assertTrue(_consults_a_gate(fn), "the repaired shape is not recognised as gated")

    def test_a_flag_off_by_default_counts_and_an_error_message_does_not(self):
        """`verify_evogen.py` asks with `--insecure`, which is louder than an
        environment variable and off unless typed. The old scripts asked the
        exception how it felt. Both must be classified correctly, or the rule is
        either useless or unusable."""
        by_flag = ast.parse("def resolve(rsids, insecure=False):\n"
                            "    if insecure:\n"
                            "        ctx.verify_mode = ssl.CERT_NONE\n")
        by_text = ast.parse("def resolve(rsids, e):\n"
                            "    if 'CERTIFICATE' in str(e).upper():\n"
                            "        ctx.verify_mode = ssl.CERT_NONE\n")
        for tree, expected in ((by_flag, True), (by_text, False)):
            fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            self.assertTrue(any(_disables_verification(n) for n in ast.walk(fn)))
            self.assertEqual(expected, _consults_a_gate(fn))


class _Env:
    """Set environment variables for the length of a block, restore after."""

    def __init__(self, **kw):
        self.kw = kw
        self.old = {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestTheSharedFallbackItself(unittest.TestCase):
    """`certificate_fallback` is what the build scripts now depend on, so it is
    tested directly rather than only through `_open`."""

    CERT = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

    def test_without_permission_it_refuses_and_says_how(self):
        with _Env(SCHOLION_TLS_INSECURE=None):
            with self.assertRaises(RuntimeError) as caught:
                net.certificate_fallback(self.CERT)
        self.assertIn("SCHOLION_TLS_INSECURE", str(caught.exception),
                      "the refusal does not say how to allow this deliberately")

    def test_with_permission_it_hands_back_a_context_and_announces_it(self):
        with _Env(SCHOLION_TLS_INSECURE="1"):
            buf = io.StringIO()
            with redirect_stderr(buf):
                ctx = net.certificate_fallback(self.CERT)
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ssl.CERT_NONE, ctx.verify_mode, "the context still verifies — "
                                                         "the escape hatch does not do what it says")
        self.assertIn("SCHOLION_TLS_INSECURE", buf.getvalue(),
                      "it kept quiet, which is what makes an insecure mode dangerous")

    def test_anything_that_is_not_a_certificate_failure_comes_straight_back(self):
        for err in (TimeoutError("timed out"),
                    urllib.error.URLError("name resolution failed"),
                    urllib.error.URLError("SSL: WRONG_VERSION_NUMBER"),
                    urllib.error.HTTPError("u", 500, "boom", {}, None)):
            with self.subTest(error=str(err)):
                with _Env(SCHOLION_TLS_INSECURE="1"):
                    with self.assertRaises(type(err)):
                        net.certificate_fallback(err)

    def test_a_message_that_merely_mentions_ssl_is_not_a_certificate_failure(self):
        """The exact discrimination the two build scripts could not make. Their
        test was `"SSL" in str(e).upper()`, and this error passes it."""
        protocol_error = urllib.error.URLError("[SSL: WRONG_VERSION_NUMBER] wrong version number")
        self.assertFalse(net._is_cert_error(protocol_error))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
