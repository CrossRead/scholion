"""The MCP revisions the server claims are the ones it speaks — checked by talking to it.

Until 0.5.3 the server stated `2024-11-05` in a constant, and nothing but the
constant said so. A number that stands in for behaviour drifts from it quietly —
the hub record did exactly that before a guard was written for it. So the claim
is held here by a run, not by a string comparison: `scholion mcp` is started as
a real process once per revision it claims, and asked what that revision obliges
a server to do. A revision added to the list without its behaviour has no check
below and fails the first test; a check that stops holding fails its own.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

import support
from scholion import mcp_server, ouroboros_tools

MODERN = mcp_server.MODERN_VERSIONS[0]
STRUCTURED_TOOL = "sch_overview"


def talk(*messages):
    """Start the server, send the messages as lines, return every answer by id."""
    lines = "".join((m if isinstance(m, str) else json.dumps(m)) + "\n" for m in messages)
    p = subprocess.run([sys.executable, "-m", "scholion", "mcp"], input=lines,
                       cwd=str(support.ROOT), env=support.env(), capture_output=True,
                       text=True, timeout=120)
    answers = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
    return answers


def by_id(answers):
    return {a["id"]: a for a in answers if isinstance(a, dict)}


def rpc(mid, method, params=None, version=None):
    params = dict(params or {})
    if version is not None:
        params["_meta"] = {"io.modelcontextprotocol/protocolVersion": version,
                           "io.modelcontextprotocol/clientCapabilities": {},
                           "io.modelcontextprotocol/clientInfo": {"name": "probe", "version": "1"}}
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params}


def init(version):
    return rpc(1, "initialize", {"protocolVersion": version, "capabilities": {},
                                 "clientInfo": {"name": "probe", "version": "1"}})


class _Revision(unittest.TestCase):

    def assert_tool_list(self, result, structured):
        names = [t["name"] for t in result["tools"]]
        self.assertEqual([t.name for t in ouroboros_tools.get_tools()], names,
                         "the tool list is not in the plugin's fixed order")
        with_schema = sorted(t["name"] for t in result["tools"] if "outputSchema" in t)
        self.assertEqual(sorted(mcp_server.OUTPUT_FIELDS) if structured else [], with_schema)

    def assert_call(self, result, structured):
        self.assertFalse(result["isError"], result)
        self.assertEqual("text", result["content"][0]["type"])
        if not structured:
            self.assertNotIn("structuredContent", result)
            return
        data = result["structuredContent"]
        self.assertIsInstance(data, dict)
        fields = mcp_server.output_schema(STRUCTURED_TOOL)["properties"]
        # The fixture is the profile the contract was taken on, so every listed
        # field is there — the schema promises no more than this run shows.
        self.assertLessEqual(set(fields), set(data))
        # A client that shows a model only the structure still hands it the report.
        self.assertEqual(result["content"][0]["text"], data[mcp_server.REPORT_FIELD])

    def legacy(self, version):
        structured = version >= mcp_server.STRUCTURED_FROM
        a = by_id(talk(init(version), {"jsonrpc": "2.0", "method": "notifications/initialized"},
                       rpc(2, "tools/list"), rpc(3, "tools/call", {"name": STRUCTURED_TOOL}),
                       rpc(4, "ping")))
        self.assertEqual(version, a[1]["result"]["protocolVersion"])
        self.assertIn("sch_rules", a[1]["result"]["instructions"])
        self.assert_tool_list(a[2]["result"], structured)
        self.assert_call(a[3]["result"], structured)
        self.assertEqual({}, a[4]["result"], "ping is part of every handshake revision")
        for answer in a.values():
            self.assertNotIn("resultType", answer.get("result", {}),
                             "a 2026 field in a legacy answer")
        return a

    def batch(self, version):
        answers = talk(init(version), [rpc(2, "ping"), rpc(3, "tools/list")])
        return answers[1]

    def check_2024_11_05(self):
        self.legacy("2024-11-05")
        self.assertEqual(-32600, self.batch("2024-11-05")["error"]["code"])

    def check_2025_03_26(self):
        self.legacy("2025-03-26")
        answer = self.batch("2025-03-26")
        self.assertIsInstance(answer, list, "2025-03-26 obliges a server to receive batches")
        self.assertEqual({2, 3}, {x["id"] for x in answer})

    def check_2025_06_18(self):
        self.legacy("2025-06-18")
        self.assertEqual(-32600, self.batch("2025-06-18")["error"]["code"],
                         "batches were removed in 2025-06-18")

    def check_2025_11_25(self):
        self.legacy("2025-11-25")
        a = by_id(talk(init("2025-11-25"),
                       rpc(2, "tools/call", {"name": "sch_check_drug_gene", "arguments": {"nope": 1}})))
        # Input errors are tool errors from 2025-11-25 on, so a model can correct itself.
        self.assertTrue(a[2]["result"]["isError"])

    def check_2026_07_28(self):
        v = MODERN
        a = by_id(talk(rpc(1, "server/discover", version=v), rpc(2, "tools/list", version=v),
                       rpc(3, "tools/call", {"name": STRUCTURED_TOOL}, version=v),
                       rpc(4, "ping", version=v), rpc(5, "tools/list", version=v),
                       rpc(6, "tools/list", version="1900-01-01"),
                       rpc(7, "initialize", {"protocolVersion": v}, version=v)))
        d = a[1]["result"]
        self.assertEqual(list(mcp_server.SUPPORTED_VERSIONS), d["supportedVersions"])
        self.assertIn("tools", d["capabilities"])
        self.assertIn("sch_rules", d["instructions"])
        for mid in (1, 2, 3, 5):
            r = a[mid]["result"]
            self.assertEqual("complete", r["resultType"], mid)
            self.assertEqual("scholion", r["_meta"]["io.modelcontextprotocol/serverInfo"]["name"])
        for mid in (1, 2):
            self.assertGreaterEqual(a[mid]["result"]["ttlMs"], 0)
            self.assertIn(a[mid]["result"]["cacheScope"], ("public", "private"))
        self.assert_tool_list(a[2]["result"], structured=True)
        self.assertEqual(a[2]["result"]["tools"], a[5]["result"]["tools"])
        self.assert_call(a[3]["result"], structured=True)
        self.assertEqual(-32601, a[4]["error"]["code"], "ping was removed in 2026-07-28")
        err = a[6]["error"]
        self.assertEqual(-32022, err["code"])
        self.assertEqual({"supported": list(mcp_server.SUPPORTED_VERSIONS), "requested": "1900-01-01"},
                         err["data"])
        self.assertIn("error", a[7], "a modern request does not open a handshake")


class TestEveryClaimedRevisionIsSpoken(_Revision):

    def test_every_claimed_revision_has_a_check_and_passes_it(self):
        checks = {name[len("check_"):].replace("_", "-") for name in dir(self) if name.startswith("check_")}
        self.assertEqual(set(mcp_server.SUPPORTED_VERSIONS), checks,
                         "a revision is claimed without a check here, or checked without a claim")
        for version in mcp_server.SUPPORTED_VERSIONS:
            with self.subTest(version=version):
                getattr(self, "check_" + version.replace("-", "_"))()

    def test_an_unknown_handshake_revision_is_answered_with_ours_not_echoed(self):
        a = by_id(talk(init("1999-01-01")))
        self.assertEqual(mcp_server.LEGACY_VERSIONS[0], a[1]["result"]["protocolVersion"])

    def test_a_client_that_skips_the_handshake_is_served_as_before(self):
        a = by_id(talk(rpc(1, "tools/list"), rpc(2, "tools/call", {"name": STRUCTURED_TOOL})))
        self.assert_tool_list(a[1]["result"], structured=False)
        self.assert_call(a[2]["result"], structured=False)

    def test_what_is_not_a_request_is_refused_in_words(self):
        answers = talk("not json", "[]", "7")
        self.assertEqual([-32700, -32600, -32600], [x["error"]["code"] for x in answers])


class TestTheOutputSchemaIsTheContract(unittest.TestCase):

    def test_the_listed_fields_are_the_contracts_own(self):
        base = json.loads((support.ROOT / "tests" / "contracts" / "public_contract.json")
                          .read_text(encoding="utf-8"))["json_fields"]
        for tool, command in mcp_server.OUTPUT_FIELDS.items():
            with self.subTest(tool=tool):
                listed = set(mcp_server.output_schema(tool)["properties"]) - {mcp_server.REPORT_FIELD}
                self.assertEqual(sorted(base[command]), sorted(listed))
                self.assertNotIn(mcp_server.REPORT_FIELD, base[command], "the report field would hide a real one")

    def test_a_structured_tool_is_the_command_the_contract_names(self):
        from scholion import contract
        for tool, command in mcp_server.OUTPUT_FIELDS.items():
            self.assertEqual(tool, contract.PLUGIN.get(command), command)

    def test_every_structured_tool_can_hand_back_its_structure(self):
        handlers = {t.name: t.handler for t in ouroboros_tools.get_tools()}
        for tool in mcp_server.OUTPUT_FIELDS:
            self.assertTrue(hasattr(handlers[tool], "both"), tool)

    def test_a_non_object_structure_is_wrapped_not_dropped(self):
        from unittest import mock
        with mock.patch.object(ouroboros_tools.engine, "overview", return_value=[1, 2]), \
                mock.patch.object(ouroboros_tools.fmt, "overview_report", return_value="two"):
            r = mcp_server.call_tool(STRUCTURED_TOOL, {}, MODERN)
        self.assertEqual({"value": [1, 2], "report": "two"}, r["structuredContent"])


if __name__ == "__main__":
    unittest.main()
