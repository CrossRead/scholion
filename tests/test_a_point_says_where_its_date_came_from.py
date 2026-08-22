"""Every lab point records where its date came from, and every writer says so.

Task 100. Task 84 taught the reader to take a date from three places: the page,
an «Ordered Date» that four lipid panels of the reference corpus print INSTEAD of
a draw date, and the file name. It printed a caveat for the last two — once, at
ingest, after which the caveat was gone and the point sat in the series
indistinguishable from one dated by the draw.

The project's own argument for refusing an ambiguous date is that a point filed
under the wrong month joins a series and moves a trend. Having refused the
ambiguous ones, it went on to accept the approximate ones in silence.

Two guards, and the second is the one that lasts. The first checks that the
field is written and validated. The second walks every call to `add_lab_point`
in the whole tree and requires `date_source=` outright — because the next writer
will be added by somebody who never read this file, and a default that quietly
says «unrecorded» is a safety net, not a habit to rely on.
"""
from __future__ import annotations

import ast
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import store  # noqa: E402


class TestTheWritersAllDeclareIt(unittest.TestCase):

    def test_every_call_in_the_tree_passes_date_source(self):
        missing = []
        for path in sorted((ROOT / "src").rglob("*.py")):
            if path.name == "store.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = (fn.attr if isinstance(fn, ast.Attribute)
                        else getattr(fn, "id", None))
                if name != "add_lab_point":
                    continue
                if not any(kw.arg == "date_source" for kw in node.keywords):
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual([], missing,
                         "these calls write a point without saying where its date came from")

    def test_the_vocabulary_is_closed(self):
        self.assertIn("form", store.DATE_SOURCES)
        self.assertIn("unrecorded", store.DATE_SOURCES)
        for value in store.DATE_APPROXIMATE:
            self.assertIn(value, store.DATE_SOURCES)
        # A value nobody declared is refused rather than stored and rendered.
        res = store.add_lab_point("glucose", "2020-01-01", 5.0,
                                  date_source="off_the_top_of_my_head")
        self.assertFalse(res.get("ok"))
        self.assertIn("off_the_top_of_my_head", res.get("error", ""))

    def test_an_omitted_source_is_not_silently_called_the_form(self):
        # The honest default is «we do not know», never «the form». Checked on
        # the function's own contract rather than through a profile, so it holds
        # even where no profile can be written.
        import inspect
        src = inspect.getsource(store.add_lab_point)
        self.assertIn('date_source or "unrecorded"', src)
        self.assertNotIn('date_source or "form"', src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
