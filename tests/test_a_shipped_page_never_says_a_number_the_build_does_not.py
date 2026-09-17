"""The numbers in the shipped pages are read from the build, not remembered.

On 13.09.2026 the README and the clinician's page were corrected from eleven
systems to twelve and from 945 genes to 1203 within hours of the base growing —
and both presentations, which say the same two numbers, were not: they went on
saying eleven and 945 while the build said otherwise. The footer of both had
stood at v0.4.6 through five releases, and the tool count at 30 when there were
32. Nothing checked any of it, because a number written into prose is a second
copy of a fact with nobody comparing the two.

This is that comparison. It does not write the text — it says where the text has
drifted from the build. Each rule below must match somewhere (a rule that matches
nothing is a gate that cannot fail), and every match must equal what the code
says.

Claims that no number can check — «chips are not read», «version 0.1.x», «nobody
outside has run it», all three false by the time somebody noticed — still need a
reader. This holds only the mechanical half.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion import ouroboros_tools

ROOT = Path(__file__).resolve().parents[1]
#: Each page by every path it is found at: the source tree first, then where the
#: sanitiser puts it in the built package. The package runs this suite too, and a
#: page that exists at neither path is a defect, not a skip.
PAGES = (("README.md",),
         ("docs/FOR-CLINICIANS.md", "src/scholion/docs/for-clinicians.md"),
         ("share/presentation.html", "docs/presentation.html"),
         ("share/presentation.ru.html", "docs/presentation.ru.html"),
         ("share/skill/INSTRUCTION.md", "claude-skill/INSTRUCTION.md",
          # the packaged copy: the one path the public repository commits
          "src/scholion/skill/INSTRUCTION.md"))


def _path(page: tuple) -> Path:
    for candidate in page:
        if (ROOT / candidate).is_file():
            return ROOT / candidate
    raise AssertionError(f"a shipped page is at none of its paths: {', '.join(page)}")


def _name(page: tuple) -> str:
    return _path(page).relative_to(ROOT).as_posix()

WORDS = {11: ("eleven", "одиннадцать"), 12: ("twelve", "двенадцать"),
         13: ("thirteen", "тринадцать"), 14: ("fourteen", "четырнадцать")}


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _lab_systems() -> int:
    return sum(1 for d in core._read_knowledge("radar_domains.json")["domains"]
               if d.get("source") == "labs")


def _genes() -> int:
    systems = core._read_knowledge("gencc_gene_disease.json")["systems"]
    return sum(len(v.get("genes") or {}) for v in systems.values())


def _positions() -> int:
    systems = core._read_knowledge("system_gene_panels.json")["systems"]
    return sum(len(v.get("positions") or []) for v in systems.values())


class TestThePagesAgreeWithTheBuild(unittest.TestCase):

    def _check(self, name, pattern, expected, least=1):
        """Every match of `pattern` in the shipped pages must read `expected`."""
        found = []
        for page in PAGES:
            text = _path(page).read_text(encoding="utf-8")
            for m in re.finditer(pattern, text):
                got = next(g for g in m.groups() if g)
                found.append((_name(page), m.group(0).strip(), got))
        self.assertGreaterEqual(
            len(found), least,
            f"{name}: the rule matched nothing — a gate that cannot fail is worse "
            f"than no gate; the pattern or the pages have moved")
        wrong = [f"{p}: «{whole}» — the build says {expected}"
                 for p, whole, got in found if str(got).replace(" ", "") != str(expected)]
        self.assertEqual([], wrong, f"{name}:\n  " + "\n  ".join(wrong))

    def test_the_version_in_the_footer_is_the_version_that_ships(self):
        self._check("version", r"· v(\d+\.\d+\.\d+) ·|build numbered (\d+\.\d+\.\d+)",
                    _version(), least=3)

    def test_the_number_of_tools_is_the_number_registered(self):
        self._check("tools", r"(?:registers|регистрирует)\s+(\d+)",
                    len(ouroboros_tools._TOOLS), least=3)

    def test_the_number_of_body_systems_is_the_number_of_domains(self):
        n = _lab_systems()
        self.assertIn(n, WORDS, f"no word is known for {n} systems — add it")
        for lang, pattern in (
                ("en", r"(?i)\b(eleven|twelve|thirteen|fourteen)\s+(?:body\s+)?systems\b"),
                ("ru", r"(?i)\b(одиннадцать|двенадцать|тринадцать|четырнадцать)\s+систем")):
            with self.subTest(language=lang):
                found = [(p, m.group(1).lower())
                         for p in PAGES
                         for m in re.finditer(pattern, _path(p).read_text(encoding="utf-8"))]
                self.assertTrue(found, f"{lang}: the rule matched nothing")
                word = WORDS[n][0 if lang == "en" else 1]
                wrong = [f"{p}: «{got}»" for p, got in found if got != word]
                self.assertEqual([], wrong,
                                 f"the build has {n} systems ({word}):\n  " + "\n  ".join(wrong))

    def test_the_number_of_genes_is_the_number_the_base_holds(self):
        self._check("genes", r"(\d[\d  ]*) genes across|(\d[\d  ]*) ген\w* на",
                    _genes(), least=3)

    def test_the_number_of_authored_positions_is_the_number_that_ships(self):
        self._check("positions", r"(\d+) (?:authored )?positions\b|(\d+) позици\w+",
                    _positions(), least=4)


class TestTheHubEntryAgreesWithTheBuild(unittest.TestCase):
    """The catalogue entry is a shipped page too, and nobody was comparing it.

    `ouroboros_plugin/hub/scholion/SKILL.md` is what the Ouroboros hub publishes:
    its frontmatter IS the catalogue row, and its prose says how many tools the
    skill registers. On 15.09.2026 the published row still read v0.4.7 and «30
    tools» seven releases later, and the copy in this tree had quietly lost
    `plugin_api: "2.0"` — a key 26 of the 35 hub skills declare and the published
    row still carried, so submitting this copy would have dropped it. The same
    class as the pages above: a second copy of a fact with nobody reading it.
    """

    ENTRY = "ouroboros_plugin/hub/scholion/SKILL.md"

    #: Exactly the keys the published row carries, frozen on purpose. A key that
    #: disappears costs the entry a field the hub reads; a key that appears
    #: unannounced has been reviewed by nobody.
    KEYS = ["name", "description", "version", "type", "runtime", "entry",
            "plugin_api", "os", "permissions", "env_from_settings",
            "install_specs", "when_to_use", "timeout_sec"]

    def setUp(self):
        path = ROOT / self.ENTRY
        if not path.is_file():
            self.skipTest("the hub package does not travel with the built package")
        self.text = path.read_text(encoding="utf-8")
        blocks = self.text.split("---", 2)
        self.assertEqual(3, len(blocks), "the entry carries no frontmatter block")
        self.front = blocks[1]

    def test_the_row_carries_every_key_the_catalogue_reads_and_no_other(self):
        keys = [m.group(1) for m in re.finditer(r"^([a-z_]+):", self.front, re.M)]
        self.assertEqual(self.KEYS, keys)

    def test_the_version_it_declares_is_the_version_that_ships(self):
        """Against `VERSION`, and not against the index — a correction made the
        day this class was written. The looser rule («any release that is on the
        index») was mine; the stricter one was already here, in
        `test_an_agent_can_ask_how_to_connect`, and it is the right one: this
        file is a source file describing THIS build, and publishing the row is a
        separate act that happens later. Opening a release therefore obliges
        updating this entry, exactly as it obliges the footers of the pages."""
        m = re.search(r"^version:\s*(\S+)\s*$", self.front, re.M)
        self.assertTrue(m, "the entry names no version")
        self.assertEqual(_version(), m.group(1))

    def test_the_version_it_declares_is_a_release_or_the_one_being_prepared(self):
        """The second half of the same fact: a row may describe the release being
        prepared, never a number nobody will ever be able to install."""
        published = json.loads((ROOT / "published.json").read_text(encoding="utf-8"))
        m = re.search(r"^version:\s*(\S+)\s*$", self.front, re.M)
        self.assertTrue(m.group(1) in published or m.group(1) == _version())

    def test_every_tool_count_it_prints_is_the_number_registered(self):
        found = re.findall(r"\b(\d+) tools\b", self.text)
        self.assertGreaterEqual(len(found), 2,
                                "the rule matched fewer places than the description and the "
                                "body — a gate that cannot fail is worse than no gate")
        self.assertEqual([str(len(ouroboros_tools._TOOLS))] * len(found), found)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
