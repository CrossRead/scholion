"""One measurement standing twice, named where a person would read it.

`add_lab_point` notices when the same period is already present at another
resolution. It used to leave every such pair standing and report it — «2026-07»
and «2026-07-14» charted twice and trended twice — and the tested part stopped
at the store: the importer's own report, which is where a person would actually
read it, carried the flag through six lines that ran in no test.

Since tasks 128 and 144 the store resolves such a pair itself, at every
resolution, and what it still reports is the one pair it cannot resolve: a bare
day or month arriving against two draws inside it. That is the pair the
importer's report must carry, and this holds that it does.

The importer is fed CSV rather than PDF for the same reason the table test is:
the delimiter path needs no reader and no mock, so the test is about the
reporting and nothing else.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import support

if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))

BY_DAY = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,31,ng/mL,13-150
"""


class ResolutionCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        # The cache too: the loader's list of already-read files lives beside
        # the profile now, and an old list found in the cache is carried over.
        self._restore_cache = support.pin_cache(self.root / "cache")
        from scholion import core
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        self._restore_cache()
        from scholion import core
        core.reset_cache()
        self.tmp.cleanup()

    def ingest(self):
        from scholion import ingest_labs
        return ingest_labs.ingest(str(self.forms), force=True)


class TestTheDoublingIsNamedInTheReport(ResolutionCase):

    def test_a_bare_day_against_two_draws_of_it_is_reported_as_one_measurement_twice(self):
        # The two draws are seeded through the store rather than through a
        # delimited file: the point under test is what the importer PRINTS when
        # the store cannot resolve a pair, and the file brings the bare day.
        from scholion import store
        self.assertTrue(store.add_lab_point("ferritin", "2018-05-22T08:22", 31, unit="ng/mL")["ok"])
        self.assertTrue(store.add_lab_point("ferritin", "2018-05-22T16:40", 29, unit="ng/mL")["ok"])
        (self.forms / "a_day.csv").write_text(BY_DAY, encoding="utf-8")

        r = self.ingest()

        mixed = r.get("resolution_mixed") or []
        self.assertTrue(mixed, "the doubling was noticed by the store and lost by the report")
        entry = next(m for m in mixed if m["marker"] == "ferritin")
        self.assertEqual(entry["others"], ["2018-05-22T08:22", "2018-05-22T16:40"],
                         "the report does not say which other points it stands beside")
        self.assertEqual(entry["date"], "2018-05-22",
                         "the report does not say which point raised it")
        self.assertEqual([], r.get("same_day_replaced") or [],
                         "a day that names neither draw was said to have replaced one")

    def test_a_month_against_the_one_day_in_it_is_no_longer_reported_but_replaced(self):
        """The pair this file was written for. It is resolved now (task 144):
        the day is the finer date of one draw, and the report names the
        replacement instead of a doubling."""
        from scholion import store
        self.assertTrue(store.add_lab_point("ferritin", "2018-05", 12, unit="ng/mL")["ok"])
        (self.forms / "a_day.csv").write_text(BY_DAY, encoding="utf-8")

        r = self.ingest()

        self.assertEqual([], r.get("resolution_mixed") or [],
                         "resolved and still reported as a doubling")
        rep = [x for x in r.get("same_day_replaced") or [] if x["marker"] == "ferritin"]
        self.assertEqual(len(rep), 1, "the monthly point was swallowed and nobody was told")
        self.assertEqual(rep[0]["replaced"], ["2018-05"])
        self.assertEqual(rep[0]["date"], "2018-05-22")

    def test_a_series_at_one_resolution_raises_nothing(self):
        """Both points dated to the day: two measurements, not one twice."""
        (self.forms / "a_day.csv").write_text(BY_DAY, encoding="utf-8")
        (self.forms / "another_day.csv").write_text(
            BY_DAY.replace("2018-05-22", "2018-06-19"), encoding="utf-8")

        r = self.ingest()

        self.assertEqual([], r.get("resolution_mixed") or [],
                         "an ordinary second measurement was called a doubling")


if __name__ == "__main__":
    unittest.main()
