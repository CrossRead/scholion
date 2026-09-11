"""A refusal names which silence it is — and the build knows its own age.

Three silences wore one sentence. «We could not look», «we looked and there is no
such drug» and «we looked, found it, and no guideline for it is in our copy» are
different facts that send a reader somewhere different — to the network, to the
spelling on the box, or nowhere at all because the answer is genuinely that there
is nothing to know. A clinician asked about ursodiol, got «to be assessed with the
doctor», and wrote that she could not tell whether the literature has nothing or
whether the project has not got round to it.

A guideline snapshot has a date, and the date is what tells those two apart. So it
travels with the refusal.

The second half is the build itself. The product says when a reference database
went stale and said nothing about its own age; a physician ran a version one
release behind for four days and the release she was missing fixed the very thing
she spent the session on. The first attempt asked PyPI and the privacy guard
refused it, correctly — a product whose claim is that nothing leaves the disk does
not acquire an outbound host to deliver a convenience. The build's own release
date answers the useful half with nobody contacted.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion.engine import pgx, sources as S
from scholion.i18n import en, ru


class TestARefusalNamesWhichSilenceItIs(unittest.TestCase):

    def test_no_network_is_not_an_unknown_drug(self):
        with mock.patch("scholion.net.offline", return_value=True), \
             mock.patch("scholion.drugsource.resolve_drug", return_value=None):
            r = pgx._check_drug_online("урсодиол")
        self.assertEqual("not_checked", r["status"])
        self.assertEqual("offline", r["reason"])

    def test_an_unknown_drug_is_not_a_missing_network(self):
        with mock.patch("scholion.net.offline", return_value=False), \
             mock.patch("scholion.drugsource.resolve_drug", return_value=None):
            r = pgx._check_drug_online("не-препарат-вовсе")
        self.assertEqual("not_found", r["status"])
        self.assertEqual("unknown_name", r["reason"])

    def test_a_recognised_drug_with_no_pair_says_which_snapshot(self):
        with mock.patch("scholion.net.offline", return_value=False), \
             mock.patch("scholion.drugsource.resolve_drug",
                        return_value={"name": "ursodiol", "internal_class": None,
                                      "atc": [], "url": "x"}), \
             mock.patch.object(pgx, "cpic_snapshot", return_value="2026-08-19"):
            r = pgx._check_drug_online("урсодиол")
        self.assertEqual("found_online", r["status"])
        self.assertEqual("absent_from_cpic_snapshot", r["no_pair_reason"])
        self.assertIn("2026-08-19", r["message"],
                      "the refusal does not date the copy it is a statement about")

    def test_the_snapshot_date_is_read_from_the_provenance_and_not_invented(self):
        with mock.patch.object(S, "provenance",
                               return_value={"pgx": {"updated": "2026-01-02"}}):
            self.assertEqual("2026-01-02", pgx.cpic_snapshot())

    def test_a_missing_provenance_gives_an_empty_date_rather_than_a_guess(self):
        with mock.patch.object(S, "provenance", return_value={}):
            self.assertEqual("", pgx.cpic_snapshot())


class TestTheRegimenSaysWhatIsInTheModel(unittest.TestCase):

    def test_a_drug_in_the_pharmacogenetic_base_is_marked(self):
        with mock.patch("scholion.core.cpic_kb",
                        return_value={"drugs": [{"names": ["clopidogrel"], "gene": "CYP2C19"}]}):
            self.assertIn("CYP2C19", fmt._pgx_mark("clopidogrel"))

    def test_a_supplement_is_not(self):
        with mock.patch("scholion.core.cpic_kb",
                        return_value={"drugs": [{"names": ["clopidogrel"], "gene": "CYP2C19"}]}):
            self.assertEqual("", fmt._pgx_mark("омега-3"))

    def test_the_list_explains_what_being_unmarked_means(self):
        with mock.patch("scholion.core.cpic_kb", return_value={"drugs": []}):
            out = fmt.medications_report({"medications": [{"name": "омега-3"}]})
        self.assertIn(en.MESSAGES["medications.pgx_legend"].strip("_").split(".")[0], out)

    def test_a_long_note_does_not_take_the_whole_line(self):
        """Entries here carry up to fifteen hundred characters of history each. A
        list of forty-five of them is not a list anybody reads."""
        long = "Первое предложение. " + ("хвост " * 200)
        with mock.patch("scholion.core.cpic_kb", return_value={"drugs": []}):
            out = fmt.medications_report({"medications": [{"name": "x", "note": long}]})
        line = [l for l in out.split("\n") if l.strip().startswith("·")][0]
        self.assertLess(len(line), 200, line[:120])
        self.assertIn("Первое предложение", line, "the note vanished instead of folding")


class TestTheBuildKnowsItsOwnAge(unittest.TestCase):

    def test_it_reads_the_date_from_the_journal_it_ships(self):
        r = S.build_freshness()
        self.assertIn(r["status"], ("fresh", "ageing", "unknown"))
        if r["status"] != "unknown":
            self.assertIsNotNone(r["released"])
            self.assertGreaterEqual(r["days"], 0)

    def test_nobody_is_contacted(self):
        """The first attempt asked PyPI and the privacy guard refused it. This
        one may not reach for the network at all — not even indirectly."""
        import scholion.net as net
        with mock.patch.object(net, "get_json",
                               side_effect=AssertionError("the network was used")):
            S.build_freshness()

    def test_the_line_appears_only_once_the_build_is_old(self):
        base = {"markers_total": 1, "abnormal_count": 0, "flagged": [],
                "high_flags": [], "watch_flags": [], "pending_suggestions": [],
                "genome_gaps": [], "disclaimer": "—"}
        fresh = fmt.overview_report({**base, "build": {"status": "fresh", "days": 2}})
        old = fmt.overview_report({**base, "build": {
            "status": "ageing", "days": 60, "installed": "0.4.8", "released": "2026-07-12"}})
        self.assertNotIn("0.4.8", fresh)
        self.assertIn("0.4.8", old)
        self.assertIn("60", old)

    def test_the_threshold_is_a_named_number(self):
        self.assertIsInstance(S.AGEING_AFTER_DAYS, int)
        self.assertGreater(S.AGEING_AFTER_DAYS, 0)


class TestEveryNewPhraseExistsInBothLanguages(unittest.TestCase):

    KEYS = ("drug.not_checked_offline", "drug.no_pair_in_snapshot",
            "medications.in_pgx", "medications.pgx_legend", "overview.build_ageing")

    def test_both_catalogues_carry_them(self):
        for key in self.KEYS:
            for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, cat)


if __name__ == "__main__":
    unittest.main()
