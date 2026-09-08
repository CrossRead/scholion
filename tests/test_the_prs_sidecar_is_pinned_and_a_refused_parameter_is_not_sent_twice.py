"""The PRS sidecar is started with its dependency resolution pinned, a refusal
names its cause, and a parameter the server refused once is not offered again.

Task 129: `just-prs-mcp@0.1.3` declares `fastmcp[tasks]>=3.4.2` with no upper
bound; resolved freely on a fresh cache it took fastmcp 4.x and died at start-up,
and the whole polygenic layer with it — seen on 05.09.2026. The application now
launches `uvx` with UV_CONSTRAINT pointing at a file written from
`prs.PRS_CONSTRAINTS`; the shell path uses `src/ingest/prs_constraints.txt`. The
two copies are held together here, because a pin that exists in one launcher
and not the other protects only the launcher somebody happened to use.

Task 131a: `profile` and `include_children` are not accepted by 0.1.3. They used
to be sent with every trait, refused with every trait, and every call went
twice. A refusal is now remembered for the rest of the run.
"""
from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import net, prs


class _FakeProcess:
    """Enough of a Popen for `_MCP.__init__` to complete: answers `initialize`."""

    def __init__(self, lines=None):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("" if lines is None else "".join(lines))
        self.returncode = 3

    def poll(self):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return self.returncode


def _fake_popen(record):
    def popen(args, **kw):
        record["args"] = list(args)
        record["env"] = dict(kw.get("env") or {})
        return _FakeProcess(['{"jsonrpc": "2.0", "id": 1, "result": {}}\n'])
    return popen


class TestTheLaunchCarriesTheConstraint(unittest.TestCase):

    def setUp(self):
        self._restore = support.pin_profile(support.ROOT / "tests" / "fixtures" / "profile")
        self._had = os.environ.pop("UV_CONSTRAINT", None)

    def tearDown(self):
        if self._had is not None:
            os.environ["UV_CONSTRAINT"] = self._had
        self._restore()

    def test_uvx_is_started_with_uv_constraint_pointing_at_the_pin(self):
        record = {}
        with mock.patch.object(net, "offline", return_value=False), \
                mock.patch.object(prs.subprocess, "Popen", _fake_popen(record)):
            m = prs._MCP()
            m.close()
        self.assertEqual(["uvx", prs.PKG, "stdio"], record["args"][:3])
        self.assertIn("UV_CONSTRAINT", record["env"],
                      "the sidecar was started with its resolution unpinned — a fresh "
                      "uvx cache will take a fastmcp the server was not written for")
        pinned = Path(record["env"]["UV_CONSTRAINT"])
        self.assertTrue(pinned.is_file())
        lines = [ln.strip() for ln in pinned.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
        self.assertEqual(list(prs.PRS_CONSTRAINTS), lines)

    def test_an_owners_own_constraint_file_is_kept(self):
        record = {}
        os.environ["UV_CONSTRAINT"] = "/somewhere/the-owners-own.txt"
        with mock.patch.object(net, "offline", return_value=False), \
                mock.patch.object(prs.subprocess, "Popen", _fake_popen(record)):
            prs._MCP().close()
        self.assertEqual("/somewhere/the-owners-own.txt", record["env"]["UV_CONSTRAINT"])


class TestTheShellCopyAgreesWithTheCode(unittest.TestCase):

    def test_prs_constraints_txt_carries_exactly_the_same_pins(self):
        txt = support.ROOT / "src" / "ingest" / "prs_constraints.txt"
        if not txt.exists():
            self.skipTest("src/ingest is not part of this build")
        lines = [ln.strip() for ln in txt.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
        self.assertEqual(list(prs.PRS_CONSTRAINTS), lines,
                         "the shell launcher and the application would pin the sidecar "
                         "differently — whichever one is used decides whether it starts")


class TestASilentServerNamesItsCause(unittest.TestCase):

    def test_the_exception_names_the_exit_code_and_the_pin(self):
        m = prs._MCP.__new__(prs._MCP)
        m.p = _FakeProcess([])
        with self.assertRaises(prs.PrsUnavailable) as cm:
            m._read_id(1)
        text = str(cm.exception)
        self.assertIn("3", text)
        for pin in prs.PRS_CONSTRAINTS:
            self.assertIn(pin, text)
        self.assertIn("UV_CONSTRAINT", text)


class TestARefusedParameterIsNotOfferedAgain(unittest.TestCase):

    def test_rejected_keys_are_read_from_the_servers_message(self):
        extra = {"profile": "all", "include_children": True}
        msg = ("Invalid arguments for tool 'compute_prs_by_trait': "
               "unexpected_keyword_argument 'profile'")
        self.assertEqual({"profile"}, prs._rejected_keys(msg, extra))
        self.assertEqual(set(extra), prs._rejected_keys("unexpected keyword", extra),
                         "a refusal that names no key must drop every optional one, "
                         "or the double call continues")

    def test_a_panel_pays_the_refusal_once_not_per_trait(self):
        restore = support.pin_profile(support.ROOT / "tests" / "fixtures" / "profile")
        self.addCleanup(restore)
        calls = []

        class FakeMCP:
            def __init__(self, *a, **k):
                pass

            def call(self, name, args):
                calls.append((name, dict(args)))
                if name == "compute_prs_by_trait" and "profile" in args:
                    raise RuntimeError("Invalid arguments for tool "
                                       "'compute_prs_by_trait': "
                                       "unexpected_keyword_argument 'profile'")
                return {"rows": []}

            def close(self):
                pass

        traits = [{"label": "First", "term": "first", "efo_id": "EFO_0000001"},
                  {"label": "Second", "term": "second", "efo_id": "EFO_0000002"}]
        with tempfile.TemporaryDirectory() as d:
            vcf = Path(d) / "g.vcf.gz"
            vcf.write_bytes(b"")
            with mock.patch.object(prs, "_MCP", FakeMCP):
                res = prs.report(str(vcf), traits=traits, normalize=False,
                                 profile="all", superpopulation="EUR")
        self.assertTrue(res["ok"], res)
        computes = [a for n, a in calls if n == "compute_prs_by_trait"]
        # First trait: offered with `profile`, refused, repeated without it.
        # Second trait: one call, and `profile` is not in it.
        self.assertEqual(3, len(computes),
                         "every trait paid for the refusal again: " + repr(computes))
        self.assertIn("profile", computes[0])
        self.assertNotIn("profile", computes[1])
        self.assertNotIn("profile", computes[2])
        self.assertEqual("EFO_0000002", computes[2]["trait_id"])


if __name__ == "__main__":
    unittest.main()
