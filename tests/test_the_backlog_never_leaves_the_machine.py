"""The backlog is the owner's alone: it never ships and it stays consistent.

Two guarantees, and they are different in kind, so they are two classes.

THE FIRST IS ABOUT PRIVACY and it runs everywhere, including inside the unpacked
sdist where `backlog/` does not exist — because that is exactly the state this
guard describes. What travels outside is the release record (CHANGELOG.md and
rule 10), and nothing else. The backlog itself carries PGP participant
identifiers next to their numbers, which rule (3) of the reference-corpus
handling forbids letting off the machine, and it carries the owner's own medical
detail besides.

The guarantee is STRUCTURAL rather than a maintained exclusion list: the sdist
`include`, the wheel `packages` and `make_shareable.build` each name what they
take. A directory nobody named cannot travel. This test pins that property so a
later "let's just ship the docs folder too" cannot quietly undo it.

THE SECOND IS ABOUT CONSISTENCY and it can only run where the backlog is, so it
skips with a reason elsewhere. It shells out to the backlog's own linter rather
than reimplementing it: the linter reads Russian prose, and a tool that reads
Russian prose must not live in a directory that ships (the language gate exists
for that), so it lives next to the backlog and this test calls it.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKLOG = REPO / "backlog"
PYPROJECT = REPO / "pyproject.toml"
SHAREABLE = REPO / "src" / "tools" / "make_shareable.py"

# The one word that must not appear in any allow-list. Kept as a constant so the
# assertion messages can name it and so a reader sees immediately what is banned.
NAME = "backlog"


def _read(path):
    with path.open(encoding="utf-8") as fh:
        return fh.read()


def _sdist_include(text):
    """The `include = [...]` list under [tool.hatch.build.targets.sdist].

    Parsed from the text rather than with tomllib: tomllib is 3.11+, and this
    suite promises to run on every Python the package promises.
    """
    head = text.find("[tool.hatch.build.targets.sdist]")
    if head < 0:
        return []
    start = text.find("include", head)
    if start < 0:
        return []
    open_bracket = text.find("[", start)
    close_bracket = text.find("]", open_bracket)
    body = text[open_bracket + 1:close_bracket]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        for piece in line.split(","):
            piece = piece.strip().strip('"').strip("'")
            if piece and not piece.startswith("#"):
                out.append(piece)
    return out


class TestTheBacklogDoesNotTravel(unittest.TestCase):
    def test_the_sdist_names_what_it_takes_and_does_not_name_the_backlog(self):
        include = _sdist_include(_read(PYPROJECT))
        # The self-check first: an empty list would pass every assertion below
        # while having examined nothing. Same shape as every other enumerator here.
        self.assertGreater(len(include), 5,
                           "the sdist include list came back near-empty — the "
                           "parser is looking at the wrong place, and a guard "
                           "that scanned nothing passes like a clean tree")
        self.assertIn("/src/scholion", include,
                      "the package itself is missing from the include list — "
                      "the parser found the wrong table")
        for entry in include:
            self.assertNotIn(NAME, entry.lower(),
                             f"the sdist would carry {entry!r}: the backlog is "
                             f"the owner's alone and never ships")

    def test_the_wheel_carries_the_package_only(self):
        text = _read(PYPROJECT)
        head = text.find("[tool.hatch.build.targets.wheel]")
        # -1 is "absent"; 0 is "the very first line of the file". Comparing with
        # zero passes the real tree only because the table happens not to sit at
        # the top — which is luck, not a check. Found by showing this guard a
        # tree it was supposed to reject.
        self.assertNotEqual(head, -1, "the wheel target is not declared at all")
        line = text[head:text.find("\n", text.find("packages", head))]
        self.assertIn("src/scholion", line, "the wheel no longer carries the package")
        self.assertNotIn(NAME, line.lower(),
                         "the wheel would carry the backlog")

    def test_the_shareable_tree_never_copies_it(self):
        # make_shareable.build() copies named directories. The check is on the
        # whole file rather than on build() alone: a helper added later would be
        # just as effective at carrying the folder out, and just as easy to miss.
        text = _read(SHAREABLE)
        self.assertIn("def build(", text, "make_shareable.py no longer has build()")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn(NAME, stripped.lower(),
                             f"make_shareable.py:{lineno} names the backlog: "
                             f"the public tree must not learn it exists")

    def test_no_backlog_file_matches_anything_the_sdist_takes(self):
        if not BACKLOG.is_dir():
            self.skipTest("no backlog/ in this tree — nothing could travel from it")
        include = _sdist_include(_read(PYPROJECT))
        files = [p for p in BACKLOG.rglob("*") if p.is_file()]
        self.assertTrue(files, "backlog/ exists but is empty — nothing was checked")
        prefixes = [e.strip("/").split("/")[0] for e in include]
        for path in files:
            top = path.relative_to(REPO).parts[0]
            self.assertNotIn(top, prefixes,
                             f"{path.relative_to(REPO)} sits under a directory the "
                             f"sdist takes")


class TestTheBacklogStaysConsistent(unittest.TestCase):
    def test_its_own_linter_passes(self):
        linter = BACKLOG / "lint.py"
        if not linter.is_file():
            self.skipTest("no backlog/lint.py in this tree — the backlog lives "
                          "on the owner's machine and travels nowhere")
        # stdin is closed explicitly: a run of this suite asks nobody anything
        # (task 90), and the AST guard over tests/ requires the argument to be
        # written rather than inherited.
        proc = subprocess.run([sys.executable, str(linter), str(BACKLOG)],
                              stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0,
                         "the backlog no longer agrees with itself:\n"
                         + proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
