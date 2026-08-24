"""The cheapest door: a folder with one file in it, at a path several hosts read.

No registry, no account, nobody's moderation — and no plugin mechanism either,
which is the point. A host that has none of those can still be reached, and the
instructions for it are one line.

What makes that line worth trusting is that the single file has to carry
everything by itself. A host reading only `SKILL.md` learns from it or does not
learn at all: what this is, what to run, the safety rules that come before any
answer, and — the line this door was blocked on for two releases — that a tool
server and an in-process module exist. Until 24.08.2026 the entry named neither,
so a runtime without a plugin mechanism had no way to discover the door built
for it.

So the properties are checked on the FILE, not on a description of it, and the
claim `access()` makes about that file is checked against the file too. A door
that describes itself is only as good as the description.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import contract

ENTRY = contract.skill_entry_path()

#: The entry a model loads first. `docs/DEVELOPMENT.md` fixes the ceiling: the
#: long text is `INSTRUCTION.md` and is opened on demand, because loading a
#: thousand lines on every trigger costs about seventeen thousand tokens.
MAX_ENTRY_BYTES = 12 * 1024


class TestTheEntryIsWhatAHostNeeds(unittest.TestCase):

    def setUp(self):
        if ENTRY is None or not ENTRY.exists():
            self.skipTest("this build carries no skill entry")
        self.text = ENTRY.read_text(encoding="utf-8")

    def test_it_opens_with_frontmatter(self):
        self.assertTrue(self.text.startswith("---\n"),
                        "a host reads the frontmatter first and would find prose")

    def test_the_frontmatter_carries_a_name_and_a_description_and_no_licence(self):
        """Two fields, and deliberately not a third. A `license` in the
        frontmatter would put one statement of the licensing on the entry and
        another in the package, and the two are NOT the same: what a host may
        redistribute is this file, while the instruction and the canon of rules
        stay with the package they are printed from."""
        fields = set(re.findall(r"^([a-z_]+):", self.text.split("---")[1], re.M))
        self.assertIn("name", fields)
        self.assertIn("description", fields)
        self.assertNotIn("license", fields,
                         "the entry states a licence of its own — decided against, "
                         "because it would describe the package it does not carry")

    def test_it_is_small_enough_to_be_loaded_every_time(self):
        size = len(self.text.encode("utf-8"))
        self.assertLessEqual(size, MAX_ENTRY_BYTES,
                             f"the entry is {size} bytes: past the ceiling that keeps it "
                             f"loadable on every trigger. The long text belongs in "
                             f"INSTRUCTION.md, which is opened on demand.")

    def test_it_names_the_doors_a_host_could_not_otherwise_find(self):
        """The defect this door was blocked on. A runtime with no plugin
        mechanism reads this file and nothing else."""
        self.assertIn("scholion mcp", self.text,
                      "the entry does not name the tool server, so a host that reads only "
                      "this file never learns the door exists")
        self.assertIn("ouroboros_tools", self.text,
                      "nor the in-process module")

    def test_the_safety_rules_arrive_with_the_file(self):
        """The folder IS the whole installation, so a host that fetched only this
        must not be reasoning without them. They are inline, not linked."""
        self.assertRegex(self.text, r"(?im)^##\s+The rules that come before any answer")
        numbered = re.findall(r"(?m)^\d+\.\s+\*\*", self.text)
        self.assertGreaterEqual(len(numbered), 5,
                                "the rules section is a heading with nothing under it")

    def test_every_reference_is_reachable_without_the_folder_beside_it(self):
        """The defect this door would otherwise have carried.

        Copying the entry into a skills folder copies ONE file. The reference
        texts are not next to it, and the entry used to point at
        `reference/instruction.md` as if they were — a path that does not exist,
        which is worse than no pointer at all, because a model follows it and
        reports the file missing instead of asking for what it needs.

        So each is named twice: the file, for the bundle where it does sit there,
        and a command, for every other way in.
        """
        # The PARAGRAPH, not the line. Prose wraps at eighty columns, and asking
        # for the command on the same physical line as the path is a constraint
        # about typography rather than about the reader.
        paragraphs = re.split(r"\n\s*\n", self.text)
        for ref in re.findall(r"`reference/([a-z-]+)\.md`", self.text):
            with self.subTest(reference=ref):
                where = [par for par in paragraphs if f"reference/{ref}.md" in par]
                self.assertTrue(where, f"reference/{ref}.md vanished between two reads")
                self.assertTrue(any(re.search(r"`scholion [a-z]", par) for par in where),
                                f"reference/{ref}.md is pointed at with no command beside "
                                f"it — for a one-file install that path is not there")

    def test_those_commands_are_real(self):
        """Named after being tried, not before. Four of them are quoted in the
        entry, and a quoted command that does not exist teaches a model that this
        product is broken."""
        from scholion import cli
        parser = cli.build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)  # noqa: SLF001
        for cmd in set(re.findall(r"`scholion ([a-z][a-z-]*)", self.text)):
            with self.subTest(command=cmd):
                self.assertIn(cmd, commands, f"the entry tells a model to run "
                                             f"`scholion {cmd}`, which does not exist")


class TestTheEntryMeetsThePublishedFormat(unittest.TestCase):
    """The constraints of the Agent Skills specification, checked here.

    They are somebody else's rules, which is exactly why they are worth a test:
    a file that violates one is refused by a host with a message about YAML, and
    the person meets that instead of the product. The limits are quoted from
    agentskills.io/specification as read on 24.08.2026.
    """

    NAME_MAX = 64
    DESCRIPTION_MAX = 1024
    BODY_LINES_RECOMMENDED = 500

    def setUp(self):
        if ENTRY is None or not ENTRY.exists():
            self.skipTest("this build carries no skill entry")
        self.text = ENTRY.read_text(encoding="utf-8")
        self.front = self.text.split("---")[1]

    def _name(self):
        return re.search(r"^name:\s*(.+)$", self.front, re.M).group(1).strip()

    def _description(self):
        m = re.search(r"^description:\s*>-\n((?:\s{2,}.*\n)+)", self.front, re.M)
        if m:
            return " ".join(l.strip() for l in m.group(1).splitlines())
        return re.search(r"^description:\s*(.+)$", self.front, re.M).group(1).strip()

    def test_the_name_is_a_valid_slug(self):
        name = self._name()
        self.assertLessEqual(len(name), self.NAME_MAX)
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$",
                         "lowercase letters, digits and single hyphens; no leading, "
                         "trailing or doubled hyphen")

    def test_the_name_is_the_folder_the_instructions_tell_people_to_make(self):
        """The format requires the directory name and the `name` field to match,
        so the install line and the frontmatter are one claim, not two."""
        name = self._name()
        self.assertIn(f"~/.agents/skills/{name}", contract.AGENT_SKILLS_DIR + "/",
                      "the declared install path and the skill's own name disagree")

    def test_the_description_fits_the_limit(self):
        d = self._description()
        self.assertTrue(d, "the description is empty; a host would never surface the skill")
        self.assertLessEqual(len(d), self.DESCRIPTION_MAX,
                             f"the description is {len(d)} characters against a limit of "
                             f"{self.DESCRIPTION_MAX} — a host refuses the file, and the "
                             f"person meets a YAML error instead of this product")

    def test_the_body_stays_within_what_is_recommended(self):
        body = self.text.split("---", 2)[2]
        lines = len(body.splitlines())
        self.assertLessEqual(lines, self.BODY_LINES_RECOMMENDED,
                             f"the body is {lines} lines; past the recommended ceiling the "
                             f"reference material belongs in files opened on demand")

    def test_only_fields_the_format_defines_are_used(self):
        allowed = {"name", "description", "license", "compatibility",
                   "metadata", "allowed-tools"}
        used = set(re.findall(r"^([a-z-]+):", self.front, re.M))
        self.assertEqual(set(), used - allowed,
                         "the frontmatter carries fields the format does not define: "
                         + ", ".join(sorted(used - allowed)))


class TestTheBuildPutsTheSkillWhereAnInstallerLooks(unittest.TestCase):
    """`npx skills add owner/repo` reads a repository, not a package.

    It scans three levels: the root if it holds a SKILL.md, `skills/`, and the
    agent folders — the documented shape being `skills/<name>/SKILL.md`. None of
    those existed in the published repository, so the entry could be found only
    by the tool's fallback recursive search, at a path whose folder is called
    `skill` rather than `scholion`. The format requires those to match.

    Checked in the builder's source rather than by building: the suite does not
    build a package anywhere, and one full build to assert three lines would be
    the slowest test here by an order of magnitude. What is checked is that the
    builder still says it — the same shape as the other checks on this file.
    """

    SOURCE = support.ROOT / "src" / "tools" / "make_shareable.py"

    def setUp(self):
        if not self.SOURCE.exists():
            self.skipTest("this build does not carry the builder")
        self.src = self.SOURCE.read_text(encoding="utf-8")

    def test_the_builder_writes_the_folder_an_installer_scans_for(self):
        self.assertIn('"skills" / "scholion"', self.src,
                      "the build no longer writes skills/scholion/ — an installer reading "
                      "the repository finds the entry only by a fallback search, if at all")

    def test_the_folder_is_named_after_the_skill(self):
        """A rule of the format, and the reason the folder is not called `skill`."""
        if ENTRY is None or not ENTRY.exists():
            self.skipTest("this build carries no skill entry")
        name = re.search(r"^name:\s*(.+)$", ENTRY.read_text(encoding="utf-8").split("---")[1],
                         re.M).group(1).strip()
        self.assertIn(f'"skills" / "{name}"', self.src,
                      f"the folder the build writes and the skill's own name disagree; "
                      f"the format requires them to match ({name})")

    def test_only_the_entry_goes_there(self):
        """The licensing decision, not economy. What is published as a skill is
        the entry; the long instruction and the canon of rules stay with the
        package they are printed from, under their own licence. A folder that
        carried them would put one licence over two bodies of text."""
        block = self.src[self.src.index('skills_dir = shared / "skills"'):]
        block = block[:block.index("# ── 5)")]
        copies = re.findall(r"skills_dir / \"([A-Za-z._-]+)\"", block)
        self.assertEqual(["SKILL.md"], copies,
                         "something other than the entry is being published as the skill: "
                         + ", ".join(copies))

    def test_it_is_not_excluded_from_the_published_repository(self):
        """`claude-skill/` is deliberately ignored — it travels in the archive
        only. This one must NOT be: an installer fetches it from the repository,
        and a folder excluded from git does not exist for the purpose it was
        made for."""
        ignored = re.search(r'"claude-skill/\\n", encoding="utf-8"\)', self.src)
        self.assertIsNotNone(ignored, "the .gitignore the build writes has moved; check by hand")
        head = self.src[:ignored.end()]
        self.assertNotIn('"skills/\\n"', head,
                         "the build excludes skills/ from the published repository, which is "
                         "the one place an installer looks")


class TestWhatAccessSaysAboutTheDoorIsTrueOfTheFile(unittest.TestCase):
    """A door that describes itself is only as good as the description, so the
    description is compared with what it describes."""

    def setUp(self):
        self.door = contract.access()["doors"].get("agent_skills")
        if not self.door:
            self.skipTest("this build declares no skill-folder door")
        if ENTRY is None or not ENTRY.exists():
            self.skipTest("this build carries no skill entry")
        self.text = ENTRY.read_text(encoding="utf-8")

    def test_the_size_it_reports_is_the_size_of_the_file(self):
        self.assertEqual(len(self.text.encode("utf-8")), self.door["entry_bytes"])

    def test_the_claim_about_the_tool_server_is_checked_and_true(self):
        self.assertTrue(self.door["names_the_tool_server"],
                        "the build says the entry does not name the tool server — which is "
                        "the one thing this door exists to carry")

    def test_it_says_who_it_is_for(self):
        self.assertEqual("an agent", self.door["for"])
        self.assertTrue(self.door["agent_surface"])

    def test_the_path_it_names_is_the_shared_one(self):
        self.assertIn(contract.AGENT_SKILLS_DIR, self.door["how"])
        self.assertTrue(contract.AGENT_SKILLS_DIR.startswith("~/.agents/skills/"),
                        "the point of this door is the path several hosts read")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
