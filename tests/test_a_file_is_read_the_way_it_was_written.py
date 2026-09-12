"""Text is opened with a stated encoding, not with whatever the machine assumes.

`open(path)` does not mean «read this file». It means «read this file in the
encoding of this machine's locale» — UTF-8 on the two platforms this was built
on, `cp1251` or `cp1252` on a Windows one. A genotype table, a cached answer, a
laboratory export written as UTF-8 and read back through `cp1251` does not raise
anything: it decodes, and the characters come out wrong. Where the call also
passes `errors="replace"` — several of them did — the wrongness is silent by
construction.

That is the worst shape a defect can take here: the program keeps answering, and
its answers are about a file it misread. Python's own `-X warn_default_encoding`
finds such a call only when a test happens to EXECUTE it; six of the seventeen
that existed were never reached by the suite. So the question is asked of the
source instead, by walking it — the class, not the instances.

What is accepted is listed below, each with a reason. The list is short on
purpose: a growing allowlist is how this kind of gate stops meaning anything.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import support

ROOT = support.ROOT

#: Calls that take an `encoding` and silently default it when not given.
WATCHED = {"open", "read_text", "write_text", "TextIOWrapper"}

#: Where the question is asked. `src/scholion` is the package a person installs
#: and `tests` runs inside the published artefact, so both must be portable.
#: `src/tools` is the build-and-check apparatus, run where the package is BUILT.
TREES = ("src/scholion", "tests", "src/tools")

#: Data preparation is deliberately outside the walk: those scripts drive
#: `bwa`, `samtools` and `mosdepth` over a whole genome and are documented as
#: needing a Unix machine, so a promise about their portability would be false.
#: The two of them a COMMAND reaches — the wearable loaders — are inside it.
ALSO = ("src/ingest/ingest_garmin.py", "src/ingest/ingest_whoop.py")

#: Accepted places, with the reason each is not a defect. A path here is not
#: «ignore this file» — it is one call, at one line, that somebody looked at.
ACCEPTED = {
    # Not a file at all: `urllib`'s opener, reached through a call rather than a
    # name, so the walk cannot see what it is. `.open(request)` here returns an
    # HTTP response, which has no encoding to state.
    "src/scholion/net.py:239",
    # The same opener, in the GenCC fetcher: a HEAD and a GET on an HTTP
    # response — bytes with a header, no text encoding to state. The bytes are
    # decoded once, later, with the encoding named at that call.
    "src/tools/fetch_gencc.py:162",
    "src/tools/fetch_gencc.py:180",
    # HTTP openers, not text files: `encoding=` was pasted onto these three on
    # 0.4.9 to satisfy this test, and the fetcher then crashed on its first
    # request (TypeError) — found 13.09.2026, the first time it was run since.
    "src/tools/fetch_demo_genome.py:135",
    "src/tools/fetch_demo_genome.py:176",
    "src/tools/fetch_demo_genome.py:197",
}


#: What a file mode looks like: `r`, `rb`, `w+`, `xt`. Matched as a shape rather
#: than by position, because the mode sits in a different argument depending on
#: which `open` it is — `open(path, "rb")` puts it second, `path.open("rb")` puts
#: it first, and `gzip.open(path, "rb")` looks like the second while being
#: written like the first. Reading only one position was what made the first
#: draft of this walk report eleven files that were already correct.
_MODE = re.compile(r"^[rwxa][bt+]*$|^[bt+]*[rwxa][bt+]*$")


def _binary(node: ast.Call) -> bool:
    """Is the mode a binary one? Then there is no encoding to state."""
    for a in node.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                and _MODE.match(a.value):
            return "b" in a.value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return "b" in str(kw.value.value)
    return False


#: Objects whose `.open()` is not the text `open()` at all: an archive member, a
#: URL, a PDF. Named rather than pattern-matched, so a new one has to be thought
#: about instead of slipping through.
NOT_A_FILE = {"zipfile", "tarfile", "zf", "archive", "pdfplumber", "webbrowser",
              "os", "socket", "urllib", "opener", "_diag_opener"}


def offenders(tree_root: Path, rel: str):
    out = []
    try:
        src = tree_root.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    try:
        node_tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(node_tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name not in WATCHED:
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) \
                and fn.value.id in NOT_A_FILE:
            continue
        if _binary(node):
            continue
        out.append(f"{rel}:{node.lineno}")
    return out


def walk_the_trees():
    found = []
    for tree in TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            found += offenders(p, p.relative_to(ROOT).as_posix())
    for extra in ALSO:
        p = ROOT / extra
        if p.exists():
            found += offenders(p, extra)
    return found


class TestNothingReadsTextByGuesswork(unittest.TestCase):

    def test_every_text_open_states_its_encoding(self):
        found = set(walk_the_trees())
        unexpected = sorted(found - set(ACCEPTED))
        self.assertEqual(unexpected, [],
                         "these read or write text in whatever encoding the "
                         "machine happens to use — on a Windows machine that is "
                         "cp1251/cp1252, and the file was written as UTF-8. Add "
                         "`encoding=\"utf-8\"`, or record the place in ACCEPTED "
                         "with the reason it is not a defect.")

    def test_the_accepted_list_has_not_gone_stale(self):
        """An entry that no longer matches anything is a claim about code that
        has moved. Left there, it silently accepts a DIFFERENT line later."""
        found = set(walk_the_trees())
        # A file that does not ship — `fetch_demo_genome.py` stays in the
        # source tree — cannot be stale in the package: the claim is about a
        # line that is simply not here. The source tree still checks it.
        here = {e for e in ACCEPTED if (ROOT / e.split(":")[0]).exists()}
        stale = sorted(here - found)
        self.assertEqual(stale, [], "accepted places that no longer exist")


class TestTheWalkCanActuallyFind(unittest.TestCase):
    """A walk that finds nothing proves nothing until it is shown a real one."""

    def test_it_reports_an_encodingless_open(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.py"
            p.write_text("def f(x):\n    return open(x).read()\n", encoding="utf-8")
            self.assertEqual(offenders(p, "sample.py"), ["sample.py:2"])

    def test_it_leaves_a_stated_one_alone(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.py"
            p.write_text('def f(x):\n    return open(x, encoding="utf-8").read()\n',
                         encoding="utf-8")
            self.assertEqual(offenders(p, "sample.py"), [])

    def test_a_binary_open_is_not_an_offence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.py"
            p.write_text('import pathlib\n'
                         'def f(x):\n'
                         '    return open(x, "rb").read()\n'
                         'def g(p):\n'
                         '    return p.open("rb").read()\n', encoding="utf-8")
            self.assertEqual(offenders(p, "sample.py"), [])


if __name__ == "__main__":
    unittest.main()
