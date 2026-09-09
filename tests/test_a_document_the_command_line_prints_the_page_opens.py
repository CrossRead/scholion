"""A document the command line can print, the page can open.

The product's own output names files: `limits` sends the reader to
PREPARING-THE-GENOME.md, the second opinion offers the clinician a page about
what this program is. They ship inside the package precisely because after
`pip install` there is nowhere else to read them — and until now the only way to
read one was `scholion doc <name>` at a terminal, which the person reading the
interface may not have open and may not have at all.

Three things are tested, and the second is the reason this file exists at all.

**Parity.** Every document in the build opens through the route. Not the one
the button points at — every one, because a list of names in a route is the
copy-of-an-enumeration defect this project keeps paying for.

**The name in a URL is not the name at a prompt.** `docs.path_of` was tolerant
about spelling — `DATA_LAYOUT`, `data-layout.md` and `data-layout` are one
request — and while a person typed it themselves that tolerance cost nothing.
A route hands it a string from a URL, and `../../../etc/passwd` composes a path
outside the package exactly as readily. The tolerance stays; the shape does not.

**What the renderer does not know survives as text.** It is not a Markdown
implementation and does not try to be. The failure that matters is not an
unstyled line — it is a line that disappears, because nobody proof-reads a
document they did not write against a source they cannot see.
"""
from __future__ import annotations

import re
import unittest

import support  # noqa: F401  — puts src/ on the import path

from scholion import docs, docpage


class TestEveryDocumentOpens(unittest.TestCase):

    def test_the_build_carries_documents_at_all(self):
        """Otherwise every assertion below is about an empty list."""
        self.assertGreaterEqual(len(docs.available()), 5, docs.available())

    def test_each_one_becomes_a_page(self):
        for name, _ in docs.available():
            with self.subTest(doc=name):
                html = docpage.page(name)
                self.assertTrue(html.startswith("<!doctype html>"))
                self.assertIn("</main>", html)

    def test_the_page_the_second_opinion_offers_is_one_of_them(self):
        """The button carries a name. A name in a page and a file on disk are two
        copies of one fact, and this is where they are compared."""
        from pathlib import Path
        from scholion import engine
        page = (Path(engine.__file__).resolve().parent.parent
                / "web" / "index.html").read_text(encoding="utf-8")
        offered = set(re.findall(r'href="/doc/([a-z0-9-]+)"', page))
        self.assertTrue(offered, "the page offers no document at all")
        have = {n for n, _ in docs.available()}
        self.assertEqual(set(), offered - have,
                         "the page offers a document this build does not carry: "
                         + ", ".join(sorted(offered - have)))

    def test_a_name_nobody_carries_gives_the_list_rather_than_an_error(self):
        html = docpage.page("no-such-document")
        self.assertIn("/doc/", html)
        for name, _ in docs.available():
            self.assertIn(f"/doc/{name}", html)


class TestTheNameIsOneFileName(unittest.TestCase):

    def test_the_spelling_stays_tolerant(self):
        self.assertIsNotNone(docs.path_of("for-clinicians"))
        self.assertIsNotNone(docs.path_of("FOR_CLINICIANS"))
        self.assertIsNotNone(docs.path_of("for-clinicians.md"))

    def test_a_path_is_refused_whatever_it_leads_to(self):
        for bad in ("../pyproject", "../../etc/passwd", "a/b", "/etc/passwd",
                    "..", ".", "", "   ", "./readme"):
            with self.subTest(name=bad):
                self.assertIsNone(docs.path_of(bad), f"{bad!r} resolved to a file")

    def test_the_refusal_is_not_merely_that_the_file_is_absent(self):
        """`../docs/readme` names a file that DOES exist. It is refused for its
        shape, which is the only reason that keeps holding when the tree moves."""
        self.assertIsNone(docs.path_of("../docs/readme"))


class TestNothingIsSilentlyDropped(unittest.TestCase):

    def test_every_line_of_prose_reaches_the_page(self):
        """Word for word, over the whole build: a renderer that quietly ate a
        paragraph would leave a document that reads as complete and is not."""
        for name, _ in docs.available():
            with self.subTest(doc=name):
                md = docs.path_of(name).read_text(encoding="utf-8")
                html = docpage.render(md)
                text = re.sub(r"<[^>]+>", " ", html)
                for line in md.split("\n"):
                    words = [w for w in re.findall(r"[A-Za-z\u0400-\u04FF]{6,}", line)][:1]
                    if words:
                        self.assertIn(words[0], text,
                                      f"{name}: a line vanished — {line[:60]!r}")

    def test_the_check_would_notice_a_dropped_line(self):
        """A renderer that returns everything makes the test above vacuous."""
        md = "# Title\n\nA paragraph with recognisable wording in it.\n"
        self.assertIn("recognisable", re.sub(r"<[^>]+>", " ", docpage.render(md)))
        self.assertNotIn("recognisable", re.sub(r"<[^>]+>", " ", docpage.render("# Title\n")))

    def test_nothing_in_a_document_can_become_a_tag(self):
        md = "A line with <script>alert(1)</script> and a & in it.\n"
        html = docpage.render(md)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_the_shapes_these_documents_use_are_rendered(self):
        md = ("# H\n\n## H2\n\ntext **bold** `code` [x](y)\n\n- a\n- b\n\n"
              "1. one\n2. two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
              "```\ncode block\n```\n\n---\n")
        h = docpage.render(md)
        for tag in ("<h1>", "<h2>", "<b>", "<code>", "<a href=", "<ul>", "<ol>",
                    "<table>", "<pre>", "<hr>"):
            with self.subTest(tag=tag):
                self.assertIn(tag, h)


if __name__ == "__main__":
    unittest.main()
