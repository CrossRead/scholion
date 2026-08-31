"""The sentence that follows the arrow, rendered.

`analyze_labs` gained a per-marker floor: the smallest relative change this
marker's own history has shown itself able to tell from its own wobble. Below
that, the report says so instead of leaving «↑ 3 %» to be read as a finding.

The engine side of it was tested; the sentence itself was not rendered in any
test, so the phrase a reader actually sees — and the shape of the structure it
formats — were unchecked. The suite's reach gate is what noticed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import support

if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))

from scholion import core, engine, format as fmt                 # noqa: E402
from scholion.engine import labs as labs_engine                  # noqa: E402

#: Seven readings wobbling by a few per cent, then a last move smaller than the
#: wobble. Synthetic and deliberately dull: the point is the arithmetic, not a
#: clinical picture.
SERIES = [(f"2025-{m:02d}-10", v) for m, v in
          enumerate([5.00, 5.20, 4.95, 5.15, 4.90, 5.10, 5.25], start=1)]


class LabFloorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lab-floor-")).resolve()
        (self.tmp / "profile").mkdir()
        self._env = dict(os.environ)
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.tmp / "profile")
        os.environ["SCHOLION_REPO_DIR"] = str(self.tmp)
        os.environ["SCHOLION_OFFLINE"] = "1"
        os.environ["SCHOLION_LANG"] = "en"
        labs = {"_meta": {"what": "synthetic fixture"},
                "markers": {"glucose": {"name": "Glucose", "unit": "mmol/L",
                                        "series": [{"date": d, "value": v} for d, v in SERIES]}}}
        (self.tmp / "profile" / "labs.json").write_text(
            json.dumps(labs, ensure_ascii=False), encoding="utf-8")
        core.reset_cache()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        core.reset_cache()
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestTheFloorIsMeasuredFromTheHistory(LabFloorCase):

    def test_a_move_under_the_floor_is_not_called_a_direction(self):
        floor = labs_engine.change_floor([{"date": d, "value": v} for d, v in SERIES])
        self.assertIsNotNone(floor, "six intervals were not enough to measure anything")
        self.assertEqual("own_history", floor["from"])
        last = 100.0 * (SERIES[-1][1] - SERIES[-2][1]) / SERIES[-2][1]
        self.assertLess(abs(last), floor["rcv_pct"],
                        "the fixture no longer demonstrates a move under the floor")

    def test_the_report_says_so_in_words(self):
        """The rendered sentence, not just the flag underneath it."""
        text = fmt.labs_report(engine.analyze_labs())
        self.assertIn("own scatter", text,
                      "the arrow is printed with nothing said about what it can tell apart")
        self.assertIn("intervals)", text, "the sentence does not say what it was measured on")

    def test_a_history_too_short_says_nothing_at_all(self):
        """Below the minimum the layer is silent rather than unstable."""
        short = [{"date": d, "value": v} for d, v in SERIES[:3]]
        self.assertIsNone(labs_engine.change_floor(short))

    def test_a_value_at_or_below_zero_is_refused_rather_than_divided_by(self):
        bad = [{"date": d, "value": v} for d, v in SERIES]
        bad[2]["value"] = 0.0
        self.assertIsNone(labs_engine.change_floor(bad))


if __name__ == "__main__":
    unittest.main()
