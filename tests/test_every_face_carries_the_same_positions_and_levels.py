"""C20, C21 and C22 of the 0.6.0 brief: one data layer, every face, and what a
level below B may and may not say.

U2 (owner, 27.09.2026): an assistant receives everything the data holds, the
hypotheses at C and D included, and every face is in step. The difference is
only in the showing — the person's own screen counts the hypotheses, the
clinician's shows each passport, the assistant gets the passport and the rule
for retelling it.

C20 — the set of positions and their levels is the same on the page's API,
      the command line's --json, the MCP tool and the Ouroboros tool, in
      both registers.
C21 — every C and D position carries its level and a passport, a model reads
      every passport in the tool's answer, and the retelling rule is in the
      canon `sch_rules` hands out.
C22 — at E there is no statement on any face: a value, «no source», nothing
      else.

Held on the demo with three positions read from the profile: a C (ADRB1
Arg389), a D (DIO1) and an E (AGT M235T), each one copy.
"""
from __future__ import annotations

import io
import json
import shutil
import socket
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import support
from scholion import cli, demo, engine, mcp_server, ouroboros_tools
from scholion.i18n import t

READ = {"rs1801253": ("ADRB1", "G/C"), "rs2294512": ("DIO1", "G/A"), "rs699": ("AGT", "A/G")}
SYSTEMS = ("cardio", "thyroid", "behaviour")


class _Read(unittest.TestCase):

    def setUp(self):
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)

    @classmethod
    def setUpClass(cls):
        root = Path(tempfile.mkdtemp(prefix="levels_")).resolve()
        cls._root = root
        (root / "profile").mkdir()
        files = demo.build_all()
        files["pharmacogenomics.json"]["genotypes"] += [
            {"gene": g, "rsid": rs, "genotype": gt, "source": "test"} for rs, (g, gt) in READ.items()]
        for name, data in files.items():
            (root / "profile" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        cls._restore = support.pin_profile(root / "profile")

    @classmethod
    def tearDownClass(cls):
        cls._restore()
        shutil.rmtree(cls._root, True)

    @staticmethod
    def index(positions):
        return sorted((p.get("rsid"), p.get("level")) for p in positions or [])


class TestC20OneLayerOnEveryFace(_Read):

    def cli_card(self, key, reg):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(0, cli.main(["system", key, "--register", reg, "--json"]))
        return json.loads(out.getvalue())

    def web_card(self, key, reg):
        from scholion import server
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        srv = server._Server(("127.0.0.1", port), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/system?key={key}&register={reg}",
                                         headers={"Host": f"127.0.0.1:{port}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        finally:
            srv.shutdown()
            srv.server_close()

    def test_the_positions_and_levels_agree_on_every_face_and_in_both_registers(self):
        for key in SYSTEMS:
            core_idx = self.index(engine.system(key, "clinician")["genetics"]["positions"])
            self.assertTrue(core_idx)
            for reg in ("patient", "clinician"):
                with self.subTest(system=key, register=reg):
                    for face, card in (("engine", engine.system(key, reg)),
                                       ("cli", self.cli_card(key, reg)),
                                       ("web", self.web_card(key, reg))):
                        self.assertEqual(core_idx, self.index(card["genetics"]["positions"]), face)

    def test_the_tool_text_names_every_position_below_b(self):
        """The two tool faces print text, and a model reads all of it: every C–E
        position is named there, in the person's register as well."""
        for key in SYSTEMS:
            below = [p for p in engine.system(key, "clinician")["genetics"]["positions"]
                     if p.get("level") in ("C", "D", "E") and p.get("rsid") in READ]
            text = ouroboros_tools._h_system(ouroboros_tools.ToolContext(), key=key)
            mcp = mcp_server.call_tool("sch_system", {"key": key})["content"][0]["text"]
            for p in below:
                with self.subTest(system=key, rsid=p["rsid"]):
                    self.assertIn(p["rsid"], text)
                    self.assertIn(p["rsid"], mcp)


class TestC21AHypothesisTravelsWithItsPassport(_Read):

    def test_every_c_and_d_position_carries_a_passport_and_no_conclusion(self):
        seen = set()
        for key in SYSTEMS:
            for p in engine.system(key, "clinician")["genetics"]["positions"]:
                if p.get("level") not in ("C", "D"):
                    self.assertIsNone(p.get("passport"), p.get("rsid"))
                    continue
                seen.add(p["level"])
                with self.subTest(rsid=p["rsid"]):
                    pp = p["passport"]
                    self.assertEqual(p["level"], pp["level"])
                    self.assertTrue(pp["source"], "a passport without a source")
                    self.assertIsInstance(pp["missing"], list)
                    if p.get("state") in ("het", "hom"):
                        self.assertIsNone(p.get("text"), "a hypothesis printed as a conclusion")
        self.assertEqual({"C", "D"}, seen)

    def test_the_read_hypothesis_carries_what_is_reported_for_this_genotype(self):
        adrb1 = next(p for p in engine.system("cardio", "clinician")["genetics"]["positions"]
                     if p["rsid"] == "rs1801253")
        self.assertEqual("het", adrb1["state"])
        self.assertIn("Arg389", adrb1["passport"]["reported"])

    def test_the_tool_hands_the_passport_and_the_rule_in_the_persons_register(self):
        text = ouroboros_tools._h_system(ouroboros_tools.ToolContext(), key="cardio")
        self.assertIn("Arg389", text, "the model was not told what the hypothesis says")
        self.assertIn(t("system.hyp.rule"), text)

    def test_the_persons_register_counts_and_the_clinicians_shows(self):
        from scholion import format as fmt
        patient = fmt.system_report(engine.system("cardio", "patient"))
        clinician = fmt.system_report(engine.system("cardio", "clinician"))
        self.assertNotIn("Arg389", patient, "the person's screen printed a hypothesis")
        self.assertIn("Arg389", clinician)
        for key in SYSTEMS:
            original = engine.system(key, "patient")
            before = json.dumps(original, sort_keys=True)
            rendered = fmt.system_report(original)
            lower = [p for p in original["genetics"]["positions"] if p.get("level") in ("C", "D", "E")]
            self.assertTrue(lower)
            for position in lower:
                self.assertNotIn(position["rsid"], rendered, "patient output must count, not enumerate lower levels")
            self.assertEqual(before, json.dumps(original, sort_keys=True), "presentation changed the data contract")

    def test_the_retelling_rule_is_in_the_canon_the_tool_hands_out(self):
        rules = ouroboros_tools._h_rules_or_levels(ouroboros_tools.ToolContext())
        self.assertIn("**2c. A hypothesis is retold as a hypothesis", rules)


class TestC22AtENothingIsSaid(_Read):

    def test_e_is_a_value_on_every_face(self):
        agt = next(p for p in engine.system("cardio", "clinician")["genetics"]["positions"]
                   if p["rsid"] == "rs699")
        self.assertEqual(("E", "het", True), (agt["level"], agt["state"], agt["value_only"]))
        self.assertIsNone(agt["text"])
        self.assertIsNone(agt["passport"])
        text = ouroboros_tools._h_system(ouroboros_tools.ToolContext(), key="cardio",
                                         register="clinician")
        line = next(ln for ln in text.splitlines() if "rs699 — level E:" in ln)
        self.assertIn("A/G", line)
        row = next(r for r in engine.system("cardio", "clinician")["genetics"]["rows"]
                   if r.get("rsid") == "rs699")
        self.assertFalse(row["pending"], "a value at E waits for no phrase")

    def test_no_position_at_e_carries_a_sentence_anywhere_in_the_catalogue(self):
        for s in engine.systems()["systems"]:
            for p in engine.system(s["key"], "clinician").get("genetics", {}).get("positions") or []:
                if p.get("level") == "E" and p.get("state") in ("het", "hom", "hemi"):
                    with self.subTest(rsid=p.get("rsid")):
                        self.assertIsNone(p.get("text"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
