"""One capability, four faces, one tick.

The rule this file enforces is the project's oldest and the one it keeps
breaking: a capability is added to the core and then has to REACH somebody, and
it reaches them through four doors —

    the web interface        a person clicking
    the command line         a MODEL with a shell, first; a person typing, second
    the plugin's tool list   a model deciding what it can call
    the model's instruction  a model deciding what exists at all

The second line said «a person typing, and every script» until the owner
corrected it, and the correction is not cosmetic. Three of the four doors are
model-facing, and the command line is the widest of them: it is how an agent that
has the binary actually works with Scholion. That changes where the danger sits.
A model reaching the command line does not explore — it will not try `--help` on
a hunch — it runs what its instruction named. So the instruction is not a fourth
peer face; it is the DISCOVERY MECHANISM of the main surface, and the day it
falls behind, that surface silently shrinks to whatever the document remembers.

`contract.py` was written after «Second opinion», the summary and the health
index lived in the web tabs alone for half a year. It closed the first two doors
against each other and left the other two open. Both then drifted, and each was
found the same way — not by a test, but by somebody noticing months later:

  · the plugin lacked nine capabilities, `limits` among them, so a model could
    not ask what the data cannot answer;
  · the instruction named 40 commands of 47, and three of the seven absent were
    real capabilities — two added the same week they were found missing.

WHY ONE TEST AND NOT FOUR. The question an author has after adding something is
«what did I forget», and four separate red runs answer it one quarter at a time:
a run per face, a fix per run, and the fourth found an hour later. This reports
every face at once, in one message.

WHY THE FACES ARE NOT EQUAL. A person who suspects something is missing has
other channels: the README, the tab bar, a search, asking. A model has the
document it was given. It cannot see a capability it was never shown — it answers
from what it has instead of saying it cannot, and that answer looks exactly like
a good one. So the model-facing doors carry a higher bar: an omission is written
down with a reason, and the reason must be about the capability, not about the
schedule.

AND THE INSTRUCTION IS NOT THE ONLY ROUTE ANY MORE. `scholion capabilities` is
generated from the parser and the maps here, so it cannot fall behind them, and
the instruction now tells a model to believe it over itself. That is the point:
a hand-written document is a single point of failure for the surface a model
uses most, and the fix is a second route to the same truth rather than a promise
to keep the first one current.
"""
from __future__ import annotations

import unittest

import support
from scholion import contract


class TestEveryFaceMovesInTheSameTick(unittest.TestCase):

    def test_nothing_reaches_only_some_of_the_four(self):
        faces = contract.check_all_faces()
        broken = {name: probs for name, probs in faces.items() if probs}
        if broken:
            lines = ["A capability has moved on some faces of the core and not others:", ""]
            for name, probs in broken.items():
                lines.append(f"  {name}")
                lines += [f"    · {p}" for p in probs]
                lines.append("")
            lines.append("Add the missing entry point, or record the omission with its reason "
                         "in the matching list in contract.py. There are no silent exceptions.")
            self.fail("\n".join(lines))

    def test_the_report_covers_every_face_the_project_claims_to_have(self):
        """The map of faces is itself something that can fall behind.

        `contract.py` opens by naming three faces and the instruction is a
        fourth. If a fifth ever appears — an MCP server is in the backlog as
        task 13 — this is the assertion that will fail and say so.
        """
        faces = set(contract.check_all_faces())
        self.assertEqual(len(faces), 4, f"the number of faces changed: {sorted(faces)}")

    def test_an_excuse_names_the_capability_and_not_the_calendar(self):
        """«Not yet» is not a reason; it is a note about the author's week.

        A reason has to say why the capability does not belong on that face at
        all, because a reason of the other kind quietly becomes permanent.
        """
        # English only, and that is not an oversight: `check_language.py` refuses
        # Russian anywhere in the shipping tree, `contract.py` included, so a
        # reason in another language cannot reach these tables without failing a
        # different gate first. Two gates, one rule each.
        bad = ("not yet", "todo", "later", "temporar", "for now", "wip", "soon")
        for label, table in (("NO_CLI", contract.NO_CLI),
                             ("NO_PLUGIN", contract.NO_PLUGIN),
                             ("NO_INSTRUCTION", contract.NO_INSTRUCTION)):
            for key, reason in table.items():
                with self.subTest(table=label, key=key):
                    self.assertTrue(reason and reason.strip(), "an empty reason")
                    low = reason.lower()
                    self.assertFalse(any(w in low for w in bad),
                                     f"{label}[{key}] excuses the omission by time rather "
                                     f"than by nature: {reason!r}")


class TestTheModelFacingDoorsCarryTheHigherBar(unittest.TestCase):
    """A person notices an absence. A model does not."""

    def test_every_read_capability_reaches_the_model_somehow(self):
        """Either as a tool it can call, or named in what it is told.

        A capability excused from BOTH is invisible to a model twice over, and
        that is a decision worth making on purpose rather than by two separate
        omissions that never met.
        """
        invisible = sorted(set(contract.NO_PLUGIN) & set(contract.NO_INSTRUCTION))
        for cmd in invisible:
            with self.subTest(command=cmd):
                self.assertIn(cmd, contract.NO_PLUGIN)
                self.assertIn(cmd, contract.NO_INSTRUCTION)
        # Not an error — a ledger. These are the commands no model can reach by
        # any route, and the list should be short and boring.
        self.assertLessEqual(len(invisible), 8,
                             f"{len(invisible)} capabilities are hidden from a model on "
                             f"every route: {invisible}")

    def test_the_instruction_is_the_one_a_recipient_gets(self):
        """Checked against the SHARED edition, not the owner's.

        The owner's edition carries personal refinements and never ships. A guard
        pointed at it would pass on one machine and prove nothing about the file
        every other user's model actually reads — the shape of defect this
        project has now paid for four times.
        """
        self.assertIn("share/", contract.INSTRUCTION_DOC)
        self.assertNotIn("owner", contract.INSTRUCTION_DOC)


class TestTheManifestCannotFallBehindTheBuild(unittest.TestCase):
    """The second route to what this build can do.

    A model with a stale instruction and a current binary can ask the binary —
    but only while the manifest is generated rather than maintained. These check
    that it still is.
    """

    def test_every_command_appears_exactly_once(self):
        caps = contract.capabilities()
        names = [c["command"] for c in caps["commands"]]
        self.assertEqual(sorted(names), sorted(contract.cli_commands()),
                         "the manifest and the parser disagree about what exists")
        self.assertEqual(len(names), len(set(names)))

    def test_reading_and_writing_are_separated_and_the_split_is_complete(self):
        """The one distinction a caller must not get wrong.

        Everything else it can discover by running the thing; whether a command
        changes the person's data it has to know BEFORE running anything.
        """
        caps = contract.capabilities()
        self.assertEqual(sorted(caps["reads_only"] + caps["writes"]),
                         sorted(contract.cli_commands()),
                         "a command is in neither list, so a caller cannot tell")
        self.assertFalse(set(caps["reads_only"]) & set(caps["writes"]))

    def test_the_writes_split_covers_everything_and_nothing_twice(self):
        """AUTHORS and TRANSCRIBES must partition WRITES exactly.

        A write outside both sets is a write whose rule nobody wrote down;
        a write in both is a rule that contradicts itself.
        """
        self.assertEqual(contract.AUTHORS | contract.TRANSCRIBES, contract.WRITES,
                         "a write command belongs to neither kind, so no rule covers it")
        self.assertFalse(contract.AUTHORS & contract.TRANSCRIBES,
                         "a command cannot both invent values and merely move a document")

    def test_no_authoring_command_is_offered_to_a_model_as_a_tool(self):
        """The first version of this test banned all of WRITES from the tool list —
        and went red on sch_ingest_labs, which had been a tool from the beginning.
        The premise was false, not the build: ingest-labs moves the person's own
        documents into the profile and invents nothing, so a model may hold it.
        What a model must never hold is a command that AUTHORS values from
        nobody's document. Hence the split, and hence this test's narrower claim.
        """
        for cmd in sorted(contract.AUTHORS):
            with self.subTest(command=cmd):
                self.assertNotIn(cmd, contract.PLUGIN,
                                 f"«{cmd}» invents values into the profile and is exposed "
                                 f"as a tool")
                self.assertIn(cmd, contract.NO_PLUGIN,
                              f"«{cmd}» invents values into the profile and its absence "
                              f"from the tool list is not written down anywhere")

    def test_every_transcribing_command_is_accounted_for_either_way(self):
        """A transcriber MAY be a tool — but the decision must be recorded,
        in PLUGIN if a model holds it, in NO_PLUGIN with a reason if not.
        Silence is the one state the contract does not allow.
        """
        for cmd in sorted(contract.TRANSCRIBES):
            with self.subTest(command=cmd):
                self.assertTrue(cmd in contract.PLUGIN or cmd in contract.NO_PLUGIN,
                                f"«{cmd}» moves the person's documents and nobody decided "
                                f"whether a model may hold it")

    def test_every_write_in_the_manifest_names_its_kind(self):
        """A caller deciding whether to run a write needs to know WHICH rule
        applies — «never for a model» or «the person's own document only»."""
        for c in contract.capabilities()["commands"]:
            with self.subTest(command=c["command"]):
                if c["writes"]:
                    self.assertIn(c["kind"], ("authors", "transcribes"),
                                  f"«{c['command']}» writes but does not say how")
                else:
                    self.assertEqual(c["kind"], "reads",
                                     f"«{c['command']}» does not write yet claims a "
                                     f"writing kind")

    def test_every_command_carries_a_sentence_saying_what_it_does(self):
        empty = [c["command"] for c in contract.capabilities()["commands"] if not c["does"]]
        self.assertEqual(empty, [], "a command with no help text is a command a model "
                                    "cannot choose between")

    def test_the_instruction_points_at_the_manifest(self):
        """Otherwise the second route exists and nobody is told to take it."""
        text = contract.instruction_text()
        self.assertIn("scholion capabilities", text)
        self.assertIn("believe the build", text.lower().replace("**", ""))


if __name__ == "__main__":
    unittest.main()
