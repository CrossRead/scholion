"""Legal terms: the files are in place, the paths are real, the verbatim notices are not lost.

Licensing obligations are the only class of requirement in the project where a
mistake is not repaired by the next release: a package that shipped without a
LICENSE has already shipped without rights, and a verbatim LOINC notice lost
during the build has already been violated at the recipient's end. So what is
checked here is not "is it nicely written" but three things a machine can check:

  1. the legal files exist and are not empty;
  2. every path named in them really exists — an attribution that points at a
     non-existent file does not fulfil its function (this has already happened:
     the files were prepared for the package's future name and pointed at
     `src/scholion/`);
  3. the verbatim terms of the sources are present EXACTLY WHEN the data itself
     is used. The check goes from the fact in the repository to the text in
     NOTICE, and not the other way round: the LOINC codes appeared before the
     notice did, and only a test like this could have spotted it.
"""
import json
import re
import unittest
from pathlib import Path

import support

ROOT = support.ROOT
KNOWLEDGE = ROOT / "src" / "scholion" / "knowledge"
LEGAL_FILES = ["LICENSE", "LICENSE-DATA", "NOTICE", "ATTRIBUTION.md", "DISCLAIMER.md"]

# The verbatim wording from section 10(a) of the LOINC licence. A paraphrase will
# not do: the licence fixes exactly this text.
LOINC_REQUIRED = [
    "This material contains content from LOINC",
    "Regenstrief Institute",
    "http://loinc.org/license",
]


def _has_legal_files() -> bool:
    return all((ROOT / n).exists() for n in LEGAL_FILES)


@unittest.skipUnless(_has_legal_files(), "the legal files are not part of this build")
class TestLegalFiles(unittest.TestCase):

    def test_files_are_in_place_and_not_empty(self):
        for name in LEGAL_FILES:
            with self.subTest(file=name):
                p = ROOT / name
                self.assertTrue(p.exists(), f"{name} is missing")
                self.assertGreater(p.stat().st_size, 500, f"{name} is suspiciously short")

    def test_mentioned_paths_exist(self):
        """An attribution pointing at a non-existent file does not carry its function."""
        path_re = re.compile(r"(?:src|tests|docs)/[A-Za-z0-9_./-]+\.(?:json|py|md|sh)")
        for name in ("ATTRIBUTION.md", "NOTICE", "LICENSE-DATA"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for rel in sorted(set(path_re.findall(text))):
                with self.subTest(file=name, path=rel):
                    self.assertTrue((ROOT / rel).exists(),
                                    f"{name} points at {rel}, which is not in the repository")


    def test_readme_leads_to_the_terms(self):
        """The first thing the recipient reads is the README. If the licence and
        the caveat about the intended purpose are not visible from it, the files
        beside it do not exist as far as the reader is concerned."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in ("LICENSE", "DISCLAIMER.md", "ATTRIBUTION.md"):
            with self.subTest(file=name):
                self.assertIn(name, readme, f"the README does not link to {name}")

    def test_version_in_readme_matches_the_version_file(self):
        vf = ROOT / "VERSION"
        if not vf.exists():
            self.skipTest("there is no VERSION file")
        version = vf.read_text(encoding="utf-8").strip()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(version, readme,
                      f"the README declares the wrong version: VERSION says {version}")


@unittest.skipUnless(_has_legal_files(), "the legal files are not part of this build")
class TestVerbatimTerms(unittest.TestCase):

    def _notice(self) -> str:
        return (ROOT / "NOTICE").read_text(encoding="utf-8")

    def test_loinc_notice_is_present_if_the_codes_are(self):
        used = False
        for f in KNOWLEDGE.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:                                    # noqa: BLE001
                continue
            if re.search(r'"loinc"\s*:\s*"\d', json.dumps(data, ensure_ascii=False)):
                used = True
                break
        if not used:
            self.skipTest("LOINC codes are not used in the knowledge base")
        notice = self._notice()
        for fragment in LOINC_REQUIRED:
            self.assertIn(fragment, notice,
                          "the LOINC licence requires a VERBATIM notice in NOTICE; "
                          "a paraphrase or an abridgement will not do")

    def test_hagr_citation_is_present_if_longevitymap_is(self):
        if not (KNOWLEDGE / "longevitymap.json").exists():
            self.skipTest("longevitymap.json is not in this build")
        text = self._notice() + (ROOT / "ATTRIBUTION.md").read_text(encoding="utf-8")
        self.assertIn("Human Ageing Genomic Resources", text)
        self.assertIn("Creative Commons Attribution 3.0", text)


@unittest.skipUnless(_has_legal_files(), "the legal files are not part of this build")
class TestForbiddenData(unittest.TestCase):
    """The ATTRIBUTION statements about what the repository does NOT contain are checked by a machine.

    The claim "we do not store this" is worth exactly as much as the check for
    it: without one it lives until the first convenient occasion.
    """

    def test_atc_codes_are_not_stored(self):
        atc = re.compile(r'"[A-Z]\d{2}[A-Z]{2}\d{2}"')      # e.g. "C10AA05"
        for f in KNOWLEDGE.glob("*.json"):
            with self.subTest(file=f.name):
                self.assertIsNone(atc.search(f.read_text(encoding="utf-8")),
                                  "ATC codes must not be copied (the terms of the WHO centre) — "
                                  "they are fetched at runtime through RxClass")

    def test_pgs_model_weights_are_not_stored(self):
        p = KNOWLEDGE / "prs_models.json"
        if not p.exists():
            self.skipTest("there is no registry of models")
        data = json.loads(p.read_text(encoding="utf-8"))
        blob = json.dumps(data, ensure_ascii=False)
        for key in ('"effect_weight"', '"weight"', '"beta"', '"effect_allele_frequency"'):
            self.assertNotIn(key, blob,
                             "the PGS registry must hold identifiers only: some of the scores "
                             "come under CC BY-NC-ND and are incompatible with the repository")


class TestExecutableFiles(unittest.TestCase):
    """Scripts must run rather than answer "permission denied".

    The `+x` bit is lost when files are moved across a bridge, a web upload or
    archives that do not preserve permissions. For the recipient this is the very
    first command from the README — and the first impression of the project. The
    check is cheaper than the explanations.
    """


    def test_the_crossread_wrapper_runs(self):
        """`crossread` is a public entry point, not decoration.

        The command name deliberately differs from the project name: the noun
        holds the brand, the verb explains itself without documentation. What is
        checked is that the wrapper is in place, is executable and really starts
        the same core.
        """
        wrapper = ROOT / "bin" / "crossread"
        if not wrapper.exists():
            self.skipTest("the wrapper is not part of this build")
        self.assertTrue(wrapper.stat().st_mode & 0o111, "bin/crossread has no execute bit")
        import subprocess
        p = subprocess.run([str(wrapper), "--help"], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        self.assertIn("crossread", p.stdout, "the help names the wrong command")

    def test_the_execute_bit_is_in_place(self):
        candidates = [ROOT / "run_tests.sh"] + sorted(ROOT.glob("src/tools/*.sh")) \
            + sorted(ROOT.glob("src/tools/hooks/pre-*"))
        checked = 0
        for p in candidates:
            if not p.is_file():
                continue
            checked += 1
            with self.subTest(file=p.name):
                self.assertTrue(p.stat().st_mode & 0o111,
                                f"{p.name} has no execute bit: "
                                f"chmod +x {p.relative_to(ROOT)}")
        self.assertGreater(checked, 0, "not a single script was found — the check means nothing")


class TestOldName(unittest.TestCase):
    """The project's former name must not remain in what ships to the recipient.

    A rename is not caught by eye: the string survives in the least noticeable
    places. One such leftover cost dearly — the `.gitignore` of the public
    package went on excluding the profile directory under its FORMER name, which
    means the recipient's personal data in the folder with the new name was not
    excluded at all. The changelog and the private directories are excluded from
    the check: there the former name is legitimate — it is history.

    The word being searched for is itself assembled from pieces: otherwise the
    check finds its own text and fails on itself — that has already happened with
    the scan of the core for calls to models.
    """

    SEARCHED = "personal" + "doctor"

    # `.personal_patterns` holds the owner's own identifiers, is in `.gitignore`
    # and never ships. One of those identifiers is a folder path on their disk,
    # and that folder still carries the project's former name — renaming a
    # directory on somebody's machine is not this test's business, and the string
    # has to keep matching what is actually there or the privacy gate stops firing.
    HIDDEN = {"CHANGELOG.md", "CHANGELOG.private.md", ".personal_patterns"}
    DIRECTORIES = {".git", "_backups", "_to_delete", "__pycache__", "dist",
                   "profile", "genome", "reports", "work", ".cache", "demo",
                   "inbox", "kb"}

    def test_there_is_no_old_name(self):
        root = support.ROOT
        offenders = []
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in (
                    ".py", ".md", ".sh", ".json", ".toml", ".yml", ".yaml", ".html", ""):
                continue
            rel = f.relative_to(root)
            if set(rel.parts) & self.DIRECTORIES or rel.name in self.HIDDEN:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if self.SEARCHED in text.lower():
                offenders.append(str(rel))
        self.assertEqual(offenders, [], "the former name of the project is left in: " + ", ".join(offenders))




class TestCitationAndSecurity(unittest.TestCase):
    """The files an outsider reads: the citation and the vulnerability reporting channel.

    What is checked is not presence for the sake of a tick, but two concrete ways
    of going wrong. CITATION.cff holds the VERSION NUMBER — its fourth copy after
    VERSION, the README and the package metadata; an unchecked copy diverges from
    the original, and that has already happened. SECURITY.md is obliged to name a
    working channel: a security policy that sends a person nowhere is worse than
    its absence — it creates the appearance of a process.
    """

    def test_version_in_citation_matches_the_version_file(self):
        cff = ROOT / "CITATION.cff"
        vf = ROOT / "VERSION"
        if not cff.exists() or not vf.exists():
            self.skipTest("CITATION.cff is not part of this build")
        version = vf.read_text(encoding="utf-8").strip()
        text = cff.read_text(encoding="utf-8")
        m = re.search(r'^version:\s*"?([^"\s]+)"?', text, re.M)
        self.assertIsNotNone(m, "CITATION.cff has no version field")
        self.assertEqual(m.group(1), version,
                         f"CITATION.cff declares version {m.group(1)}, VERSION says {version}")

    def test_security_names_a_channel(self):
        sec = ROOT / "SECURITY.md"
        if not sec.exists():
            self.skipTest("SECURITY.md is not part of this build")
        text = sec.read_text(encoding="utf-8")
        self.assertIn("Report a vulnerability", text,
                      "SECURITY.md does not name a private reporting channel")
        self.assertNotIn("TODO", text, "an unfilled contact is left in SECURITY.md")

    def test_the_threat_model_does_not_promise_the_absence_of_network(self):
        """The claim "nothing leaves" is refuted by the application's own scan:
        the requests exist, they are explicit and they are listed. The document is
        obliged to name them rather than promise emptiness."""
        tm = ROOT / "THREAT_MODEL.md"
        if not tm.exists():
            self.skipTest("THREAT_MODEL.md is not part of this build")
        text = tm.read_text(encoding="utf-8")
        self.assertIn("rxnav.nlm.nih.gov", text,
                      "the threat model does not list the real addresses of the requests")
        self.assertIn("translate", text,
                      "the threat model keeps quiet about the translator the drug name goes to")


if __name__ == "__main__":
    unittest.main()
