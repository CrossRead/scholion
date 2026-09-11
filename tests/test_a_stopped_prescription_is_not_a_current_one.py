"""What the person is taking NOW, asked instead of assumed.

Found on a real question rather than by a test. A physician replaced a pulse
course of an azole with a single tablet, and the whole point of the change was
that the statin had left the scheme that same day — so the azole × statin pair,
which had been the reason to watch the course for six weeks, no longer existed.
The engine printed the red line anyway: «↑ statin concentration, risk of
myopathy», about an entry whose status in the file read `not_in_scheme_2026-09-10`.
Beside it came a second warning, about a probiotic paused six weeks earlier.

Nothing was broken. Nothing had ever asked: `medication_names()` returned every
name in the file, and every comparison — interactions, classes, the laboratory
layer, the limitations — ran against all of them. A drug the physician stopped
carried exactly as much weight as one taken this morning.

Three things are held here. A status decides, and it decides by a WHITE list, so
a value nobody taught this code about is not silently current. An entry with no
status at all is treated as current, because these predate the field and reading
them as stopped would delete real prescriptions from every check at once —
silence where a warning belongs is the worse mistake. And what was left out is
named in the answer: a red line that disappears because a drug was stopped and a
red line nobody computed look identical on the page.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import pgx


def med(name, status=..., **kw):
    m = {"name": name}
    if status is not ...:
        m["status"] = status
    m.update(kw)
    return m


class _Profile(unittest.TestCase):
    """A profile whose prescription file this test writes."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._env = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir)
        core.medications_json.cache_clear() if hasattr(core.medications_json, "cache_clear") else None

    def tearDown(self):
        if self._env is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._env
        core.medications_json.cache_clear() if hasattr(core.medications_json, "cache_clear") else None

    def write(self, *meds):
        (self.dir / "medications.json").write_text(
            json.dumps({"medications": list(meds)}, ensure_ascii=False), encoding="utf-8")
        if hasattr(core.medications_json, "cache_clear"):
            core.medications_json.cache_clear()


class TestWhichStatusesCount(unittest.TestCase):

    def test_the_three_the_profile_writes_are_current(self):
        for status in ("active", "active_new", "active_self"):
            with self.subTest(status=status):
                self.assertTrue(core.is_active_medication({"name": "x", "status": status}))

    def test_stopped_and_paused_are_not(self):
        for status in ("paused", "not_in_scheme_2026-09-10", "historical", "cancelled"):
            with self.subTest(status=status):
                self.assertFalse(core.is_active_medication({"name": "x", "status": status}))

    def test_a_word_nobody_taught_this_code_is_not_current_by_default(self):
        """A white list, on purpose: the failure mode of a black one is that a new
        status invented next year quietly means «still taking it»."""
        self.assertFalse(core.is_active_medication({"name": "x", "status": "on_hold_until_may"}))

    def test_an_entry_written_before_the_field_existed_is_current(self):
        """The other direction of the same care. Reading these as stopped would
        delete a real prescription from every check at once."""
        self.assertTrue(core.is_active_medication({"name": "x"}))
        self.assertTrue(core.is_active_medication({"name": "x", "status": ""}))


class TestWhatTheComparisonUses(_Profile):

    def test_a_stopped_drug_is_not_among_the_names(self):
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10"),
                   med("omeprazole", "active"))
        self.assertEqual(core.medication_names(), ["omeprazole"])

    def test_a_paused_drug_is_not_either(self):
        self.write(med("saccharomyces boulardii", "paused"), med("omeprazole", "active"))
        self.assertNotIn("saccharomyces boulardii", core.medication_names())

    def test_the_file_keeps_them_and_names_them(self):
        """They are excluded from the comparison, not deleted from the record."""
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10"), med("omeprazole", "active"))
        self.assertEqual([m["name"] for m in core.inactive_medications()], ["atorvastatin"])
        self.assertEqual([m["name"] for m in core.active_medications()], ["omeprazole"])

    def test_entries_with_no_status_are_listed_as_such(self):
        self.write(med("atorvastatin"), med("omeprazole", "active"))
        self.assertEqual([m["name"] for m in core.medications_without_status()], ["atorvastatin"])


class TestTheInteractionCheck(_Profile):

    def test_a_stopped_statin_produces_no_interaction(self):
        """The case as it happened: the pair the warning was about had ended."""
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10"))
        r = pgx.check_interactions("fluconazole")
        if r.get("status") != "ok":
            self.skipTest("the drug dictionary does not classify this pair in this build")
        self.assertEqual(r["count"], 0, r.get("interactions"))

    def test_the_same_statin_taken_now_still_produces_one(self):
        """The half that must not be lost while fixing the other half."""
        self.write(med("atorvastatin", "active"))
        r = pgx.check_interactions("fluconazole")
        if r.get("status") != "ok":
            self.skipTest("the drug dictionary does not classify this pair in this build")
        self.assertGreaterEqual(r["count"], 1,
                                "a current statin against an azole is the interaction this layer exists for")

    def test_what_was_left_out_travels_with_the_answer(self):
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10"),
                   med("saccharomyces boulardii", "paused"),
                   med("omeprazole", "active"))
        r = pgx.check_interactions("fluconazole")
        if r.get("status") != "ok":
            self.skipTest("the drug dictionary does not classify this drug in this build")
        excluded = {e["name"]: e["status"] for e in r["baseline"]["excluded"]}
        self.assertEqual(set(excluded), {"atorvastatin", "saccharomyces boulardii"})
        self.assertEqual(excluded["atorvastatin"], "not_in_scheme_2026-09-10")

    def test_an_entry_with_no_status_is_counted_and_declared(self):
        self.write(med("atorvastatin"))
        r = pgx.check_interactions("fluconazole")
        if r.get("status") != "ok":
            self.skipTest("the drug dictionary does not classify this drug in this build")
        self.assertEqual(r["baseline"]["status_not_recorded"], ["atorvastatin"])

    def test_both_sentences_exist_in_both_languages(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for key in ("prescription.excluded_from_check", "prescription.status_not_recorded"):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn("⟦", _t(key, names="x"))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


class TestASafetyFlagIsNotFilteredByStatus(_Profile):
    """A flag is a documented EVENT — a reaction, an intolerance, a complication —
    and an event does not stop having happened when the drug is stopped. Filtering
    it would delete the reason a drug was stopped at the moment somebody is
    offered it again."""

    def test_a_flag_on_a_stopped_drug_still_shows(self):
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10",
                       safety_flags=[{"kind": "red_flag", "text": "myopathy in 2024"}]))
        flags = pgx._own_safety_flags("atorvastatin")
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["medication"], "atorvastatin")


class TestACourseIsCurrentAndOneDictionaryDecides(unittest.TestCase):
    """The draw checklist carried a dictionary of its own since 1.0.0 —
    `active` and `course` — while the interaction check accepted `active`
    alone. A pulse course was current for one reader of the file and absent
    for the other. One dictionary, in core; the checklist reads it."""

    def test_a_pulse_course_is_current(self):
        self.assertTrue(core.is_active_medication({"name": "x", "status": "course"}))
        self.assertTrue(core.is_active_medication({"name": "x", "status": "course_2026-09"}))

    def test_a_postponed_course_is_not_current_by_its_spelling(self):
        self.assertFalse(core.is_active_medication({"name": "x", "status": "course_postponed"}))

    def test_the_checklist_reads_the_dictionary_from_core(self):
        import importlib.util
        from pathlib import Path
        src = Path(core.__file__).resolve().parents[1] / "ingest" / "draw_checklist.py"
        spec = importlib.util.spec_from_file_location("draw_checklist_under_test", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIs(mod.DEFERRED, core.DEFERRED_STATUSES)
        self.assertFalse(hasattr(mod, "ACTIVE_PREFIXES"),
                         "the checklist grew a dictionary of its own again")
        self.assertIn("course", core.ACTIVE_STATUS_PREFIXES)


class TestAStatusCanBeWrittenAndSurvivesAReAdd(_Profile):
    """No writer could record a status: the command and the page wrote
    `{name, dose, note}`, so for anyone not editing the JSON by hand every
    entry was «no status recorded». And re-adding a name replaced the entry
    whole — a stopped drug added again for its dose came back current, with its
    start date and monitoring gone, and nothing said so."""

    def setUp(self):
        super().setUp()
        from scholion import store
        self.store = store
        self.write()

    def read(self):
        data = json.loads((self.dir / "medications.json").read_text(encoding="utf-8"))
        return {m["name"]: m for m in data["medications"]}

    def test_a_status_given_is_written(self):
        self.store.add_medication("atorvastatin", "20 mg", status="stopped", subject="owner")
        self.assertEqual("stopped", self.read()["atorvastatin"]["status"])

    def test_no_status_given_is_no_status_recorded(self):
        self.store.add_medication("atorvastatin", "20 mg", subject="owner")
        self.assertNotIn("status", self.read()["atorvastatin"])

    def test_a_re_add_keeps_what_it_was_not_given(self):
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10", dose="10 mg",
                       start_date="2024-01-01", monitoring=["alt"]))
        r = self.store.add_medication("atorvastatin", "20 mg", subject="owner")
        m = self.read()["atorvastatin"]
        self.assertEqual("20 mg", m["dose"])
        self.assertEqual("not_in_scheme_2026-09-10", m["status"],
                         "a re-add for the dose made a stopped drug current")
        self.assertEqual("2024-01-01", m["start_date"])
        self.assertEqual(["alt"], m["monitoring"])
        self.assertTrue(r["updated"])
        self.assertEqual("atorvastatin", r["replaced"])
        self.assertIn("status", r["kept"])

    def test_a_re_add_with_a_status_changes_it(self):
        self.write(med("atorvastatin", "paused"))
        self.store.add_medication("atorvastatin", status="active", subject="owner")
        self.assertEqual("active", self.read()["atorvastatin"]["status"])

    def test_the_command_takes_a_status(self):
        import shutil
        import tempfile
        from pathlib import Path
        import support
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "profile"
            shutil.copytree(support.FIXTURE_PROFILE, prof)
            code, out, err = support.run(["add-med", "test drug", "--status", "stopped"],
                                         profile_dir=prof)
            self.assertEqual(0, code, err)
            meds = {m["name"]: m for m in
                    support.run_json(["medications"], profile_dir=prof)["medications"]}
            self.assertEqual("stopped", meds["test drug"]["status"])
            self.assertFalse(meds["test drug"]["current"])


class TestAListingMarksWhatIsNotCurrent(_Profile):
    """Everywhere the regimen was listed — the command, the page, the context
    pasted into a model — a stopped entry was drawn like one taken this
    morning. The comparison had already excluded it; the listings showed a
    regimen the engine was not using."""

    def setUp(self):
        super().setUp()
        self.write(med("atorvastatin", "not_in_scheme_2026-09-10", dose="20 mg"),
                   med("omeprazole", "active", dose="20 mg"),
                   med("vitamin d3"))

    def test_the_list_carries_the_verdict(self):
        from scholion import store
        got = {m["name"]: m["current"] for m in store.list_medications()}
        self.assertEqual({"atorvastatin": False, "omeprazole": True, "vitamin d3": True}, got)

    def test_the_command_marks_it(self):
        from unittest import mock
        from scholion import format as fmt, store
        with mock.patch("scholion.core.cpic_kb", return_value={"drugs": []}):
            out = fmt.medications_report({"medications": store.list_medications()})
        lines = [l for l in out.split("\n") if "·" in l]
        by_name = {n: next(l for l in lines if n in l)
                   for n in ("atorvastatin", "omeprazole", "vitamin d3")}
        self.assertIn("not_in_scheme_2026-09-10", by_name["atorvastatin"])
        self.assertNotIn("not current", by_name["omeprazole"])
        self.assertNotIn("not current", by_name["vitamin d3"])

    def test_the_context_for_a_model_marks_it(self):
        from scholion import assistant
        rows = [l for l in assistant._fmt_meds().splitlines() if l.startswith("—")]
        by_name = {n: next(l for l in rows if n in l) for n in ("atorvastatin", "omeprazole")}
        self.assertIn("not_in_scheme_2026-09-10", by_name["atorvastatin"])
        self.assertNotIn("not current", by_name["omeprazole"])

    def test_the_page_marks_it(self):
        from pathlib import Path
        from scholion import engine
        page = (Path(engine.__file__).resolve().parent.parent
                / "web" / "index.html").read_text(encoding="utf-8")
        item = page[page.index("function medItem"):page.index("async function viewMeds")]
        self.assertIn("m.current===false", item, "the page does not look at the verdict")
        self.assertIn("web.meds.not_current", item)
        form = page[page.index("async function viewMeds"):page.index("function bindRemove")]
        self.assertIn('id="m-status"', form, "the form has no status field")
        self.assertIn("status:$('#m-status',root).value", form,
                      "the status is on the form and not in the request")

    def test_the_sentence_about_a_missing_status_does_not_date_it(self):
        """An entry added yesterday without a status looks exactly like one
        written before the field existed; a sentence that says «predate» is
        wrong about it."""
        from scholion.i18n import en, ru
        self.assertNotIn("predate", en.MESSAGES["prescription.status_not_recorded"])
        self.assertNotIn("старше", ru.MESSAGES["prescription.status_not_recorded"])


if __name__ == "__main__":
    unittest.main()
