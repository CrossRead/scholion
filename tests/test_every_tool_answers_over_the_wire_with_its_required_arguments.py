"""Every tool answers over MCP when called with its required arguments — none with a TypeError.

The cross-face audit of 12.09.2026 found three tools that no host could call:
`sch_focus_log`, `sch_lab_draw` and `sch_marker_propose` read their arguments
off `ctx.args`, while the MCP server and the Hub call `handler(ctx, **args)`.
The one write a model was given had answered every MCP call with a TypeError
since it landed, and the test that covered it filled `ctx.args` by hand. The
suite also accepted a raw «⟦tool.x.description⟧» as a description, so five
tools were served with no description in either language.

Here the whole plugin list goes over the wire with the arguments its schema
declares required, on a throw-away copy of the fixture profile; a refusal in
words is a pass, an `isError` is not.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import mcp_server, ouroboros_tools

#: A minimal valid argument for every required parameter the schemas declare.
ARG = {"drug": "clopidogrel", "folder": "", "day": "2026-01-01",
       "key": "audit_key", "names": "audit name", "date": "2026-01-02"}


class TestEveryToolAnswers(unittest.TestCase):

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="wire_"))
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(support.FIXTURE_PROFILE, root / "profile")
        self.addCleanup(support.pin_profile(root / "profile"))
        self.addCleanup(support.pin_cache(root / "cache"))
        # `sch_marker_propose` writes the marker overlay beside the REPOSITORY
        # (`core.knowledge_dir_local`, task 177), so the repo root is pinned
        # too — without it the first run of this test left `audit_key` in the
        # source tree, and every later run from the tree carried that marker.
        old_repo = os.environ.get("SCHOLION_REPO_DIR")
        os.environ["SCHOLION_REPO_DIR"] = str(root)
        self.addCleanup(lambda: os.environ.update({"SCHOLION_REPO_DIR": old_repo})
                        if old_repo is not None else os.environ.pop("SCHOLION_REPO_DIR", None))
        (root / "empty").mkdir()
        self.empty = root / "empty"

    def test_no_tool_answers_a_call_with_an_error_of_the_calling_convention(self):
        for name, params, required, handler in ouroboros_tools._TOOLS:
            args = {p: (str(self.empty) if p == "folder" else ARG[p]) for p in required}
            with self.subTest(tool=name, args=args):
                out = mcp_server.call_tool(name, args)
                text = "".join(c.get("text", "") for c in out.get("content") or [])
                self.assertFalse(out.get("isError"), f"{name}: {text[:200]}")
                self.assertNotIn("unexpected keyword argument", text)
                self.assertNotIn("has no attribute 'args'", text)
                self.assertTrue(text.strip(), f"{name} answered with nothing")

    def test_a_tool_called_with_no_arguments_at_all_refuses_in_words(self):
        """The shape a host produces when the model omits everything."""
        for name, params, required, handler in ouroboros_tools._TOOLS:
            with self.subTest(tool=name):
                out = mcp_server.call_tool(name, {})
                text = "".join(c.get("text", "") for c in out.get("content") or [])
                self.assertFalse(out.get("isError"), f"{name}: {text[:200]}")
                self.assertNotIn("unexpected keyword argument", text)
                self.assertNotIn("has no attribute 'args'", text)
                self.assertNotIn("Traceback", text)

    def test_the_ingest_tool_never_reads_the_working_directory(self):
        out = mcp_server.call_tool("sch_ingest_labs", {"folder": ""})
        text = "".join(c.get("text", "") for c in out.get("content") or [])
        self.assertIn("no folder was named", text)


class TestEveryToolIsDescribedInBothLanguages(unittest.TestCase):

    def test_no_description_or_parameter_is_a_raw_key(self):
        for code in ("en", "ru"):
            with _Lang(code):
                for t in mcp_server.tool_descriptors():
                    with self.subTest(lang=code, tool=t["name"]):
                        self.assertNotIn("⟦", t["description"], t["description"][:80])
                        for pname, prop in (t["inputSchema"].get("properties") or {}).items():
                            self.assertNotIn("⟦", prop.get("description", ""), f"{t['name']}.{pname}")


class _Lang:
    """Set the catalogue language for the block, and put it back."""

    def __init__(self, code):
        self.code = code

    def __enter__(self):
        import os
        self.old = os.environ.get("SCHOLION_LANG")
        os.environ["SCHOLION_LANG"] = self.code
        return self

    def __exit__(self, *a):
        import os
        if self.old is None:
            os.environ.pop("SCHOLION_LANG", None)
        else:
            os.environ["SCHOLION_LANG"] = self.old


if __name__ == "__main__":
    unittest.main()
