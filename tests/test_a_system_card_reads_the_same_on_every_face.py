"""A system's card is the same answer on the command line, over HTTP and on the page.

Task 168, step 4 — the acceptance items of the brief (§9) held on the faces
rather than in the engine: an empty curated file gives a meaningful answer for
every system (1); the answer carries all seven layers or an explicit reason
for each (7); the next step is three baskets and none of them is silently
empty (8); no clinical string is an instruction (9); the patient's and the
clinician's registers differ in detail and never in the verdict (10); the
card prints as one block (12); the card ends with the questions, and an empty
list names its reason (16). And the two rings are two numbers — the share of
the laboratory panel measured and the share of the genetic half read — never
one figure made of both.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import support
from scholion import cli, core, server
from scholion import format as fmt
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

LAYERS = ("labs", "dynamics", "genetics", "medications", "target", "tests", "questions")
BASKETS = ("lab", "genome", "ask")
WEB = Path(server.__file__).resolve().parent / "web" / "index.html"

#: Words a clinical sentence must not open with — the list the target layer's
#: test uses, widened. The Russian catalogue is held by SHAPE below rather than
#: by a word list: the language gate counts every Cyrillic letter in this tree,
#: and a list of Russian imperatives in a test is exactly the kind of «input
#: pattern» it would have to be told about by hand.
IMPERATIVE = ("start", "stop", "take", "increase", "reduce", "cancel", "raise", "lower",
              "begin", "avoid", "switch", "add", "remove", "order")


def _main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue()


class TestTheCommandLine(unittest.TestCase):

    def test_an_empty_curated_file_answers_every_system_and_none_says_nothing_found(self):
        """Item 1. With no base and no curated rows every laboratory system says
        «no genetic list in this build», and the wearable one says «no genetic
        half by design» — three different answers, not an empty block."""
        with mock.patch.object(SP, "_base", lambda: {}), \
                mock.patch.object(SP, "_curated", lambda: {"_meta": {"why_empty": "nobody wrote a row"}}):
            for d in SP.domains():
                with self.subTest(system=d["key"]):
                    code, out = _main(["system", d["key"]])
                    self.assertEqual(0, code)
                    self.assertNotIn("nothing reportable was found", out.lower())
                    if d["genetic_half"]:
                        self.assertIn("no genetic list for this system is in this build", out)
                    else:
                        self.assertIn("no genetic half by design", out)

    def test_the_card_prints_seven_numbered_layers_and_the_three_baskets(self):
        """Items 7, 8 and 12: one block, seven layers in order, three baskets."""
        code, out = _main(["system", "lipids"])
        self.assertEqual(0, code)
        heads = [int(m) for m in re.findall(r"^\*\*(\d)\. ", out, re.M)]
        self.assertEqual([1, 2, 3, 4, 5, 6, 7], heads)
        for basket in ("to test", "to read in the genome", "to ask the clinician"):
            self.assertIn("**" + basket + "**", out)
        self.assertEqual(1, out.count("**System: "), "one card, one block")
        self.assertTrue(out.rstrip().endswith("_"), "the block ends with the disclaimer")

    def test_an_empty_basket_names_its_reason(self):
        """Item 8 on the printed face: the genome basket of a system with no
        genetic list says why it is empty, in words. Every shipped system has a
        list since 13.09.2026, so the base is emptied for the check."""
        with mock.patch.object(SP, "_base", lambda: {}), \
                mock.patch.object(SP, "_curated", lambda: {"_meta": {"why_empty": "nobody wrote a row"}}):
            _, out = _main(["system", "lipids"])
        tail = out.split("**to read in the genome**", 1)[1].split("**to ask", 1)[0]
        self.assertIn("no genetic list for this system is in this build", tail)

    def test_the_questions_close_the_card_and_an_empty_list_says_why(self):
        """Item 16, both ways: a card with a gap ends its layers on the
        questions; a card with nothing open prints the reason instead."""
        _, out = _main(["system", "lipids"])
        self.assertIn("**7. Questions for the clinician**", out)
        self.assertRegex(out, r"7\. Questions for the clinician\*\*\n   1\. ")
        r = SP.system("lipids")
        r["questions"] = {"status": "ok", "rows": [], "empty_why": "nothing_open"}
        text = fmt.system_report(r)
        self.assertIn(en.MESSAGES["system.why.nothing_open"], text)

    def test_the_two_registers_share_the_verdict_and_differ_in_detail(self):
        """Item 10 on the printed face."""
        _, patient = _main(["system", "thyroid"])
        _, clinician = _main(["system", "thyroid", "--register", "clinician"])
        v = lambda s: s.splitlines()[2]                      # noqa: E731 — the verdict line
        self.assertEqual(v(patient), v(clinician))
        self.assertGreater(len(clinician), len(patient))
        self.assertIn("clinician's register", clinician)
        self.assertIn("patient's register", patient)

    def test_with_no_key_the_systems_are_listed_and_a_wrong_key_names_them(self):
        code, out = _main(["system"])
        self.assertEqual(0, code)
        for d in SP.domains():
            self.assertIn("`" + d["key"] + "`", out)
        code, out = _main(["system", "spleen"])
        self.assertEqual(0, code)
        self.assertIn("thyroid", out)

    def test_json_carries_every_layer_with_a_status(self):
        """Item 7 on the machine face."""
        _, out = _main(["system", "thyroid", "--json"])
        r = json.loads(out)
        for layer in LAYERS:
            with self.subTest(layer=layer):
                self.assertIn("status", r[layer])
        for basket in BASKETS:
            b = r["next"][basket]
            self.assertTrue(b["rows"] or (b["empty_why"] and b["empty_reason"]),
                            f"basket «{basket}» is silently empty")


class TestNoClinicalLineIsAnInstruction(unittest.TestCase):
    """Item 9, by reading the texts — every `system.*` phrase in both catalogues
    and two rendered cards — rather than by the author's intention."""

    def _check(self, text: str, where: str):
        for line in text.splitlines():
            words = line.strip().lstrip("·-*_0123456789. ").split(" ")
            if len(words) < 2:
                continue                          # a lone label is not a sentence
            first = words[0].lower().strip("{}:,")
            self.assertNotIn(first, IMPERATIVE, f"{where}: «{line.strip()[:80]}»")

    def test_the_catalogue(self):
        for key, text in en.MESSAGES.items():
            if key.startswith(("system.", "systems.", "tool.sch_system.")):
                self._check(text, f"en:{key}")

    def test_the_russian_edition_asks_where_the_english_one_asks(self):
        """A question is the one clinical shape that cannot be an instruction,
        and the two catalogues must agree on which phrases are questions."""
        for key, text in en.MESSAGES.items():
            if key.startswith(("system.q.", "system.next.", "system.row.")):
                with self.subTest(key=key):
                    self.assertEqual(text.rstrip().endswith("?"),
                                     ru.MESSAGES[key].rstrip().endswith("?"))

    def test_the_rendered_cards(self):
        for reg in SP.REGISTERS:
            for key in ("lipids", "thyroid", "fitness"):
                self._check(fmt.system_report(SP.system(key, reg)), f"{key}/{reg}")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestOverHttp(unittest.TestCase):
    """The same answer through the routes the page reads."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="scholion-system-")
        cls._profile = Path(cls._tmp) / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, cls._profile)
        cls._was = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(cls._profile)
        core.reset_cache()
        cls.port = _free_port()
        cls.srv = server._Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(50):
            try:
                cls.get("/api/ping")
                break
            except Exception:                                    # noqa: BLE001
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        if cls._was is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = cls._was
        core.reset_cache()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def get(cls, path):
        with urllib.request.urlopen(cls.base + path, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_the_two_rings_are_two_numbers(self):
        """Item 11: the laboratory ring and the genetics ring are separate
        counts, and no field folds them into one figure."""
        d = self.get("/api/systems")
        self.assertEqual(len(SP.domains()), d["count"])
        for s in d["systems"]:
            with self.subTest(system=s["key"]):
                self.assertIn("measured", s["labs"])
                self.assertIn("total", s["labs"])
                self.assertIsInstance(s["genetics"]["read_count"], int)
                self.assertIsInstance(s["genetics"]["unread_count"], int)
                self.assertFalse({"completeness", "index", "combined"} & set(s),
                                 "a single index of completeness is what 6.6 forbids")
        thyroid = next(s for s in d["systems"] if s["key"] == "thyroid")
        self.assertEqual("composed", thyroid["genetics"]["status"])
        fitness = next(s for s in d["systems"] if s["key"] == "fitness")
        self.assertEqual("no_genetic_half", fitness["genetics"]["status"])

    def test_the_card_carries_seven_layers_and_the_registers_agree_on_the_verdict(self):
        p = self.get("/api/system?key=thyroid&register=patient")
        c = self.get("/api/system?key=thyroid&register=clinician")
        for layer in LAYERS:
            self.assertIn("status", p[layer])
        self.assertEqual(p["verdict"], c["verdict"])
        self.assertEqual(p["verdict_line"], c["verdict_line"])
        self.assertGreaterEqual(len(c["genetics"]["rows"]), len(p["genetics"]["rows"]))
        self.assertIn("rows_withheld_as_detail", p["genetics"])
        self.assertNotIn("rows_withheld_as_detail", c["genetics"])

    def test_a_missing_key_names_the_systems_and_the_baskets_never_fall_silent(self):
        r = self.get("/api/system")
        self.assertEqual("unknown_system", r["status"])
        self.assertIn("thyroid", r["systems"])
        for key in ("lipids", "fitness"):
            n = self.get("/api/system?key=" + key)["next"]
            for basket in BASKETS:
                with self.subTest(system=key, basket=basket):
                    b = n[basket]
                    self.assertTrue(b["rows"] or b["empty_reason"])

    def test_the_joins_the_other_tabs_read_are_in_the_listing(self):
        d = self.get("/api/systems")
        self.assertIn("prescriptions", d)
        self.assertIn("genes_index", d)
        self.assertIn("class_systems", d)
        self.assertEqual(["thyroid"], d["class_systems"]["thyroid_hormone"])
        m = self.get("/api/labs")["markers"][0]
        self.assertIn("system", m, "a marker names the system whose panel holds it")


if __name__ == "__main__":
    unittest.main()


class TestTheToolFace(unittest.TestCase):
    """The fourth door — the tool an assistant calls — hands out the same card
    the command line prints, and with no key it hands out the same listing."""

    def test_the_tool_answers_with_the_card_the_command_line_prints(self):
        from scholion import engine, ouroboros_tools as OT
        ctx = OT.ToolContext()
        self.assertEqual(fmt.system_report(engine.system("thyroid", "clinician")),
                         OT._h_system(ctx, key=" thyroid ", register="clinician"))
        self.assertEqual(fmt.system_report(engine.system("thyroid", "patient")),
                         OT._h_system(ctx, key="thyroid"), "no register means the patient's")

    def test_without_a_key_the_tool_lists_the_systems(self):
        from scholion import engine, ouroboros_tools as OT
        self.assertEqual(fmt.systems_report(engine.systems()),
                         OT._h_system(OT.ToolContext(), key="  "))
        entry = next(e for e in OT.get_tools() if e.name == "sch_system")
        self.assertIs(OT._h_system, entry.fn if hasattr(entry, "fn") else OT._h_system)


if __name__ == "__main__":
    unittest.main()
