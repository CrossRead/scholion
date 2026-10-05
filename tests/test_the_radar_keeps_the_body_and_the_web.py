"""The radar keeps its two pictures, and what they say is in the reader's language.

0.6.0 redraws the page in Crossread. The owner's condition for the radar
(27.09.2026) was that its logic stays: the human figure with a mark at every
organ the body map names, and the web with an axis for every system that has a
score. A redraw is exactly when a picture quietly loses a mark — a place in the
map with no spot on the figure draws a healthier person than the data
describes — so the two are held here (C35).

Redrawing the mock-up from the engine's real answer also found three defects,
held here too:

* the demo kept vitamin B12 under `b12`, a key nothing reads, so the radar
  counted a measured 176 as never drawn (C36);
* the figure and the radar printed the marker names the way the profile keeps
  them — «TSH», «Free T4 · Anti-TPO antibodies» on a Russian page;
* the axis straight up printed its score on its own dot.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core, demo

PAGE = (support.SRC / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
BODY_MAP = json.loads((support.SRC / "scholion" / "knowledge" / "body_map.json").read_text(encoding="utf-8"))


class TestTheTwoPicturesStay(unittest.TestCase):

    def test_both_are_drawn_from_the_same_systems(self):
        render = PAGE[PAGE.index("async function renderSystems("):]
        render = render[:render.index("\n}\n")]
        self.assertIn("bodySVG(doms, sex)", render)
        self.assertIn("radarSVG(doms)", render)

    def test_every_place_the_map_can_name_has_a_spot_on_the_figure(self):
        spots = PAGE[PAGE.index("const ORGAN_SPOT"):]
        spots = spots[:spots.index(";\n")]
        drawn = set(re.findall(r"(\w+):\[\[", spots))
        self.assertEqual(set(), set(BODY_MAP["vocabulary"]) - drawn,
                         "a place the body map can name has nowhere to be drawn")

    def test_the_web_has_an_axis_for_every_system_including_no_data(self):
        web = PAGE[PAGE.index("function radarSVG("):]
        web = web[:web.index("\n}\n")]
        self.assertIn("const d=domains;", web)
        self.assertIn("N=d.length", web)
        self.assertIn('rdot-empty', web)
        self.assertIn("dom[field]==null||d[j][field]==null", web)
        render = PAGE[PAGE.index("async function renderSystems("):]
        self.assertNotIn("filter(d=>d.score!=null)", render[:render.index("\n}\n")])

    def test_the_axis_straight_up_does_not_print_on_its_dot(self):
        web = PAGE[PAGE.index("function radarSVG("):]
        self.assertIn("anchor==='middle'&&ly<cy", web[:web.index("\n}\n")])

    def test_print_keeps_the_radar_without_a_full_height_overview_silhouette(self):
        self.assertIn('#ov-systems .syspane:first-child', PAGE)
        self.assertIn('#sl-systems .sysrow,#ov-systems .sysrow{grid-template-columns:minmax(0,1fr)}', PAGE)
        self.assertIn('.sysrow{break-inside:avoid}', PAGE)
        self.assertIn('.syscard,.sysblock{break-inside:auto}', PAGE)

    def test_a_part_named_by_two_markers_is_two_lines(self):
        body = PAGE[PAGE.index("function bodySVG("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("split(' · ')", body)
        self.assertIn("label:p.label||d.label", body)


class _Demo(unittest.TestCase):
    """The demo, generated into a throw-away folder and pinned for the test."""

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="radar_demo_")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        prof = root / "profile"
        prof.mkdir()
        for name, data in demo.build_all().items():
            path = prof / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.labs = json.loads((prof / "labs.json").read_text(encoding="utf-8"))
        self.addCleanup(support.pin_profile(prof))
        self.addCleanup(support.pin_cache(root / "cache"))
        old = os.environ.get("SCHOLION_LANG")
        self.addCleanup(lambda: os.environ.update({"SCHOLION_LANG": old}) if old is not None
                        else os.environ.pop("SCHOLION_LANG", None))


class TestTheDemoSpeaksTheDictionary(_Demo):

    def test_every_demo_marker_is_a_known_marker(self):
        known = set((core.lab_markers().get("markers") or {}))
        self.assertEqual(set(), set(self.labs["markers"]) - known,
                         "a demo key the dictionary does not know is a value nothing reads")

    def test_the_measured_b12_reaches_the_radar(self):
        from scholion import engine
        r = engine.health_radar()
        micro = next(d for d in r["domains"] if d["key"] == "micronutrients")
        self.assertNotIn("vitamin_b12", micro["missing"])
        self.assertIn("vitamin_b12", [a["key"] for a in micro["abnormal"]])


class TestTheRadarSpeaksOneLanguage(_Demo):

    def test_russian_names_on_a_russian_radar(self):
        from scholion import i18n
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))
        i18n.set_lang(None)  # this test exercises SCHOLION_LANG, not a prior CLI override
        os.environ["SCHOLION_LANG"] = "ru"
        from scholion import engine
        r = engine.health_radar()
        thyroid = next(d for d in r["domains"] if d["key"] == "thyroid")
        labels = [p["label"] for p in thyroid["place"]["parts"] if p["label"]]
        names = [a["name"] for d in r["domains"] for a in d.get("abnormal", [])
                 if a["key"] in (core.lab_markers().get("markers") or {})]
        for text in labels + names:
            with self.subTest(text=text):
                self.assertRegex(text, r"[А-Яа-яЁё]", "a Latin marker name on a Russian radar")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
