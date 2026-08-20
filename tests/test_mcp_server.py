"""The server side of MCP: the same tools, spoken to a model directly.

The project had the client half already — `prs.py` drives an external MCP server
— so the framing and the handshake were proven before this existed. What is
tested here is the dialogue and, more importantly, the DERIVATION: the tool list
is not written down twice. A tool the plugin registers is served over MCP the
same day, and one it drops disappears from both. Two descriptions of one
capability always diverge, and this project has an entire contract layer built on
that observation.

The transport is exercised without a subprocess, by handing `serve()` an iterator
and a buffer. What is worth testing is the conversation, not the pipe.
"""
from __future__ import annotations

import io
import json
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import mcp_server, ouroboros_tools


def talk(*messages):
    out = io.StringIO()
    mcp_server.serve(iter(json.dumps(m) + "\n" for m in messages), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


class TestTheHandshake(unittest.TestCase):

    def test_initialize_states_a_protocol_version(self):
        (answer,) = talk({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(answer["id"], 1)
        self.assertEqual(answer["result"]["protocolVersion"], mcp_server.PROTOCOL_VERSION)
        self.assertIn("tools", answer["result"]["capabilities"])
        self.assertEqual(answer["result"]["serverInfo"]["name"], "scholion")

    def test_a_notification_gets_no_answer(self):
        self.assertEqual(talk({"jsonrpc": "2.0", "method": "notifications/initialized"}), [])

    def test_an_unknown_method_is_refused_rather_than_ignored(self):
        (answer,) = talk({"jsonrpc": "2.0", "id": 9, "method": "tools/invent"})
        self.assertEqual(answer["error"]["code"], mcp_server.METHOD_NOT_FOUND)

    def test_a_broken_line_does_not_end_the_session(self):
        out = io.StringIO()
        mcp_server.serve(iter(["{not json\n",
                               json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"]),
                         out)
        answers = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(answers[0]["error"]["code"], mcp_server.PARSE_ERROR)
        self.assertEqual(answers[1]["id"], 2, "one bad frame must not take the session with it")


class TestTheToolListIsDerived(unittest.TestCase):

    def test_it_is_exactly_the_plugin_list(self):
        served = {t["name"] for t in mcp_server.tool_descriptors()}
        plugin = {t.name for t in ouroboros_tools.get_tools()}
        self.assertEqual(served, plugin,
                         "two lists of one capability diverge — that is why this one is derived")

    def test_every_tool_carries_a_description_and_an_input_schema(self):
        for t in mcp_server.tool_descriptors():
            with self.subTest(tool=t["name"]):
                self.assertTrue(t["description"].strip())
                self.assertEqual(t["inputSchema"].get("type"), "object")

    def test_tools_list_answers_over_the_wire(self):
        (answer,) = talk({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        self.assertTrue(answer["result"]["tools"])


class TestCallingATool(unittest.TestCase):

    def test_an_unknown_tool_is_an_error_not_an_empty_answer(self):
        res = mcp_server.call_tool("sch_not_a_tool", {})
        self.assertTrue(res["isError"])
        self.assertIn("unknown tool", res["content"][0]["text"])

    def test_a_bad_argument_reports_what_went_wrong(self):
        name = mcp_server.tool_descriptors()[0]["name"]
        res = mcp_server.call_tool(name, {"no_such_parameter": 1})
        self.assertTrue(res["isError"])
        self.assertTrue(res["content"][0]["text"].strip(),
                        "«nothing came back» and «this went wrong» are different facts")

    def test_a_real_call_answers_with_text(self):
        res = mcp_server.call_tool("sch_check_drug_gene", {"drug": "clopidogrel"})
        self.assertFalse(res["isError"], res["content"][0]["text"][:200])
        self.assertIn("CYP2C19", res["content"][0]["text"])

    def test_tools_call_without_a_name_is_an_invalid_request(self):
        (answer,) = talk({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {}})
        self.assertEqual(answer["error"]["code"], mcp_server.INVALID_PARAMS)


class TestItServesNoWriterThatAuthors(unittest.TestCase):

    def test_no_tool_creates_a_value_from_nobody_s_document(self):
        """The plugin's rule, inherited rather than restated — and checked here too."""
        from scholion import contract
        served = {t["name"] for t in mcp_server.tool_descriptors()}
        for command in contract.AUTHORS:
            with self.subTest(command=command):
                self.assertNotIn(f"sch_{command.replace('-', '_')}", served)


if __name__ == "__main__":
    unittest.main()
