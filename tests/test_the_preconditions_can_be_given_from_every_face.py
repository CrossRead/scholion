"""The five facts the engine cannot derive, and the doors a person can give them through.

Sex, year of birth, height, reference population and which wearable answers are
preconditions: the application will not invent any of them, and without them it
withholds. A dozen reference intervals are not shown, the age-banded rows of a
laboratory form cannot be read, there is no body-mass index, and a polygenic
percentile becomes a position inside somebody else's population.

They were settable from the command line only. Not by decision — the web view
that holds the form was written, and never put in the tab list. It had never been
in it, in the whole history of the file: a page of working code with no door, and
the command's own help still said «the page has always had this field; the command
had not». That is the shape this file tests for now, structurally, because a view
nobody can reach fails no test that calls its functions directly.

Two more defects were found in the same place and are pinned here. The age was
computed from `birth_year` alone, so a profile carrying `birth_date` — which is
what the demonstration writes and what an imported medical record writes —
reported no age at all while the file held a date. And the page compared the
stored sex against `male`, while the file is allowed to say `m`; a recorded sex
then showed as «—» and offered an empty box for a question already answered.

`none` for the wearable is an ANSWER. Without it, «I do not wear one» and «nobody
asked» are one blank field, and anything listing what the profile still needs
would ask a person with no watch about their watch for ever.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, engine, store, wearables

WEB = Path(engine.__file__).resolve().parent.parent / "web" / "index.html"

#: Every field `update_metric_profile` accepts. The faces are checked against
#: this rather than against a list typed in each test.
FIELDS = ("sex", "birth_year", "height_cm", "ancestry", "wearable_primary")

#: Fields the form deliberately does NOT offer — by name, with the reason, and
#: never silently.
#:
#: `ancestry` is the reference panel a percentile is computed against. Nobody
#: knows their own 1000 Genomes superpopulation in those terms, so a box asking
#: for one does not collect a fact; it collects a guess that nothing downstream
#: can tell from a measurement. It is determined while a genome is prepared and
#: shown here read-only, with where it came from. The command-line flag stays —
#: the public contract may not shrink — as an override rather than a question.
NOT_A_FIELD = {"ancestry"}
ASKED_FOR = tuple(f for f in FIELDS if f not in NOT_A_FIELD)


@contextmanager
def profile(initial=None):
    tmp = Path(tempfile.mkdtemp(prefix="preconditions-")).resolve()
    (tmp / "metrics.json").write_text(json.dumps({
        "profile": dict(initial or {}), "metrics": {}}), encoding="utf-8")
    old = os.environ.get("SCHOLION_PROFILE_DIR")
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp)
    core.reset_cache()
    try:
        yield tmp
    finally:
        if old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = old
        core.reset_cache()
        shutil.rmtree(tmp, ignore_errors=True)


def stored(tmp):
    return json.loads((tmp / "metrics.json").read_text(encoding="utf-8"))["profile"]


class TestTheWebHasADoorToTheseFields(unittest.TestCase):
    """Structural, and it has to be: every function of that view worked."""

    def setUp(self):
        if not WEB.exists():
            self.skipTest("this build carries no web page")
        self.src = WEB.read_text(encoding="utf-8")

    def test_every_view_the_page_defines_is_reachable(self):
        """The general rule rather than the one instance. A view that nothing
        mounts is dead weight at best and — as here — a capability the product
        believes it offers and does not."""
        defined = set(re.findall(r"async function (view[A-Za-z]+)\s*\(", self.src))
        tabs = self.src[self.src.index("const TABS=["):]
        tabs = tabs[:tabs.index("\n];")]          # the closing bracket of the LIST
        mounted = set(re.findall(r"(view[A-Za-z]+)\]", tabs))
        self.assertEqual(set(), defined - mounted,
                         "these views are defined and no tab reaches them: "
                         + ", ".join(sorted(defined - mounted)))

    def test_the_profile_tab_is_named_in_both_catalogues(self):
        from scholion import contract
        self.assertIn("web.tab.profile", self.src)
        self.assertEqual([], contract.check_i18n_keys())

    def test_the_form_offers_every_field_the_writer_accepts(self):
        """The parity rule, one level down from routes and commands: a field the
        core will store and no face can set is a field only its author knows
        about."""
        form = self.src[self.src.index("pf.innerHTML="):]
        form = form[:form.index("$('#mp-save'")]
        missing = [f for f in ASKED_FOR if f not in form and f.replace("_cm", "") not in form]
        self.assertEqual([], missing,
                         "the profile form does not offer: " + ", ".join(missing))

    def test_the_form_posts_all_of_them(self):
        call = self.src[self.src.index("post('/api/metrics/profile'"):]
        call = call[:call.index("\n")]
        for f in ASKED_FOR:
            with self.subTest(field=f):
                self.assertIn(f, call, f"{f} is in the form and never sent")
        for f in NOT_A_FIELD:
            with self.subTest(field=f):
                self.assertNotIn(f + ":", call,
                                 f"{f} is sent from the form — it is determined, not asked for")


class TestThePanelIsShownAndNotAskedFor(unittest.TestCase):
    """The question a person cannot answer is not put to them.

    Asking somebody for their superpopulation gets a guess, and a guess stored in
    the same field as a measurement is indistinguishable from one afterwards —
    while every polygenic percentile they are shown depends on it. Their own
    genome answers it, and that answer is a step of preparing a genome.
    """

    def setUp(self):
        if not WEB.exists():
            self.skipTest("this build carries no web page")
        self.src = WEB.read_text(encoding="utf-8")

    def test_the_page_shows_the_panel_with_where_it_came_from(self):
        for key in ("web.metrics.panel_label", "web.metrics.panel_from_genome",
                    "web.metrics.panel_stated", "web.metrics.panel_unknown"):
            self.assertIn(key, self.src, f"the page cannot say {key}")

    def test_the_page_has_no_box_to_guess_in(self):
        self.assertNotIn("mp-anc", self.src,
                         "the reference panel is a field again — it collects a guess")

    def test_the_genome_answers_it_when_nobody_overrode_it(self):
        with profile():
            self.assertEqual({"value": None, "source": None}, core.ancestry())
        with profile() as tmp:
            (tmp / "ancestry_check.json").write_text(json.dumps({
                "date": "2026-08-24", "verdict_superpop": "SAS",
                "posterior": {"SAS": 0.97}}), encoding="utf-8")
            core.reset_cache()
            got = core.ancestry()
            self.assertEqual("SAS", got["value"])
            self.assertEqual("genome", got["source"],
                             "a measured panel must be reported as measured")

    def test_a_deliberate_override_wins_and_says_so(self):
        with profile({"ancestry": "EUR"}) as tmp:
            (tmp / "ancestry_check.json").write_text(json.dumps({
                "verdict_superpop": "SAS", "posterior": {"SAS": 0.97}}), encoding="utf-8")
            core.reset_cache()
            got = core.ancestry()
            self.assertEqual("EUR", got["value"])
            self.assertEqual("stated", got["source"])

    def test_a_verdict_nobody_recognises_is_not_used(self):
        with profile() as tmp:
            (tmp / "ancestry_check.json").write_text(
                json.dumps({"verdict_superpop": "EURO"}), encoding="utf-8")
            core.reset_cache()
            self.assertIsNone(core.ancestry()["value"])

    def test_a_check_file_that_will_not_parse_is_not_a_crash(self):
        with profile() as tmp:
            (tmp / "ancestry_check.json").write_text("{ broken", encoding="utf-8")
            core.reset_cache()
            self.assertEqual({}, core.ancestry_check())
            self.assertIsNone(core.ancestry()["value"])


class TestNoFaceCarriesItsOwnListOfChoices(unittest.TestCase):

    def test_the_command_line_offers_what_the_build_can_read(self):
        from scholion import cli
        parser = cli.build_parser()
        prof = parser._subparsers._group_actions[0].choices["profile"]  # noqa: SLF001
        choices = {a.dest: a.choices for a in prof._actions if a.choices}  # noqa: SLF001
        self.assertEqual(set(core.ANCESTRIES), set(choices["ancestry"]),
                         "the command's populations and the core's have drifted apart. The flag "
                         "stays — the contract may not shrink — but it is an override, and the "
                         "page has no box for it")
        expected = {k["source"] for k in wearables.KINDS} | {core.NO_WEARABLE}
        self.assertEqual(expected, set(choices["wearable"]),
                         "the command's devices and the build's readers have drifted apart")

    def test_the_page_is_told_which_devices_exist_rather_than_guessing(self):
        with profile():
            self.assertEqual([k["source"] for k in wearables.KINDS],
                             engine.metrics_summary()["devices"])


class TestSayingThereIsNoWearableIsAnAnswer(unittest.TestCase):

    def test_an_unanswered_question_and_a_declared_absence_are_told_apart(self):
        with profile():
            self.assertIsNone(core.wearable_primary())
            self.assertFalse(core.wearable_answered())
        with profile({"wearable_primary": core.NO_WEARABLE}):
            self.assertIsNone(core.wearable_primary(),
                              "the sentinel leaked out where a device name belongs")
            self.assertTrue(core.wearable_answered(),
                            "a person who answered «I have none» would be asked again")

    def test_a_named_device_answers_as_before(self):
        with profile({"wearable_primary": "whoop"}):
            self.assertEqual("whoop", core.wearable_primary())
            self.assertTrue(core.wearable_answered())

    def test_the_absence_can_be_recorded_through_the_writer(self):
        with profile() as tmp:
            self.assertTrue(store.update_metric_profile(
                {"wearable_primary": core.NO_WEARABLE})["ok"])
            self.assertEqual(core.NO_WEARABLE, stored(tmp)["wearable_primary"])


class TestAValueThatCannotMeanAnythingIsRefused(unittest.TestCase):
    """It used to be stored. `--ancestry EURO` went in, and every polygenic
    percentile afterwards was computed against a reference population that does
    not exist — and printed WITHOUT the caveat about a default one, because a
    value was set."""

    def test_a_population_nobody_knows(self):
        with profile() as tmp:
            res = store.update_metric_profile({"ancestry": "EURO"})
            self.assertFalse(res["ok"])
            self.assertIn("EUR", res["error"], "the refusal does not say what is accepted")
            self.assertNotIn("ancestry", stored(tmp))

    def test_a_device_this_build_cannot_read(self):
        with profile() as tmp:
            self.assertFalse(store.update_metric_profile({"wearable_primary": "grmin"})["ok"])
            self.assertNotIn("wearable_primary", stored(tmp))

    def test_a_sex_nobody_recognises(self):
        with profile() as tmp:
            self.assertFalse(store.update_metric_profile({"sex": "yes"})["ok"])
            self.assertNotIn("sex", stored(tmp))

    def test_a_sex_that_is_recognised_is_stored_in_the_spelling_the_engine_reads(self):
        for given in ("m", "MALE", "муж"):
            with self.subTest(given=given):
                with profile() as tmp:
                    self.assertTrue(store.update_metric_profile({"sex": given})["ok"])
                    self.assertEqual("male", stored(tmp)["sex"])
                    self.assertEqual("male", core.profile_sex())

    def test_writing_one_field_does_not_rewrite_another(self):
        """A writer that edits what it was not asked about is a shape this
        project keeps finding. Setting a height must not restyle a sex recorded
        years ago."""
        with profile({"sex": "m", "birth_date": "1980-06-15"}) as tmp:
            store.update_metric_profile({"height_cm": 181})
            self.assertEqual("m", stored(tmp)["sex"], "the sex was rewritten by a height")
            self.assertEqual("1980-06-15", stored(tmp)["birth_date"])


class TestTheProfileIsShownAsItIsMeant(unittest.TestCase):

    def test_an_age_is_computed_from_whichever_birth_field_is_there(self):
        from datetime import date
        year = date.today().year
        with profile({"birth_year": year - 40}):
            self.assertEqual(40, engine.metrics_summary()["age"])
        with profile({"birth_date": f"{year - 40}-01-01"}):
            self.assertEqual(40, engine.metrics_summary()["age"],
                             "a profile holding a birth DATE reported no age at all")

    def test_a_birthday_still_to_come_this_year_is_not_counted(self):
        from datetime import date
        today = date.today()
        with profile({"birth_date": f"{today.year - 30}-12-31"}):
            expected = 29 if (today.month, today.day) < (12, 31) else 30
            self.assertEqual(expected, engine.metrics_summary()["age"])

    def test_a_birth_field_that_is_nonsense_is_no_age_rather_than_a_crash(self):
        for bad in ({"birth_date": "not a date"}, {"birth_year": "soon"}, {}):
            with self.subTest(bad=bad):
                with profile(bad):
                    self.assertIsNone(engine.metrics_summary()["age"])

    def test_the_sex_is_shown_through_the_one_recogniser(self):
        with profile({"sex": "m"}):
            self.assertEqual("male", engine.metrics_summary()["profile"]["sex"],
                             "a recorded sex would show as «—» and be asked for again")

    def test_the_view_does_not_change_the_file(self):
        with profile({"sex": "m"}) as tmp:
            engine.metrics_summary()
            self.assertEqual("m", stored(tmp)["sex"],
                             "reading the profile rewrote it")


class TestTheRecogniserIsOneFunction(unittest.TestCase):
    """The reader accepted six spellings and the writer accepted anything, so a
    seventh could be stored and then read back as «not set» — the profile would
    show a sex while every sex-specific interval went on being withheld."""

    def test_reading_and_writing_agree(self):
        for spelling in ("m", "male", "муж", "f", "female", "жен"):
            with self.subTest(spelling=spelling):
                self.assertIsNotNone(core.profile_sex_of(spelling))
        for nonsense in ("", None, "yes", "unknown", "1"):
            with self.subTest(nonsense=nonsense):
                self.assertIsNone(core.profile_sex_of(nonsense))

    def test_the_stored_reader_goes_through_it(self):
        src = Path(core.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "profile_sex")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "profile_sex_of"]
        self.assertTrue(calls, "profile_sex has its own copy of the spellings again")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
