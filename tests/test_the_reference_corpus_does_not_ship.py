"""Nothing of the reference test may travel inside the package.

Rule (1) of how the reference corpus is handled: it does not ship in any form —
not the files, not the scripts, not the protocol, not the method. Rules (2) to
(4) are held by a `.gitignore` and by habit. Rule (5) says this one must be held
by a machine, and until now it was the only rule of the five that was not.

Two things are looked for, and they are different in kind.

**A participant identifier.** The corpus is other people's data, published by
them under open consent — consent to publish THEIR data, not a licence for us to
republish it. An identifier next to a finding is the one thing that can never be
undone, and it reaches every recipient of the package at once.

**A path into the corpus, or the name of the stand.** Harmless to a reader and
fatal to the claim: a package that names where somebody's genomes are kept is a
package that has been built from a tree where they were, and the next accident
is a file rather than a string.

What travels is not listed here a second time — it is read out of the build
configuration, the same lists `check_published.py` uses and the build itself
obeys. A second list would drift, and the day it did this test would be about a
package that no longer exists.

The mutation check at the end is not decoration. A gate that cannot fail is
worse than no gate: it reports success either way, and the success is the part
people remember.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support

ROOT = support.ROOT

#: What must never appear in a file that ships. Each is paired with the reason,
#: because a pattern without one gets deleted by whoever meets it next.
#:
#: **The patterns are assembled from pieces, and so are the samples below.** The
#: first run of this file failed on the file itself: `tests/` travels in the
#: sdist, so a guard that spells out what it forbids ships exactly what it
#: forbids. Excluding itself from the scan was the other option and is a hole
#: somebody would widen later. Written this way the guard obeys its own rule,
#: which is the only version of it worth trusting.
_HU = "hu"
FORBIDDEN = (
    (re.compile(_HU + r"[0-9A-F]{6}\b"),
     "a Personal Genome Project participant identifier"),
    (re.compile(r"pgp[_-]cor" + "pus", re.I),
     "the name of the corpus builder"),
    (re.compile(r"pgp-hms\." + "org", re.I),
     "the address the corpus is fetched from"),
    (re.compile(r"PGP" + r"\s+" + "files"),
     "the folder the corpus lives in"),
    (re.compile(r"\bmk" + r"tbi\b", re.I),
     "a tool of the stand, which does not ship either"),
)

#: Binary and vendored assets are read as bytes and skipped: a false positive
#: inside minified CSS would be noise, and none of these is written by hand.
SKIP_SUFFIX = (".png", ".ico", ".svg", ".gz", ".bz2", ".zip", ".pyc", ".woff", ".woff2")
SKIP_NAME = ("pico.min.css", "chart.min.js")


def packaged_paths() -> list:
    """What travels, read out of `pyproject.toml` rather than listed again."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    out: set = set()
    m = re.search(r"^packages\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if m:
        out |= {p.strip().strip('"').strip("/") for p in m.group(1).split(",") if p.strip()}
    m = re.search(r"^include\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if m:
        for line in m.group(1).splitlines():
            line = line.split("#", 1)[0].strip().rstrip(",").strip()
            if line.startswith('"') and line.endswith('"'):
                out.add(line.strip('"').strip("/"))
    return sorted(p for p in out if p)


def shipped_files() -> list:
    """Everything that reaches a stranger — which is not the same as the wheel.

    The Hub manifest travels in a pull request and never touches the registry,
    so `packaged_paths()` does not know about it. It is read by hosts and by
    people all the same, and rule (1) says «in no form», not «in no artefact».
    """
    files = []
    for rel in packaged_paths() + ["ouroboros_plugin"]:
        base = ROOT / rel
        for f in (sorted(base.rglob("*")) if base.is_dir() else [base]):
            if not f.is_file() or "__pycache__" in str(f):
                continue
            if f.suffix.lower() in SKIP_SUFFIX or f.name in SKIP_NAME:
                continue
            files.append(f)
    return files


def offences(text: str) -> list:
    return [why for rx, why in FORBIDDEN if rx.search(text)]


class TestNothingOfTheStandTravels(unittest.TestCase):

    def test_the_package_names_no_participant_and_no_corpus_path(self):
        files = shipped_files()
        self.assertGreater(len(files), 50,
                           "almost nothing was scanned — the build configuration was "
                           "read wrongly, and a check that scans nothing always passes")
        bad = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for why in offences(text):
                bad.append(f"{f.relative_to(ROOT)}: {why}")
        self.assertEqual(bad, [], "the reference test reached the package")

    def test_the_check_can_actually_fail(self):
        """Each pattern is exercised on a string that must set it off.

        Written per pattern rather than once: a rule nobody proved can fire is a
        rule that quietly stopped matching after somebody tightened it.
        """
        samples = ("participants/" + _HU + "AB12CD" + "/wgs",
                   "pgp" + "_cor" + "pus.py",
                   "my." + "pgp-hms." + "org/user_file",
                   "Projects/" + "PGP " + "files/corpus",
                   "mk" + "tbi.py --budget=60")
        self.assertEqual(len(samples), len(FORBIDDEN))
        for sample, (rx, why) in zip(samples, FORBIDDEN):
            with self.subTest(reason=why):
                self.assertTrue(rx.search(sample), f"«{why}» no longer matches {sample!r}")

    def test_an_ordinary_sentence_is_not_an_offence(self):
        """The other half of a gate: it has to stay silent when nothing is wrong."""
        for innocent in ("a human genome", _HU + " is not an identifier",
                         "the corpus of published exports",
                         _HU + "ABCDE", _HU + "ABCDEFG"):
            with self.subTest(text=innocent):
                self.assertEqual(offences(innocent), [])


if __name__ == "__main__":
    unittest.main()
