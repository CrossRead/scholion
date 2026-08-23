"""A number is never printed next to a word that has to agree with it.

Task 108. `limits` — the screen this project treats as its main argument — said
«1 markers are printed without a reference range». The plural machinery existed
and was in use (`count.*` with `.one/.few/.many`, chosen by `i18n.plural`); this
line simply did not go through it, and it was not alone: a walk over the
catalogue found twenty-three messages putting `{n}` in front of a plural noun.
In Russian it is worse, because there are three forms and «1 маркеров» reads as
carelessness about everything else on the screen.

Two ways out are both correct, and the rule admits both:

  * the phrase goes through a family — `count.rows`, or the whole sentence when
    the verb agrees too («1 строка не прошла» / «5 строк не прошли»);
  * or the number is moved off the noun — «commands: {n}» — which needs no
    grammar in any language, and is what several messages already did.

What is forbidden is the third thing: `{n}` immediately followed by a word.

The page has a `plural()` of its own, because it renders from the catalogue with
no server in the loop. Two implementations of one rule is a thing this project
otherwise refuses; here it is unavoidable, so the second guard below runs the
page's function under node and requires the two to choose the same form for
every n they can meet. Where node is absent the check skips rather than passing
quietly.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "scholion"
sys.path.insert(0, str(ROOT / "src"))

from scholion import i18n  # noqa: E402

#: `{n}` followed by whitespace and a letter — the shape that cannot be right
#: when the word agrees with the number, and the shape a walk can find.
_N_BEFORE_WORD = re.compile(r"\{n\}\s+\w", re.UNICODE)

#: What the walk still finds, frozen. **This list may only shrink.**
#:
#: Twenty-three messages were repaired when this guard was written — the ones
#: where the noun stood immediately after the number and the fix was plain. What
#: is left divides into three kinds, and none of them is repaired by a rule:
#:
#:   * a real agreement, needing an editorial decision per phrase («{n} давних»,
#:     «{n} подписей строк», "{n} of the 9 markers are missing");
#:   * the `(s)` hedge, which is what a catalogue writes when it has given up on
#:     forms — «{n} item(s)», «form(s)», «target(s)»;
#:   * and the walk's own false alarms, where the next word is not a noun at all
#:     ("{k} of {n} could be judged").
#:
#: Freezing them is the same move `check_language.py` makes with its remainder:
#: a large legacy class is not repaired by a commit, and the useful guarantee is
#: that it cannot GROW while it is being worked through. A key repaired here has
#: to leave this list, or the test fails — so the list cannot rot into a
#: permission slip.
_KNOWN = frozenset({
    "clinvar.low_confidence_note", "clinvar.shown", "ingest.not_ingested_more",
    "ingest_labs.reason_several_dates", "ingest_labs.reason_table_labels",
    "labs.near_more", "limits.date_unrecorded_what", "overview.stale_note",
    "overview.suggestions", "overview.suggestions_priority",
    "phenoage.cannot_missing", "phenoage.incomplete", "selfcheck.unreadable",
    "sources.refreshed", "web.focus.entry_saved", "web.goalgen.saved",
    "web.header.genome_gaps", "web.second.no_domain_issues",
    "web.second.no_drug_data", "web.second.no_drug_flags",
    "web.second.pgx_basis", "web.second.pgx_basis_none",
    "web.second.routine_elsewhere",
})


def _catalogue(lang: str) -> dict:
    ns: dict = {}
    exec(compile((SRC / "i18n" / f"{lang}.py").read_text(encoding="utf-8"),
                 f"{lang}.py", "exec"), ns)
    return max((v for v in ns.values() if isinstance(v, dict)), key=len)


class TestNoMessagePutsANumberInFrontOfAWord(unittest.TestCase):

    def _offenders(self, lang: str) -> set:
        out = set()
        for key, value in _catalogue(lang).items():
            if not isinstance(value, str) or key.endswith((".one", ".few", ".many")):
                continue                          # a family: that is the fix
            if _N_BEFORE_WORD.search(value):
                out.add(key)
        return out

    def test_nothing_new_puts_a_number_in_front_of_a_word(self):
        new = (self._offenders("en") | self._offenders("ru")) - _KNOWN
        self.assertEqual(set(), new,
                         "these print a number next to a word that must agree with it — "
                         "route them through a plural family, or move the number off the noun")

    def test_the_frozen_list_only_shrinks(self):
        # A key that has been repaired must leave the list. Otherwise the list
        # slowly becomes a permission slip instead of a record of what is left.
        still = self._offenders("en") | self._offenders("ru")
        stale = sorted(_KNOWN - still)
        self.assertEqual([], stale,
                         "these are fixed and still listed as known — remove them from _KNOWN")

    def test_the_walk_is_reading_something(self):
        # A scan that matched nothing at all would pass exactly as loudly.
        for lang in ("en", "ru"):
            cat = _catalogue(lang)
            self.assertGreater(len(cat), 500, f"{lang}: the catalogue did not load")
            families = {k.rsplit(".", 1)[0] for k in cat if k.endswith(".one")}
            self.assertGreater(len(families), 5, "no plural families found — the rule guards nothing")

    def test_every_family_is_complete_in_both_languages(self):
        en, ru = _catalogue("en"), _catalogue("ru")
        for cat, lang in ((en, "en"), (ru, "ru")):
            for key in [k for k in cat if k.endswith(".one")]:
                stem = key[: -len(".one")]
                for form in ("few", "many"):
                    with self.subTest(lang=lang, family=stem, form=form):
                        self.assertIn(f"{stem}.{form}", cat,
                                      "a family missing a form prints its own key at a person")

    def test_the_rule_catches_the_line_it_was_written_for(self):
        self.assertTrue(_N_BEFORE_WORD.search("{n} markers are printed"))
        self.assertTrue(_N_BEFORE_WORD.search("{n} показателей печатаются"))
        # And leaves the two honest shapes alone.
        self.assertFalse(_N_BEFORE_WORD.search("commands: {n}"))
        self.assertFalse(_N_BEFORE_WORD.search("threshold met {n} % of the time"))


class TestThePageChoosesTheSameFormAsThePackage(unittest.TestCase):
    """Two implementations of one rule, made to answer together."""

    NUMBERS = [0, 1, 2, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111, 121, 1002]

    def _page_forms(self, lang: str) -> list:
        node = shutil.which("node")
        if not node:                                          # pragma: no cover
            self.skipTest("node is not installed here")
        page = (SRC / "web" / "index.html").read_text(encoding="utf-8")
        body = re.search(r"function plural\(n,key,vars\)\{.*?\n\}", page, re.S)
        self.assertTrue(body, "the page has no plural() any more — this guard is stale")
        script = (f"const LANG={json.dumps(lang)};\n"
                  "const MSG={};\n"
                  "function t(key){ return key; }\n"
                  + body.group(0) + "\n"
                  f"console.log(JSON.stringify({json.dumps(self.NUMBERS)}"
                  ".map(n => plural(n,'x'))));")
        r = subprocess.run([node, "-e", script], capture_output=True, text=True,
                           timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(0, r.returncode, r.stderr)
        return [s.rsplit(".", 1)[1] for s in json.loads(r.stdout)]

    def _package_forms(self, lang: str) -> list:
        """Which FORM the package chooses — asked of the function itself.

        Not «which text comes out»: in English two of the three forms are the
        same string, so a comparison by text would call every plural «few» and
        agree with anything.
        """
        old_lang, old_t = i18n.lang(), i18n.t
        i18n.set_lang(lang)
        i18n.t = lambda key, /, **kw: key            # type: ignore[assignment]
        try:
            return [i18n.plural(n, "x").rsplit(".", 1)[1] for n in self.NUMBERS]
        finally:
            i18n.t = old_t                           # type: ignore[assignment]
            i18n.set_lang(old_lang)

    def test_english(self):
        self.assertEqual(self._package_forms("en"), self._page_forms("en"))

    def test_russian(self):
        self.assertEqual(self._package_forms("ru"), self._page_forms("ru"))


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
