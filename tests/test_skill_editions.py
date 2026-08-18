"""Two editions of the skill: the personal one and the shared one — and they must not mix.

The personal one (`src/skill/INSTRUCTION.owner.md`) accumulates around the owner's particular
investigation: his laboratories, his devices, the measured coverage of his genes.
The shared one (`share/skill/INSTRUCTION.md`), which travels into the anonymised
package, is obliged to contain only what is true for ANY user.

Mixing them is more dangerous than it seems. This is not a leak of personal data
— "the orange flag of the report" does not name a person. It is the substitution
of a general rule by a particular case: another user with a different laboratory
receives an instruction that does not apply to his data, and cannot notice this,
because the source of the qualification is not named in the text.

The check goes over a list of entities tied to one particular investigation. It
is deliberately short and concrete: a long list of general words would give false
positives and would be switched off by the first person it got in the way of.
"""
import importlib.util
import re
import unittest
from pathlib import Path

import support

OWNER_BEGIN, OWNER_END = "<!-- OWNER:BEGIN -->", "<!-- OWNER:END -->"

OWNER_EDITION = support.ROOT / "src" / "skill" / "INSTRUCTION.owner.md"
SHARED_EDITION = support.ROOT / "share" / "skill" / "INSTRUCTION.md"

# Entities of a single investigation: the names of laboratories and devices, the
# concrete measurements of one genome. They have no place in the shared edition.
OWNER_ONLY = [
    "Evogen", "эвоген",
    "88,4",              # the measured coverage of LDLR in one genome
    "307 полиморфизм",   # the size of the cross-check of one commercial report
    "18 генам из BAM",   # the size of one PyPGx run
    "владельц",          # in the shared edition the addressee is the user, not the project owner
    "1600 ноч",          # the volume of data accumulated by one person
    "2021–2022",         # his personal goal of "getting back in shape"
    "20.12.2025", "14.08.2026",   # dates from his archive and his sessions
    "garmin_export",     # the name of a folder in his installation
    "CGM_скриншоты",     # the same
    "labs.md",           # his working file, which is not in the data model
    "вешается на ярлык macOS",    # one OS as a mandatory path
]


@unittest.skipUnless(SHARED_EDITION.exists(), "the shared edition is not part of this build")
class TestSharedEdition(unittest.TestCase):

    def setUp(self):
        self.text = SHARED_EDITION.read_text(encoding="utf-8")

    def test_there_are_no_entities_of_a_single_investigation(self):
        for token in OWNER_ONLY:
            with self.subTest(entity=token):
                self.assertNotIn(token.lower(), self.text.lower(),
                                 f"«{token}» is a feature of one particular investigation; in the "
                                 f"shared edition it reads as a universal rule")

    def test_there_are_no_paths_to_someone_elses_machine(self):
        """Absolute paths and the names of somebody else's folders are the most
        noticeable sign that the text was written for one installation. An
        outsider will copy the command, get an error and decide that the tool is
        broken."""
        import re
        bad = re.findall(r'"/(?:Users|home)/[^"]+"|/path/to/[^\s`"]+', self.text)
        self.assertEqual(bad, [], f"paths from somebody else's machine: {bad[:5]}")

    def test_the_links_lead_to_existing_files(self):
        """The skill refers to files of the package. To an outsider a broken link
        looks like a lost feature rather than a typo."""
        import re
        root = support.ROOT
        refs = set(re.findall(r'`((?:src|docs|tests|knowledge)/[A-Za-z0-9_./-]+\.(?:py|sh|md|json))`',
                              self.text))
        missing = sorted(r for r in refs
                         if not (root / r).exists()
                         and not (root / "src" / "scholion" / r).exists())
        self.assertEqual(missing, [], f"links that lead nowhere: {missing}")

    def test_there_is_no_block_of_personal_qualifications(self):
        self.assertNotIn("Owner's personal refinements", self.text,
                         "the personal block seeped into the anonymised edition — "
                         "check sync_rules.py")

    def test_the_shared_edition_is_not_empty(self):
        # protection against "the test is green because the file has degenerated"
        self.assertGreater(len(self.text), 20_000)
        self.assertIn("ASSISTANT-RULES:BEGIN", self.text, "the block of rules was not carried over")


# In the SOURCE repository there are two editions and they lie at different
# paths. In the built package the path `src/skill/INSTRUCTION.owner.md` is occupied by the
# SHARED edition — the builder puts it there under the same name. So the personal
# edition can be checked by path only where `share/skill/INSTRUCTION.md` lies next to
# it: that is the only reliable sign of "we are in the source repository, not in
# the package".
IN_SOURCE_REPO = SHARED_EDITION.exists() and OWNER_EDITION.exists()


@unittest.skipUnless(IN_SOURCE_REPO, "the package holds a single edition — nothing to check")
class TestOwnerEdition(unittest.TestCase):

    def test_the_personal_qualifications_are_in_place(self):
        """The personal edition must HAVE them: otherwise the split degenerates
        into a loss of knowledge rather than into placing it where it belongs."""
        text = OWNER_EDITION.read_text(encoding="utf-8")
        self.assertIn("Owner's personal refinements", text,
                      "the personal block was not carried into the personal edition")

    def test_the_canon_explains_the_split(self):
        rules = (support.ROOT / "ASSISTANT-RULES.md")
        if not rules.exists():
            self.skipTest("the canon is not part of this build")
        text = rules.read_text(encoding="utf-8")
        self.assertIn("<!-- OWNER:BEGIN -->", text)
        self.assertIn("<!-- CORE:BEGIN -->", text)


class TestCopyInsideThePackage(unittest.TestCase):
    """The instruction is obliged to travel INSIDE the package.

    Only what lies inside `src/scholion` gets into the `pip install scholion`
    wheel. As long as the shared edition lay outside, the person got a command
    line without the instruction for the model after installing — even though the
    package description promises them a skill. The copies are mirrored by
    `sync_rules.py`; what is checked here is that the mirror has not fallen
    behind.
    """

    def setUp(self):
        self.root = support.ROOT
        self.shared = self.root / "share" / "skill" / "INSTRUCTION.md"
        if not self.shared.exists():
            self.skipTest("a built package: the source edition is not next to it")

    def test_the_copy_of_the_skill_matches_byte_for_byte(self):
        inside = self.root / "src" / "scholion" / "skill" / "INSTRUCTION.md"
        self.assertTrue(inside.exists(), "the package has no skill/SKILL.md — the wheel would ship without the instruction")
        self.assertEqual(inside.read_bytes(), self.shared.read_bytes(),
                         "the copy in the package has diverged from share/skill/INSTRUCTION.md: "
                         "fix it with `python3 src/tools/sync_rules.py --write`")

    def test_the_copy_of_the_rules_is_the_canon_without_the_personal_block(self):
        """The copy equals the canon WITHOUT the personal block — and not the canon in full.

        The previous edition of this test demanded a byte-for-byte match with the
        canon and therefore cemented the leak: the personal block of the canon,
        which declares itself uncopyable into the anonymised package, travelled
        into the wheel together with the rest of the text. The content audit did
        not catch it and could not — there is no name and no sample identifier
        there, only the peculiarities of one person's laboratory and devices.

        The lesson is general: a test that cements the current behaviour also
        cements the defect, if the behaviour was compared not against the rule but
        against itself.
        """
        canon = self.root / "ASSISTANT-RULES.md"
        inside = self.root / "src" / "scholion" / "skill" / "ASSISTANT-RULES.md"
        self.assertTrue(inside.exists(), "the package has no skill/ASSISTANT-RULES.md")

        text = canon.read_text(encoding="utf-8")
        i, j = text.find(OWNER_BEGIN), text.find(OWNER_END)
        self.assertTrue(i >= 0 and j > i, "the canon has no paired OWNER block")
        expected = (text[:i].rstrip() + "\n" + text[j + len(OWNER_END):].lstrip("\n"))

        self.assertEqual(inside.read_text(encoding="utf-8"), expected,
                         "the copy of the rules in the package has fallen behind the canon: "
                         "fix it with `python3 src/tools/sync_rules.py --write`")
        self.assertNotIn(OWNER_BEGIN, inside.read_text(encoding="utf-8"),
                         "the personal block of the canon travelled into the package")

    def test_the_skill_command_finds_the_file(self):
        """The path is counted from the module, not from the current directory:
        otherwise after installation the command looks for the file where the
        person launched it."""
        code, out, err = support.run(["skill", "--path"])
        self.assertEqual(code, 0, err)
        self.assertTrue(Path(out.strip()).is_file(), f"skill --path pointed nowhere: {out!r}")
        code, out, err = support.run(["skill", "--rules", "--path"])
        self.assertEqual(code, 0, err)
        self.assertTrue(Path(out.strip()).is_file(), f"skill --rules --path pointed nowhere: {out!r}")




class TestTheSharedSkillOnlyNamesFilesThatShip(unittest.TestCase):
    """An instruction to run a file the package does not carry is not an instruction.

    The skill is not prose about the product — it is an executable specification
    handed to a model, which will follow it literally. When it says
    `python3 src/ingest/cgm_join.py`, an assistant runs that, and on a recipient's
    copy there is no such file: the workflow dies mid-way with a shell error, in a
    tool whose entire argument is that it does not overstate what it can do.

    Three references had drifted this way by v2.22.0, and the reason each one
    survived is instructive. `brief_edit.py` was simply never on the builder's
    copy list. The two CGM loaders are on the builder's PRIVATE list *on purpose* —
    they are written against one monitoring service's export and one application's
    screenshots — so they exist in this repository, pass every "does the path
    exist" check run here, and are absent from every package ever built. A check
    that only asked whether the file exists in the source tree would have passed on
    all three.

    So this asks the question the recipient's copy asks: **will this path be
    there after the build?** Which means: it exists here, AND the builder does not
    hold it back. The owner's own edition is not checked — it is allowed to
    describe machinery that belongs to one machine, and that is what it is for.
    """

    #: A repository-relative path to a file, as the skill writes one in a command
    #: or in prose. Anchored to the directories the project actually has, so that
    #: a URL or a fragment of prose containing a slash is not mistaken for a path.
    PATH = re.compile(r'\b((?:src|docs|share|tests|bin|demo)/[A-Za-z0-9_./-]+'
                      r'\.(?:py|sh|md|json))')

    @classmethod
    def setUpClass(cls):
        cls.private = None
        spec = importlib.util.spec_from_file_location(
            "ms_private", support.ROOT / "src" / "tools" / "make_shareable.py")
        if spec and spec.loader:
            try:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cls.private = {p.replace("\\", "/") for p in mod.PRIVATE_DEFAULT}
            except Exception:                                     # noqa: BLE001
                cls.private = None

    def _paths(self, text):
        return sorted({m.group(1) for m in self.PATH.finditer(text)})

    def test_every_path_the_shared_edition_names_exists(self):
        if not SHARED_EDITION.exists():
            self.skipTest("the shared edition is not part of this build")
        missing = [p for p in self._paths(SHARED_EDITION.read_text(encoding="utf-8"))
                   if not (support.ROOT / p).exists()]
        self.assertEqual(missing, [], "the shared skill tells an assistant to run files that "
                                      "are not in the repository at all: " + ", ".join(missing))

    def test_no_path_it_names_is_held_back_by_the_builder(self):
        """The half a source-tree check cannot see.

        A file on the builder's private list exists here and never ships. Reading
        the list from the builder itself rather than restating it keeps the two
        from drifting: whatever the builder decides to hold back, this test asks
        about the same set.
        """
        if not SHARED_EDITION.exists():
            self.skipTest("the shared edition is not part of this build")
        if self.private is None:
            self.skipTest("the builder is not part of this build")
        withheld = [p for p in self._paths(SHARED_EDITION.read_text(encoding="utf-8"))
                    if p in self.private]
        self.assertEqual(withheld, [], "the shared skill names files the builder deliberately "
                                       "keeps out of the package, so they exist here and never "
                                       "reach a recipient: " + ", ".join(withheld))

    def test_the_owner_edition_is_free_to_name_whatever_it_likes(self):
        """The rule is about the SHARED edition, and the distinction is the point.

        The personal edition documents one machine — private loaders, local paths,
        a clinical key. Holding it to the package's contract would either strip it
        of what it is for or push those workflows into the shared edition, which is
        the failure this whole split exists to prevent.
        """
        if not (OWNER_EDITION.exists() and SHARED_EDITION.exists()):
            self.skipTest("both editions are needed for this comparison")
        if self.private is None:
            self.skipTest("the builder is not part of this build")
        owner_only = [p for p in self._paths(OWNER_EDITION.read_text(encoding="utf-8"))
                      if p in self.private]
        self.assertTrue(owner_only, "the personal edition no longer describes anything the "
                                    "package withholds — if that is deliberate the split has "
                                    "lost its purpose; if not, a private workflow has leaked "
                                    "into the shared edition")

    def test_the_check_reaches_the_paths_it_is_meant_to(self):
        """A regex that matched nothing would pass every assertion above in silence."""
        if not SHARED_EDITION.exists():
            self.skipTest("the shared edition is not part of this build")
        found = self._paths(SHARED_EDITION.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(found), 8,
                                f"only {len(found)} paths matched — the shared skill cites "
                                f"dozens, so the pattern has stopped seeing them")


if __name__ == "__main__":
    unittest.main()

# ──────────────────────────────────────────────────────────────────────────
# One name, one role
# ──────────────────────────────────────────────────────────────────────────
_SKIP_PARTS = {"_to_delete", "_backups", "archive", "dist", "node_modules", ".git"}


def _live(p) -> bool:
    return not (set(p.parts) & _SKIP_PARTS) and "._stale" not in str(p)


class TestOneNameMeansOneThing(unittest.TestCase):
    """`SKILL.md` is the entry. The long text is `INSTRUCTION.md`. Never the reverse.

    Until 16.08.2026 both roles were called `SKILL.md`, and the four files under
    that name ranged from 5 KB to 115 KB. Nothing failed: a wrong copy, a test
    comparing the wrong pair and a model loading seventy kilobytes where it
    expected five all produce a quietly wrong result instead of an error. That is
    the same class as `profile/` against `profile._stale/` and as a check that
    compares behaviour with itself.

    The size limit is not a style rule. It is what tells the two roles apart from
    the outside, without reading them.
    """

    ENTRY_CEILING = 12_000

    def test_every_skill_md_is_an_entry(self):
        for p in sorted(support.ROOT.rglob("SKILL.md")):
            if not _live(p):
                continue
            text = p.read_text(encoding="utf-8")
            rel = p.relative_to(support.ROOT)
            self.assertTrue(text.startswith("---"),
                            f"{rel}: an entry has to carry frontmatter — "
                            f"without it the runtime will not pick the skill up")
            self.assertLess(len(text), self.ENTRY_CEILING,
                            f"{rel}: {len(text)} bytes under the name SKILL.md — "
                            f"this is the instruction, not the entry. "
                            f"The long text is called INSTRUCTION.md")

    def test_no_instruction_pretends_to_be_an_entry(self):
        """The mirror rule: frontmatter in a long text makes it loadable by accident."""
        for p in sorted(support.ROOT.rglob("INSTRUCTION*.md")):
            if not _live(p):
                continue
            text = p.read_text(encoding="utf-8")
            self.assertFalse(text.startswith("---"),
                             f"{p.relative_to(support.ROOT)}: an instruction must not "
                             f"carry frontmatter — only the entry may")
