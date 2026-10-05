"""C4, C5 and C6 of the 0.6.0 brief: the agent's faces and the container.

C4 — a conversation is fixed to the container that was active when it began
(R2). A model's context is a cache nothing can clear, so after `use B` it is
not cleared, it is refused: every tool answers «the patient changed — start a
new conversation», names both IDs, and carries nothing of B.

C5 — every answer names its container: the text of each of the 39 tools ends
with the ID, a structured answer carries `container: {id}`, and so does every
dict the command line prints with --json (the skill that reads the command
line where no tool server runs).

C6 — the label never reaches a model. A clinic may label a container; the
label is printed by the command line and the local page on the same machine,
and nowhere a model reads, because everything a tool returns goes to the
model's provider.
"""
from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import support
from scholion import container, demo, mcp_server, ouroboros_tools

A, B = "p-aaaaaa", "p-bbbbbb"
LABEL = "LABEL-7Q2-MUST-NOT-LEAK"

#: Arguments for the tools that need one; the four that write a person's words
#: or files are left out of the sweep, and each is covered by its own test.
ARGS = {"sch_check_drug_gene": {"drug": "omeprazole"},
        "sch_check_prescription": {"drug": "Levothyroxine"},
        "sch_system": {"key": "thyroid"}}
WRITERS = {"sch_ingest_labs", "sch_lab_draw", "sch_marker_propose", "sch_focus_log"}


def _second(files):
    files = copy.deepcopy(files)
    files["medications.json"]["medications"] = [
        {"name": "Metformin", "dose": "500 mg", "status": "active"}]
    return files


class _Two(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="pinned_")).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        files = demo.build_all()
        self.addCleanup(support.workstation(self.base, {A: files, B: _second(files)}))
        rec = json.loads((self.base / "patients" / A / "container.json").read_text(encoding="utf-8"))
        rec["label"] = LABEL
        (self.base / "patients" / A / "container.json").write_text(json.dumps(rec), encoding="utf-8")

    def rpc(self, method, params=None, session=None, mid=1):
        return mcp_server.handle({"jsonrpc": "2.0", "id": mid, "method": method,
                                  "params": params or {}}, session)

    def call(self, name, session, args=None, version="2025-06-18"):
        return self.rpc("tools/call", {"name": name, "arguments": args or ARGS.get(name, {})},
                        session)["result"]


class TestC4TheConversationIsPinned(_Two):

    def test_a_switch_refuses_every_tool_with_both_ids_and_no_new_data(self):
        s = mcp_server.Session()
        self.rpc("initialize", {"protocolVersion": "2025-06-18"}, s)
        first = self.call("sch_medications", s)
        self.assertFalse(first["isError"])
        self.assertIn("Levothyroxine", first["content"][0]["text"])
        container.use(B)
        for name in ("sch_medications", "sch_overview", "sch_rules", "sch_version"):
            with self.subTest(tool=name):
                r = self.call(name, s)
                text = r["content"][0]["text"]
                self.assertTrue(r["isError"], f"{name} answered after the patient changed")
                self.assertIn(A, text)
                self.assertIn(B, text)
                self.assertNotIn("Metformin", text, "the refusal carried the new person's data")

    def test_a_new_conversation_reads_the_new_person(self):
        s = mcp_server.Session()
        self.rpc("initialize", {"protocolVersion": "2025-06-18"}, s)
        container.use(B)
        ouroboros_tools.unpin_session()           # the person started a new conversation
        s2 = mcp_server.Session()
        self.rpc("initialize", {"protocolVersion": "2025-06-18"}, s2)
        r = self.call("sch_medications", s2)
        self.assertFalse(r["isError"])
        self.assertIn("Metformin", r["content"][0]["text"])

    def test_a_conversation_with_no_handshake_is_pinned_at_its_first_call(self):
        self.call("sch_medications", None)
        container.use(B)
        self.assertTrue(self.call("sch_medications", None)["isError"])

    def test_a_write_from_a_pinned_conversation_cannot_land_in_the_new_person(self):
        """The gate holds the pin, not the active container: a switch between the
        check and the write is refused by the write itself."""
        from scholion import store
        ouroboros_tools.pin_session()
        before = (self.base / "patients" / B / "profile" / "medications.json").read_text(encoding="utf-8")
        with container.pinned(ouroboros_tools._pin().check()):
            container.use(B)
            with self.assertRaises(container.ContainerError):
                store.add_medication("Atorvastatin", "10 mg", subject="owner")
        self.assertEqual(before, (self.base / "patients" / B / "profile" / "medications.json").read_text(encoding="utf-8"))


class TestC5EveryAnswerNamesItsContainer(_Two):

    def test_every_tool_ends_with_the_id_and_a_structure_carries_it(self):
        s = mcp_server.Session()
        self.rpc("initialize", {"protocolVersion": "2025-06-18"}, s)
        names = [t["name"] for t in self.rpc("tools/list", {}, s)["result"]["tools"]]
        self.assertEqual(39, len(names))
        for name in names:
            if name in WRITERS:
                continue
            with self.subTest(tool=name):
                r = self.call(name, s)
                self.assertFalse(r["isError"], r["content"][0]["text"][:300])
                self.assertIn(f"{A}.", r["content"][0]["text"].rstrip().splitlines()[-1])
                if "structuredContent" in r:
                    self.assertEqual({"id": A}, r["structuredContent"]["container"])

    def test_the_command_line_json_carries_it(self):
        from scholion import cli
        for argv in (["overview", "--json"], ["medications", "--json"], ["labs", "--json"]):
            with self.subTest(argv=argv):
                out = io.StringIO()
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    self.assertEqual(0, cli.main(argv))
                self.assertEqual({"id": A}, json.loads(out.getvalue())["container"])


class TestC6TheLabelNeverReachesAModel(_Two):

    def test_no_tool_answer_and_no_handshake_carries_the_label(self):
        s = mcp_server.Session()
        seen = [json.dumps(self.rpc("initialize", {"protocolVersion": "2025-06-18"}, s)),
                json.dumps(self.rpc("tools/list", {}, s))]
        for t in ouroboros_tools.get_tools():
            if t.name in WRITERS:
                continue
            seen.append(json.dumps(self.call(t.name, s), ensure_ascii=False))
        leaked = [x[:120] for x in seen if LABEL in x]
        self.assertEqual([], leaked)

    def test_the_label_is_still_printed_where_the_person_is(self):
        self.assertEqual(LABEL, container.listing()["containers"][0]["label"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
