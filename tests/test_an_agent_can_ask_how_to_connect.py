"""A product that cannot be asked what it needs will have the answer invented.

An assistant was asked to send something to Scholion, had no Scholion tool in
front of it, and — with no way to say «I cannot reach it from here» — asked its
user for a «Scholion credential»: a thing that does not exist and never has. It
said in the same sentence that it did not know the name of what it was asking
for. That is not a lie; it is what a model does when the honest answer is
missing and a plausible one is available.

The repair is not a paragraph in a README, because the asker was not a person
reading documentation. It is `capabilities()['access']` — every door, what each
one costs, and the fact that there is no key to any of them, in a shape a machine
can read and in numbers derived from the build rather than typed beside it.

These tests hold the two halves apart: that the answer exists and is complete,
and that it is TRUE — the claim «no credentials» is checked against the code
rather than restated.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

import support
from scholion import contract


class TestTheAnswerExists(unittest.TestCase):

    def setUp(self):
        self.access = contract.access()

    def test_authentication_is_the_first_thing_it_answers(self):
        """Because it is the thing that gets invented when unanswered."""
        auth = self.access["auth"]
        self.assertFalse(auth["required"])
        self.assertEqual(auth["kinds_accepted"], [])
        self.assertIn("credential", auth["note"].lower())

    def test_every_door_that_exists_is_named(self):
        doors = self.access["doors"]
        for name in ("cli", "mcp", "ouroboros_tools", "ouroboros_hub", "web"):
            with self.subTest(door=name):
                self.assertIn(name, doors)
                self.assertTrue(doors[name].get("how"), "a door with no way through it")

    def test_the_mcp_door_says_what_kind_of_thing_it_is(self):
        """A host that thinks a local server is remote is where the invented
        credential came from. The answer says «stdio» before it says anything
        else, so that assumption has something to collide with."""
        mcp = self.access["doors"]["mcp"]
        self.assertEqual(mcp["transport"], "stdio")
        self.assertTrue(mcp["protocol"], "no protocol version to negotiate against")
        self.assertIn("no port", mcp["note"])

    def test_it_reaches_the_outside_through_the_command_line(self):
        code, out, err = support.run(["capabilities", "--json"])
        self.assertEqual(code, 0, err[-300:])
        self.assertIn("access", json.loads(out), "the answer exists and cannot be asked for")


class TestTheAnswerIsTrue(unittest.TestCase):
    """The claim is checked against the code, not repeated."""

    def test_no_environment_variable_looks_like_a_secret(self):
        access = contract.access()
        self.assertEqual(access["environment"]["secret_looking"], [],
                         "something here reads like a credential — either it is one, "
                         "and `auth.required` is a lie, or it is misnamed")

    def test_the_variables_are_scanned_and_not_listed_by_hand(self):
        """A hand-written list would outlive the code that reads them.

        `SCHOLION_GENOME_SAMPLE` was added after this answer was written; if the
        scan is real it is there, and if the list is typed it is not.
        """
        reads = contract.access()["environment"]["reads"]
        self.assertIn("SCHOLION_GENOME_SAMPLE", reads)
        self.assertIn("SCHOLION_PROFILE_DIR", reads)

    def test_the_tool_count_is_the_tool_count(self):
        from scholion import ouroboros_tools
        n = len(ouroboros_tools.get_tools())
        doors = contract.access()["doors"]
        self.assertEqual(doors["mcp"]["tools"], n)
        self.assertEqual(doors["ouroboros_tools"]["tools"], n)

    def test_the_server_really_answers_what_the_door_promises(self):
        """The protocol version is quoted to hosts; a wrong one fails a handshake."""
        p = subprocess.run([sys.executable, "-m", "scholion", "mcp"],
                           input='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n',
                           capture_output=True, text=True, timeout=60,
                           cwd=support.ROOT, env=support.env())
        first = json.loads(p.stdout.splitlines()[0])
        self.assertEqual(first["result"]["protocolVersion"],
                         contract.access()["doors"]["mcp"]["protocol"])


class TestWhatTheOuroborosSkillClaims(unittest.TestCase):
    """The skill is read by a host that will never run a command to check it."""

    def skill(self):
        p = support.ROOT / "ouroboros_plugin" / "hub" / "scholion" / "SKILL.md"
        if not p.exists():
            self.skipTest("the Hub skill is not part of this build")
        return p.read_text(encoding="utf-8")

    def test_its_version_is_this_version(self):
        version = (support.ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(f"version: {version}\n", self.skill(),
                      "the skill declares a version this build is not")

    def test_it_counts_the_tools_it_has(self):
        from scholion import ouroboros_tools
        n = len(ouroboros_tools.get_tools())
        text = self.skill()
        self.assertIn(f"{n} tools", text,
                      "the tool count in the description is not the number of tools")

    def test_it_says_there_is_no_key(self):
        """The one sentence that would have prevented the whole episode."""
        text = self.skill().lower()
        self.assertTrue(any(s in text for s in ("no key", "no credential")),
                        "a host reading only this file has no way to know")

    def test_it_names_the_mcp_door(self):
        self.assertIn("scholion mcp", self.skill(),
                      "a surface the product has and its own skill does not mention")


class TestTheServerStaysLocal(unittest.TestCase):
    """A decision, held by something other than memory.

    The protocol has an authorisation mechanism, and it is defined for
    HTTP-based transports: a server reachable over a network is a protected
    resource and needs OAuth. On stdio the specification says the opposite —
    do not use it, take what you need from the environment — because the trust
    boundary is the machine, and whoever started the process already has the
    files.

    That is why this server is stdio and why it has no authentication: not an
    omission, a consequence. The day somebody adds an HTTP transport, the
    boundary moves off the machine and every promise this product makes about
    the data not travelling has to be re-argued. The decision was «do not», and
    a decision without a guard is a wish.
    """

    def test_the_declared_transport_is_stdio(self):
        self.assertEqual(contract.access()["doors"]["mcp"]["transport"], "stdio")

    def test_the_server_opens_nothing(self):
        source = (support.SRC / "scholion" / "mcp_server.py").read_text(encoding="utf-8")
        for marker in ("import socket", "socketserver", "http.server", "HTTPServer",
                       "asyncio.start_server", "uvicorn", "flask", "fastapi",
                       ".bind(", ".listen("):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source,
                                 "the server has grown a network transport — the trust "
                                 "boundary is no longer the machine, and `auth.required: "
                                 "false` stops being true")

    def test_the_page_for_a_person_is_not_offered_as_a_door(self):
        web = contract.access()["doors"]["web"]
        self.assertFalse(web["agent_surface"])
        self.assertEqual(web["binds"], "127.0.0.1")


class TestTheManifestIsWrittenAndNotRemembered(unittest.TestCase):
    """The check is the weaker half; this is the other one.

    A test that catches a hand-typed version tells you it is wrong after you
    have written it wrong, and makes every version bump one more thing to
    remember. `sync_manifest.py` writes the two fields that can be derived, and
    `run_tests.sh` runs it in report mode beside the document and rule checks.
    """

    def test_the_generator_exists_and_agrees_with_the_build(self):
        import importlib.util
        tool = support.ROOT / "src" / "tools" / "sync_manifest.py"
        if not tool.exists():
            self.skipTest("sync_manifest.py is not part of this build")
        spec = importlib.util.spec_from_file_location("sync_manifest", tool)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.main([]), 0, "the manifest and the build disagree")

    def test_it_would_notice_a_wrong_number(self):
        """A gate that cannot fail is worse than no gate."""
        import importlib.util
        tool = support.ROOT / "src" / "tools" / "sync_manifest.py"
        if not tool.exists():
            self.skipTest("sync_manifest.py is not part of this build")
        spec = importlib.util.spec_from_file_location("sync_manifest", tool)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stale = "---\nversion: 0.0.1\ndescription: … 3 tools; …\n---\n"
        fresh = mod.render(stale, "9.9.9", 77)
        self.assertIn("version: 9.9.9", fresh)
        self.assertIn("77 tools", fresh)
        self.assertNotEqual(fresh, stale)


class TestEveryDoorCarriesWhatADoorMustCarry(unittest.TestCase):
    """Enumerated out of `access()`, so a fifth door fails on the day it is added.

    Both defects this file exists for were of one kind: a surface that worked and
    that nothing was obliged to describe. Listing the four we have would repeat
    the mistake in a new place — the list would be right until somebody added a
    fifth. So the doors come from the build, and each is asked the same three
    questions.
    """

    def setUp(self):
        self.doors = contract.access()["doors"]
        guide = support.ROOT / "docs" / "CONNECTING-AN-AGENT.md"
        if not guide.exists():
            guide = support.SRC / "scholion" / "docs" / "connecting-an-agent.md"
        self.guide = guide.read_text(encoding="utf-8") if guide.exists() else ""

    def test_the_guide_names_every_door(self):
        self.assertTrue(self.guide, "the connection guide is not in this build")
        missing = [name for name, door in self.doors.items()
                   if door.get("how", "") not in self.guide]
        self.assertEqual(missing, [], "a way into this product that the guide does "
                                      "not mention — the defect this guide was "
                                      "written for, in a new place")

    def test_every_door_says_who_it_is_for(self):
        """Silence reads as «for you». It was silence that got a local page driven
        by an agent and a local server asked for a token."""
        for name, door in self.doors.items():
            with self.subTest(door=name):
                self.assertIn("how", door)
                if door.get("agent_surface") is False:
                    self.assertTrue(door.get("for"), "marked not-for-agents and "
                                                     "does not say who it IS for")

    def test_the_rules_reach_a_model_that_arrives_through_the_tools(self):
        """The half that is easy to lose.

        Through the skill a model is handed the instruction and the canon. Through
        the tool interface it is handed a list of tools — it learns what it may
        call and nothing about what it must not say. The canon is therefore a tool
        of its own, and this is the check that it stays one.
        """
        from scholion import ouroboros_tools
        names = [e.name for e in ouroboros_tools.get_tools()]
        self.assertIn("sch_rules", names,
                      "no way for a model on the tool interface to reach the rules")
        entry = next(e for e in ouroboros_tools.get_tools() if e.name == "sch_rules")
        text = entry.handler(ouroboros_tools.ToolContext())
        self.assertGreater(len(text), 2000, "the rules came back empty or truncated")
        self.assertIn("precedence", text.lower(),
                      "this does not look like the canon")

    def test_the_handshake_carries_the_boundary_for_hosts_that_pass_it_on(self):
        """The protocol has a field for this. Some clients ignore it, which is a
        reason to have BOTH — the field for those that read it, the tool for the
        rest — not a reason to have neither."""
        from scholion import mcp_server
        answer = mcp_server.handle({"jsonrpc": "2.0", "id": 1,
                                    "method": "initialize", "params": {}})
        instructions = answer["result"].get("instructions", "")
        self.assertTrue(instructions, "the handshake says nothing about what this is")
        low = instructions.lower()
        self.assertIn("not a medical device", low)
        self.assertIn("sch_rules", low)
        self.assertTrue(any(w in low for w in ("no account", "no key", "nothing to authenticate")),
                        "the handshake does not settle the credential question")


if __name__ == "__main__":
    unittest.main()
