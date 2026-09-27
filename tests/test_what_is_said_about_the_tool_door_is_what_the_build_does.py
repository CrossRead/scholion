"""What is SAID about the tool door is held to what the build does.

An outside report against 0.4.11 found three statements that had come apart
from the build, and nothing in the suite could have noticed any of them:

* the canon told a model to consult `genome-status` and to run `selfcheck`
  before any negative conclusion — and the tool door carried neither;
* the absence of a tool for the regimen was excused by «the list is already
  inside overview», and the overview carries a count;
* a command was excused from the door BECAUSE it writes, while the manifest —
  computed from another table — called it a read, safe to call for an answer.

Each was a sentence, kept in one place, about a fact kept in another. So the
sentences now stand beside something a test can run: a kind from a closed
list, the tools a command is reached through, and — where the claim is «a
model gets this elsewhere» — a probe that calls both and compares.
"""
from __future__ import annotations

import json
import re
import unittest
from unittest import mock

import support
from scholion import contract, i18n
from scholion import ouroboros_tools as ot


def tools():
    return {t.name: t for t in ot.get_tools()}


def call(cmd: str) -> str:
    """The answer of the tool door for a command, by the call the contract names."""
    return tools()[contract.PLUGIN[cmd]].handler(None, **(contract.PLUGIN_ARGS.get(cmd) or {}))


class TestTheClaimsHold(unittest.TestCase):

    def test_nothing_said_about_the_door_disagrees_with_the_build(self):
        self.assertEqual([], contract.check_door_claims())

    def test_every_command_the_canon_names_is_a_call_this_door_answers(self):
        named = contract.commands_named_in(contract.canon_text())
        self.assertTrue(named, "the canon names no command at all — the reader is broken")
        for cmd in named:
            with self.subTest(command=cmd):
                self.assertIn(cmd, contract.PLUGIN)
                self.assertTrue(call(cmd).strip())

    def test_the_canon_handed_through_the_door_says_how_to_run_what_it_names(self):
        text = tools()["sch_rules"].handler(None)
        self.assertTrue(text.startswith(contract.canon_text().rstrip("\n")[:200]))
        tail = text[len(contract.canon_text().rstrip("\n")):]
        for cmd in contract.commands_named_in(contract.canon_text()):
            with self.subTest(command=cmd):
                self.assertIn(f"`{cmd}` — {contract.tool_call(cmd)}", tail)

    def test_the_canon_itself_is_not_rewritten_by_the_door(self):
        """The table is added after the canon; not one character of the rules moves."""
        text = tools()["sch_rules"].handler(None)
        self.assertIn(contract.canon_text().rstrip("\n"), text)


class TestEachRuleSeesWhatItIsFor(unittest.TestCase):
    """A check that has never failed has not been shown to work."""

    def problems(self):
        return "\n".join(contract.check_door_claims())

    def test_a_command_excused_as_a_write_and_missing_from_writes(self):
        with mock.patch.object(contract, "WRITES", contract.WRITES - {"choose-genome"}):
            self.assertIn("«choose-genome» has no tool because it writes", self.problems())

    def test_a_write_excused_as_something_else(self):
        with mock.patch.dict(contract.TOOLLESS, {"redact": ("for_the_person", ())}):
            self.assertIn("«redact» is in WRITES", self.problems())

    def test_a_sentence_with_no_kind(self):
        with mock.patch.dict(contract.NO_PLUGIN, {"medications": "the list is already inside overview"}):
            self.assertIn("«medications» is excused from the tool door by a sentence and no kind",
                          self.problems())

    def test_a_kind_outside_the_list(self):
        with mock.patch.dict(contract.TOOLLESS, {"serve": ("some day", ())}):
            self.assertIn("«some day» is not one of", self.problems())

    def test_a_sentence_that_names_a_tool_nothing_lists(self):
        with mock.patch.dict(contract.NO_PLUGIN, {"doc": "the same text comes through `sch_rules`"}):
            self.assertIn("the reason for «doc» names «sch_rules»", self.problems())

    def test_a_route_through_a_tool_that_is_not_there(self):
        with mock.patch.dict(contract.TOOLLESS, {"panel": ("reached_through", ("sch_nothing",))}):
            self.assertIn("reached through «sch_nothing»", self.problems())

    def test_a_route_that_names_no_tool(self):
        with mock.patch.dict(contract.TOOLLESS, {"panel": ("reached_through", ())}):
            self.assertIn("«panel» is «reached_through» and names no tool", self.problems())

    def test_a_job_the_recompute_does_not_run(self):
        from scholion import recompute
        runners = {k: v for k, v in recompute.RUNNERS.items() if k != "scholion acmg-scan"}
        with mock.patch.object(recompute, "RUNNERS", runners):
            self.assertIn("«acmg-scan» is said to be started through sch_recompute", self.problems())

    def test_an_argument_the_tool_does_not_take(self):
        with mock.patch.dict(contract.PLUGIN_ARGS, {"reconcile": {"everything": True}}):
            self.assertIn("with «everything», and the tool takes no such parameter", self.problems())

    def test_two_commands_behind_one_plain_call(self):
        with mock.patch.dict(contract.PLUGIN_ARGS, clear=True):
            self.assertIn("are both answered by the plain call", self.problems())

    def test_a_command_the_canon_names_and_no_tool_answers(self):
        plugin = {k: v for k, v in contract.PLUGIN.items() if k != "genome-status"}
        with mock.patch.object(contract, "PLUGIN", plugin), \
                mock.patch.dict(contract.NO_PLUGIN, {"genome-status": "already inside overview"}), \
                mock.patch.dict(contract.TOOLLESS, {"genome-status": ("for_the_person", ())}):
            self.assertIn("the canon names «genome-status», and no tool answers for it",
                          self.problems())

    def test_a_kind_with_no_sentence(self):
        with mock.patch.dict(contract.TOOLLESS, {"labs": ("for_the_person", ())}):
            self.assertIn("«labs» has a kind in TOOLLESS and no sentence", self.problems())

    def test_an_argument_for_a_command_that_has_no_tool(self):
        with mock.patch.dict(contract.PLUGIN_ARGS, {"serve": {"port": 1}}):
            self.assertIn("PLUGIN_ARGS names «serve», which has no tool", self.problems())

    def test_a_canon_that_cannot_be_read_is_said_and_not_passed_over(self):
        with mock.patch.object(contract, "canon_text", side_effect=OSError("gone")):
            self.assertIn("the canon could not be read: OSError", self.problems())

    def test_recompute_steps_that_cannot_be_read_are_said(self):
        from scholion import recompute
        with mock.patch.object(recompute, "RUNNERS", None):
            self.assertIn("the recompute steps could not be read: TypeError", self.problems())

    def test_the_call_is_spelled_the_way_a_model_makes_it(self):
        self.assertEqual("sch_medications", contract.tool_call("medications"))
        self.assertEqual("sch_selfcheck with full=true", contract.tool_call("reconcile"))
        self.assertIsNone(contract.tool_call("serve"))
        with mock.patch.dict(contract.PLUGIN_ARGS, {"labs": {"markers": "tsh", "catalogue": False}}):
            self.assertEqual("sch_analyze_labs with catalogue=false, markers=tsh",
                             contract.tool_call("labs"))

    def test_the_manifest_says_what_stands_in_for_a_missing_tool(self):
        by = {c["command"]: c["faces"] for c in contract.capabilities()["commands"]}
        self.assertEqual("sch_selfcheck with full=true", by["reconcile"]["plugin_call"])
        self.assertIsNone(by["reconcile"]["plugin_absent"])
        absent = by["acmg-scan"]["plugin_absent"]
        self.assertEqual("person_starts", absent["kind"])
        self.assertEqual(["sch_recompute", "sch_acmg"], absent["through"])
        self.assertTrue(absent["why"])
        from scholion import format as fmt
        printed = fmt.capabilities_report(contract.capabilities())
        self.assertIn("reached through sch_recompute, sch_acmg", printed)
        self.assertIn("sch_selfcheck with full=true", printed)

    def test_a_word_that_equals_a_command_is_not_a_naming(self):
        self.assertEqual([], contract.commands_named_in("read the profile and a marker"))
        self.assertEqual(["selfcheck", "reconcile", "labs"], contract.commands_named_in(
            "run `selfcheck` / `python3 -m scholion reconcile --ocr`, then `scholion labs`, "
            "then `selfcheck` again and `bgzip`"))


def _panel_is_reached_through_the_system_card(case: unittest.TestCase) -> None:
    """Every panel `panel` lists is a card `sch_system` prints, with its positions."""
    _, listing, _ = support.run(["panel", "--json"])
    rows = json.loads(listing).get("panels") or json.loads(listing).get("systems") or []
    keys = [r.get("key") for r in rows if isinstance(r, dict) and r.get("key")]
    case.assertTrue(keys, "the panel listing names no panel — the probe reads the wrong field")
    card = tools()["sch_system"].handler
    compared = 0
    for key in keys:
        with case.subTest(panel=key):
            one = json.loads(support.run(["panel", key, "--json"])[1])
            text = card(None, key=key, register="clinician")
            for pos in one.get("positions") or []:
                rsid = pos.get("rsid") if isinstance(pos, dict) else None
                if rsid:
                    compared += 1
                    case.assertIn(rsid, text, f"{key}: `panel` names {rsid} and the card does not")
    case.assertGreater(compared, 100, "the probe compared next to nothing")


PROBES = {"panel": _panel_is_reached_through_the_system_card}


class TestWhatIsReachedElsewhereIsReallyThere(unittest.TestCase):

    def test_every_such_claim_has_a_probe(self):
        claimed = sorted(c for c, (kind, _) in contract.TOOLLESS.items() if kind == "reached_through")
        self.assertEqual(claimed, sorted(PROBES),
                         "a command said to be reached through other tools, and nothing runs "
                         "both to see whether it is")

    def test_the_probes_pass(self):
        for cmd, probe in sorted(PROBES.items()):
            with self.subTest(command=cmd):
                probe(self)


class TestAReadThroughTheDoorIsTheSameRead(unittest.TestCase):
    """The tool and the command are one capability: same structure, same words."""

    SAME = ("medications", "genome-status", "genome-updates", "capabilities", "markers",
            "evidence-levels", "profile", "selfcheck", "reconcile")

    def test_the_text_is_the_text_the_command_prints(self):
        for cmd in self.SAME:
            with self.subTest(command=cmd):
                code, out, err = support.run([cmd])
                self.assertEqual(0, code, err)
                said = call(cmd)
                # The door adds a note about a newer build to its first answer;
                # everything the command printed must be in what the tool said.
                self.assertIn(out.strip(), said)

    def test_the_structure_is_the_structure_the_command_prints(self):
        for cmd in self.SAME:
            handler = tools()[contract.PLUGIN[cmd]].handler
            if not hasattr(handler, "both"):
                continue
            with self.subTest(command=cmd):
                _, data = handler.both(**(contract.PLUGIN_ARGS.get(cmd) or {}))
                want = support.run_json([cmd])
                self.assertEqual(json.loads(json.dumps(want, default=str)),
                                 json.loads(json.dumps(data, default=str)))


class TestTheAuditReadsTheFolderTheProfileDeclares(unittest.TestCase):
    """A model cannot point the audit at a folder of its own choosing: the audit
    rebuilds the record of where each point came from."""

    def test_the_tool_takes_no_folder(self):
        props = tools()["sch_selfcheck"].schema["parameters"]["properties"]
        self.assertEqual(["full"], sorted(props))

    def test_a_folder_handed_over_anyway_is_refused_and_nothing_is_read(self):
        from scholion import reconcile
        with mock.patch.object(reconcile, "reconcile") as run:
            with self.assertRaises(TypeError):
                tools()["sch_selfcheck"].handler(None, folder="/somewhere/else")
        run.assert_not_called()

    def test_both_readings_ask_for_the_declared_folder(self):
        from scholion import reconcile
        answer = {"ok": False, "error": "no folder"}
        for args in ({}, {"full": True}):
            with self.subTest(arguments=args):
                with mock.patch.object(reconcile, "reconcile", return_value=dict(answer)) as run:
                    tools()["sch_selfcheck"].handler(None, **args)
                run.assert_called_once_with(None)


class TestTheRegimenCanBeRead(unittest.TestCase):

    def test_every_prescription_on_file_is_named(self):
        from scholion import store
        names = [m.get("name") for m in store.list_medications() if m.get("name")]
        self.assertTrue(names, "the fixture holds no prescription — the test proves nothing")
        said = call("medications")
        for name in names:
            with self.subTest(prescription=name):
                self.assertIn(name, said)

    def test_the_overview_alone_would_not_have_done(self):
        """The sentence that excused the missing tool, measured: it is not true,
        and this is what keeps anybody from writing it again."""
        from scholion import store
        names = [m.get("name") for m in store.list_medications() if m.get("name")]
        said = tools()["sch_overview"].handler(None)
        self.assertTrue([n for n in names if n not in said],
                        "the overview names every prescription now — then say so in the "
                        "contract and drop this test, do not leave both")


class TestTheScreenThatWasNeverRunIsOffered(unittest.TestCase):

    def plan(self, never_run: bool, clinvar):
        from scholion import coverage, recompute
        with mock.patch.object(recompute, "_acmg_never_run", return_value=never_run), \
                mock.patch.object(coverage, "clinvar_path", return_value=clinvar):
            steps = recompute.plan()["steps"]
        return [s for s in steps if s.get("key") == "scholion acmg-scan"]

    def test_with_the_reference_file_at_hand_the_step_is_ready(self):
        step = self.plan(True, "/somewhere/clinvar.vcf.gz")
        self.assertEqual(1, len(step))
        self.assertEqual(("ready", "acmg_missing"), (step[0]["state"], step[0]["why"]))

    def test_without_it_the_step_says_what_it_needs(self):
        step = self.plan(True, None)
        self.assertEqual(("needs_input", "no_clinvar"), (step[0]["state"], step[0]["why"]))

    def test_a_screen_that_was_run_is_not_offered_again(self):
        self.assertEqual([], self.plan(False, "/somewhere/clinvar.vcf.gz"))

    def test_never_run_means_a_genome_and_no_table_beside_it(self):
        import shutil
        import tempfile
        from pathlib import Path
        from scholion import core, genome, recompute
        base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, base, True)
        with mock.patch.object(core, "genome_bases", return_value=[base]):
            with mock.patch.object(genome, "available", return_value={"ready": False}):
                self.assertFalse(recompute._acmg_never_run())
            with mock.patch.object(genome, "available", return_value={"ready": True}):
                self.assertTrue(recompute._acmg_never_run())
                (base / "acmg_sf_hits.tsv").write_text("gene\n", encoding="utf-8")
                self.assertFalse(recompute._acmg_never_run())
            with mock.patch.object(genome, "available", side_effect=RuntimeError("unreadable")):
                self.assertFalse(recompute._acmg_never_run())

    def test_the_reason_is_a_sentence_in_both_languages(self):
        for lang in ("en", "ru"):
            with self.subTest(language=lang):
                i18n.set_lang(lang)
                self.addCleanup(i18n.set_lang, "en")
                self.assertNotIn("⟦", i18n.t("recompute.why.acmg_missing"))


class TestTheDoorSaysWhenToUseIt(unittest.TestCase):
    """A host that reads no skill entry sees tool descriptions and nothing else."""

    def descriptions(self, lang):
        i18n.set_lang(lang)
        self.addCleanup(i18n.set_lang, "en")
        return {t.name: t.schema["description"] for t in ot.get_tools()}

    def test_a_visit_to_a_physician_leads_to_the_page_written_for_it(self):
        self.assertIn("visit to a physician", self.descriptions("en")["sch_second_opinion"])
        self.assertIn("визиту к врачу", self.descriptions("ru")["sch_second_opinion"])

    def test_a_tool_with_a_second_reading_says_so_where_a_model_reads(self):
        for lang in ("en", "ru"):
            for cmd, args in sorted(contract.PLUGIN_ARGS.items()):
                tool = contract.PLUGIN[cmd]
                schema = {t.name: t.schema for t in ot.get_tools()}[tool]
                i18n.set_lang(lang)
                self.addCleanup(i18n.set_lang, "en")
                for name in args:
                    with self.subTest(language=lang, tool=tool, parameter=name):
                        text = i18n.t(f"tool.{tool}.param.{name}")
                        self.assertNotIn("⟦", text)
                        self.assertTrue(re.search(r"\w", text))
                        self.assertIn(name, schema["parameters"]["properties"])


class TestTheInstructionNamesTheToolsTheBuildHas(unittest.TestCase):
    """The paragraph said «32 tools» and listed thirty-two while the build
    registered thirty-five: the counter test looked for «registers N», and this
    sentence is worded another way. Read here by what it lists, not by a phrase."""

    def paragraph(self):
        text = contract.instruction_text()
        start = text.index("through one registry")
        return text[start:text.index("derives the list from the build", start)]

    def test_the_number_is_the_number_registered(self):
        found = re.search(r"(\d+) tools", self.paragraph())
        self.assertIsNotNone(found)
        self.assertEqual(len(ot.get_tools()), int(found.group(1)))

    def test_every_tool_is_named_and_nothing_else_is(self):
        named = set(re.findall(r"`(sch_[a-z_]+)`", self.paragraph()))
        self.assertEqual(set(tools()), named)

    def test_every_second_reading_is_spelled_out(self):
        para = self.paragraph()
        for cmd, args in sorted(contract.PLUGIN_ARGS.items()):
            for name in args:
                with self.subTest(command=cmd):
                    self.assertIn(f"`{contract.PLUGIN[cmd]}` with", para)
                    self.assertIn(f"`{name}=true` is", para)
                    self.assertIn(f"`{cmd}`", para)


if __name__ == "__main__":
    unittest.main()
