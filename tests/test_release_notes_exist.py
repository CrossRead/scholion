"""A version nobody described is not ready to be published.

The journal is the only place a person outside this repository reads what a
release did — the tag carries a commit and the package carries code, and neither
of them says anything. Until now the entry was written because somebody
remembered to write it, and «somebody remembered» is the failure mode this
project keeps finding in itself.

So the entry is a precondition of the version number, checked here and again in
`publish_share.sh` before anything is built. What cannot be checked mechanically
is whether the text is any good; what can be checked is that it exists, that it
is about THIS version, and that it is not a placeholder.
"""
from __future__ import annotations

import re
import unittest

import support

ROOT = support.ROOT


def section_for(version: str, text: str) -> str:
    """The `## vX.Y.Z` block, up to the next `## ` heading."""
    m = re.search(r"^## v" + re.escape(version) + r"\b.*?$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()


class TestTheVersionIsDescribed(unittest.TestCase):

    def setUp(self):
        vf = ROOT / "VERSION"
        if not vf.exists():
            self.skipTest("there is no VERSION file")
        self.version = vf.read_text(encoding="utf-8").strip()
        self.text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.section = section_for(self.version, self.text)

    def test_the_journal_has_an_entry_for_it(self):
        self.assertTrue(self.section,
                        f"VERSION says {self.version} and CHANGELOG.md has no "
                        f"`## v{self.version}` entry — the tag would be the only "
                        f"description of this release, and a tag describes nothing")

    def test_the_entry_is_not_a_placeholder(self):
        """Not a length contest — a floor under «I will write it later».

        Four hundred characters is about two sentences and a list. Anything
        shorter is a note to the author, not an entry for a reader.
        """
        self.assertGreater(len(self.section), 400,
                           "the entry is too short to tell anybody what changed")

    def test_the_heading_carries_a_date(self):
        m = re.search(r"^## v" + re.escape(self.version) + r" — (\d{2})\.(\d{2})\.(\d{4})\s*$",
                      self.text, re.M)
        self.assertIsNotNone(m, "the heading is `## vX.Y.Z — DD.MM.YYYY`; the date is "
                                "informative and the convention is what makes the "
                                "section findable by a script")

    #: Markers of an entry written for whoever was in the room. Each is a phrase
    #: that only means something to somebody with the repository open — and each
    #: has appeared in a draft of a real entry, which is why the list is checked
    #: rather than remembered.
    INTERNAL = (
        (r"\bthe author\b|\bthe owner\b|\bhis own\b|\bher own\b",
         "the person who wrote it — a release note is about the software"),
        (r"\b(task|issue|ticket)\s+\d+\b",
         "an internal number; say what changed, not where it was tracked"),
        (r"(?<![\w/.])(src|tests)/[\w./-]+",
         "a path inside this repository; name the command, not the file"),
        (r"\b[0-9a-f]{7,40}\b(?!\.)",
         "a commit hash"),
        (r"\bwe (tested|ran|found|decided|wrote)\b|\bour (machine|branch|run|tests)\b",
         "how the work was done rather than what it produced"),
    )

    def test_it_reads_as_a_release_note_and_not_as_a_diary(self):
        """The rule from the preamble, applied to the entry.

        What cannot be checked is whether the prose is good. What can be checked
        is that it does not lean on things only somebody with this repository
        open would understand — and every pattern below was in a draft once.
        """
        import re as _re
        found = []
        for pattern, why in self.INTERNAL:
            for m in _re.finditer(pattern, self.section, _re.I):
                line = self.section[:m.start()].count("\n") + 1
                found.append(f"line {line}: «{m.group(0)}» — {why}")
        self.assertEqual(found, [], "the entry is written for whoever was in the room")

    def test_a_reader_outside_this_repository_is_addressed(self):
        """The entry names commands, not internal symbols.

        A description that reads as a list of function names is a description
        for whoever was in the room. This is a weak check on purpose: it asks
        only that the entry mention the product's own surface at all.
        """
        self.assertRegex(self.section, r"`scholion \w",
                         "the entry mentions no command a person could run")


if __name__ == "__main__":
    unittest.main()
