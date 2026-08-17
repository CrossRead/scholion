"""The exception for the copyright line — and for it alone.

The content check (`src/tools/check_staged.py`) treats the owner's name as
personal data and stops the commit. For medical files that is right, for the
licence it is not: the authorship in NOTICE is published deliberately, Apache-2.0
requires it.

The concession is dangerous precisely because it is easy to widen "while we are
at it". That is why it is pinned down by a test from both sides: the copyright
line passes, everything else does not. The test contains no real name of the
owner: it works on an invented template, as befits a file that lies in a public
repository.
"""
import importlib.util
import re
import unittest
from pathlib import Path

import support

_TOOL = support.ROOT / "src" / "tools" / "check_staged.py"

if _TOOL.exists():
    _spec = importlib.util.spec_from_file_location("check_staged", _TOOL)
    check_staged = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(check_staged)
else:                                   # this tool is not part of the anonymised package
    check_staged = None

FAKE = "петров-водкин"                  # an invented "owner identifier"


@unittest.skipIf(check_staged is None, "check_staged.py is not part of this build")
class TestCopyrightException(unittest.TestCase):

    def _passes(self, text: str) -> bool:
        """True = the check lets the text through (treats it as an exception)."""
        return check_staged._only_in_copyright(text, "sub", FAKE)

    def test_the_copyright_line_passes(self):
        self.assertTrue(self._passes(f"Copyright 2026 {FAKE}"))
        self.assertTrue(self._passes(f"© 2026 {FAKE}"))
        self.assertTrue(self._passes(f"(c) 2026 {FAKE}, все права защищены"))

    def test_an_ordinary_line_is_blocked(self):
        self.assertFalse(self._passes(f"Автор — {FAKE}, пишите ему"),
                         "a name outside the copyright line is obliged to stop the commit")

    def test_a_copyright_with_an_email_is_blocked(self):
        self.assertFalse(self._passes(f"Copyright 2026 {FAKE} <mail@example.com>"),
                         "an e-mail in the copyright line is more than authorship")

    def test_a_second_occurrence_below_is_blocked(self):
        """One legitimate line does not justify the name in the rest of the file."""
        self.assertFalse(self._passes(f"Copyright 2026 {FAKE}\nСвязаться: {FAKE}"))

    def test_the_exception_knows_no_file_names(self):
        """The rule is about the content of the line, not about what the file is called.

        It is checked by the signature: the exception function receives neither a
        path nor a file name, so "I will rename it to LICENSE and smuggle it
        through" is impossible by construction rather than by agreement.
        """
        import inspect
        params = list(inspect.signature(check_staged._only_in_copyright).parameters)
        self.assertEqual(params, ["text", "kind", "pat"],
                         "an argument carrying a path or a file name seeped into the exception")

    def test_data_identifiers_are_not_shielded_by_the_copyright(self):
        for junk in ("WG0000000", "rs4149056", "01.02.2003"):
            with self.subTest(junk=junk):
                self.assertFalse(self._passes(f"Copyright 2026 {FAKE} {junk}"))


class TestHostList(unittest.TestCase):
    """Exactly six hosts are contacted outward, and all of them are listed by name.

    The privacy promise in the README is worded so as to be verifiable: "here is
    the full list, compare it with what the application finds in its own code".
    A promise of that kind lives exactly until the first new `urlopen` added in
    passing — after that the text lies, and the reader has no way of learning it.
    So the list is pinned down here: a new host fails the test and forces you to
    update the README first and only then add the request.

    None of these hosts receives profile data: what goes outward is the name of a
    drug or an rsID, that is, what the person has just typed in themselves.
    """

    EXPECTED = {
        "api.cpicpgx.org",              # gene↔drug pairs from CPIC
        "api.mymemory.translated.net",  # translation of the Russian drug name
        "mor.nlm.nih.gov",              # RxClass — the drug class
        "rest.ensembl.org",             # parsing an rsID
        "rxnav.nlm.nih.gov",            # RxNorm — normalising the name
        "translate.googleapis.com",     # the fallback translation
    }

    def test_the_list_matches(self):
        d = support.run_json(["assistant"])
        current = set(d["audit"]["network_hosts"])
        added = sorted(current - self.EXPECTED)
        vanished = sorted(self.EXPECTED - current)
        self.assertEqual(added, [], "an address appeared that the README.md does not list: "
                                    + ", ".join(added))
        self.assertEqual(vanished, [], "an address vanished — the promise in the README is now wider "
                                       "than reality: " + ", ".join(vanished))

    EXPECTED_INGEST = {
        "api.github.com",               # release checks for the tools
        "astral.sh",                    # installing uv
        "docs.astral.sh",
        "ftp.ensembl.org",              # reference genome and annotations
        "ftp.ncbi.nlm.nih.gov",         # ClinVar
        "genomics.senescence.info",     # LongevityMap (HAGR)
        "github.com",                   # sources of the build tools
        "hgdownload.soe.ucsc.edu",      # UCSC chain files
        "pypi.org",                     # installing the pipeline's python packages
    }

    def test_the_data_preparation_list_matches(self):
        """The genome build scripts pull gigabytes and run on the owner's machine.
        The inventory saw them, nothing pinned them: a new `curl` in
        `src/ingest/*.sh` reached the report and failed no test. The core list has
        been closed from the start — the asymmetry had no justification."""
        d = support.run_json(["assistant"])
        current = set(d["audit"].get("ingest_hosts") or [])
        if not current:
            self.skipTest("the data preparation scripts are not in this build")
        added = sorted(current - self.EXPECTED_INGEST)
        vanished = sorted(self.EXPECTED_INGEST - current)
        self.assertEqual(added, [], "a host appeared in the preparation scripts that is not "
                                    "on the list: " + ", ".join(added))
        self.assertEqual(vanished, [], "a host vanished from the scripts — the list promises "
                                       "more than exists: " + ", ".join(vanished))

    def test_the_core_does_not_go_to_language_models(self):
        d = support.run_json(["assistant"])
        self.assertEqual(d["audit"]["llm_hits"], [],
                         "a call to a language model appeared in the core — the application "
                         "promises the opposite on the «Assistant» tab")


if __name__ == "__main__":
    unittest.main()
