"""Every system the radar reports is placed on the figure, or says it is not.

The figure on the Overview draws organs. The systems that are not drawn are not
drawn on purpose — they are measured in blood or describe the whole body, and
putting them on an organ would be an anatomical claim nobody made.

What must never happen is the third case: a system that is neither drawn nor
declared undrawable, because it was added to the radar after the figure was
written. Nothing would fail. The figure would simply show one system fewer than
the radar beside it, and a person reading a body with a few quiet organs would be
looking at a healthier picture than their data supports.

So the map is enumerated against the radar rather than trusted: every key the
radar emits has an entry, every entry declares exactly one of four states, every
place named is one the page actually draws, and a domain split across glands
names every one of its own markers — a hormone that quietly loses its gland
stops being drawn, and nothing says so.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core

# `from scholion.engine import lifestyle` hands back the FUNCTION of that name,
# not the module: the package re-exports it. The module itself is what this test
# reads its source from, so it is imported by path.
import importlib
lifestyle = importlib.import_module("scholion.engine.lifestyle")

WEB = Path(lifestyle.__file__).resolve().parents[1] / "web" / "index.html"

#: The four states an entry may declare. Exactly one, never two, never none.
STATES = ("place", "by_marker", "systemic", "whole_body")


def _radar_source():
    src = Path(lifestyle.__file__).read_text(encoding="utf-8")
    block = src[src.index("_RADAR_DOMAINS = ["):]
    # Cut at the list's OWN closing bracket, alone on its line — `index("]")`
    # stops at the first inner list of marker names and reports one domain.
    return src, block[:block.index(chr(10) + "]")]


def radar_keys():
    """Every key `health_radar` can emit — read off the source, not off a run.

    A run on the test fixture reports only the domains that fixture happens to
    have data for; the question here is about the domains that EXIST.
    """
    src, block = _radar_source()
    keys = re.findall(r'\(\s*"([a-z_]+)"', block)
    # `fitness` is appended after the loop, from the wearable side.
    if '"key": "fitness"' in src:
        keys.append("fitness")
    return keys


def radar_panels():
    """domain key → the markers it declares, as the source declares them."""
    _src, block = _radar_source()
    return {k: re.findall(r'"([a-z0-9_]+)"', body)
            for k, body in re.findall(r'\(\s*"([a-z_]+)"\s*,\s*\[([^\]]*)\]', block)}


class TestEverySystemDeclaresWhereItIs(unittest.TestCase):

    def setUp(self):
        self.map = json.loads(
            core.knowledge_path("body_map.json").read_text(encoding="utf-8"))
        self.places = self.map["places"]

    def test_the_radar_and_the_map_name_the_same_systems(self):
        missing = [k for k in radar_keys() if k not in self.places]
        self.assertEqual(missing, [],
                         "these systems reach the radar and the body map has never heard "
                         "of them, so the figure would draw one system fewer than the "
                         "radar beside it: " + ", ".join(missing))
        extra = [k for k in self.places if k not in radar_keys()]
        self.assertEqual(extra, [],
                         "the map places systems the radar does not emit — an entry that "
                         "describes nothing goes stale unnoticed: " + ", ".join(extra))

    def test_each_entry_declares_exactly_one_state(self):
        for key, e in self.places.items():
            with self.subTest(system=key):
                declared = [s for s in STATES if e.get(s)]
                self.assertEqual(len(declared), 1,
                                 f"{key} declares {declared or 'nothing'}; it must declare "
                                 f"exactly one of {STATES}")

    def test_every_entry_says_on_what_grounds(self):
        """A placement is a claim about anatomy. An unsourced one is the class this
        project refuses everywhere else, and a drawing is not an exception. A domain
        split across glands owes the reason per marker: `by_marker` makes three
        claims, and one sentence cannot answer for all of them."""
        for key, e in self.places.items():
            with self.subTest(system=key):
                basis = e.get("basis")
                if e.get("by_marker"):
                    self.assertIsInstance(basis, dict,
                                          f"{key} is split by marker; its basis must be too")
                    for marker in e["by_marker"]:
                        self.assertTrue((basis.get(marker) or "").strip(),
                                        f"{key}/{marker} is placed at a gland with no reason "
                                        f"given: nobody can disagree with it")
                else:
                    self.assertTrue((basis or "").strip(),
                                    f"{key} has no basis: nobody can disagree with it")

    def test_a_split_domain_places_exactly_its_own_markers(self):
        """`by_marker` is a second copy of a panel that lives in `_RADAR_DOMAINS`,
        and copies drift. A marker added to the domain and not here is measured,
        scored into the radar and drawn nowhere; a marker named here and dropped
        from the domain is a gland waiting for a number that never arrives."""
        panels = radar_panels()
        for key, e in self.places.items():
            if not e.get("by_marker"):
                continue
            with self.subTest(system=key):
                self.assertEqual(sorted(e["by_marker"]), sorted(panels[key]),
                                 f"{key}: the map places {sorted(e['by_marker'])}, the radar "
                                 f"declares {sorted(panels[key])}")

    def test_a_marker_that_is_made_nowhere_says_so_and_why(self):
        """`systemic` inside `by_marker` is the fourth answer a single marker may
        give, and it is an answer, not a gap: DHT is converted in peripheral tissue
        and estradiol comes from a different source in each figure. It owes a reason
        exactly as a placement does — and it must never reach the vocabulary, or a
        page would look for coordinates named «systemic»."""
        for key, e in self.places.items():
            for marker, place in (e.get("by_marker") or {}).items():
                if place != "systemic":
                    continue
                with self.subTest(system=key, marker=marker):
                    self.assertNotIn("systemic", self.map["vocabulary"])
                    self.assertTrue(((e.get("basis") or {}).get(marker) or "").strip(),
                                    f"{key}/{marker} claims no place and does not say why")

    def test_a_place_is_one_the_page_can_draw(self):
        """The vocabulary, the page and the map have to agree, or a system is
        placed at coordinates that do not exist and silently disappears."""
        vocab = set(self.map["vocabulary"])
        used = set()
        for key, e in self.places.items():
            with self.subTest(system=key):
                if e.get("place"):
                    self.assertIn(e["place"], vocab)
                    used.add(e["place"])
                for marker, place in (e.get("by_marker") or {}).items():
                    if place == "systemic":
                        continue
                    self.assertIn(place, vocab, f"{key}/{marker} is placed at {place}, "
                                                f"which the vocabulary does not allow")
                    used.add(place)
        self.assertEqual(used, vocab,
                         "the vocabulary allows a place nobody uses; an unused coordinate is "
                         f"never checked against the figure: {sorted(vocab - used)}")
        drawn = set(re.findall(r"(\w+):\[\[", WEB.read_text(encoding="utf-8")
                               .split("const ORGAN_SPOT = {")[1].split("};")[0]))
        self.assertEqual(drawn, vocab,
                         "the regions the page draws and the vocabulary the map allows "
                         f"have drifted apart: page={sorted(drawn)}, map={sorted(vocab)}")

    def test_every_place_can_be_named_in_both_languages(self):
        """The mark says which gland it points at. A place with no phrase behind it
        would print its own key at a person."""
        from scholion.i18n import en, ru
        for place in self.map["vocabulary"]:
            for name, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
                with self.subTest(place=place, lang=name):
                    self.assertTrue((cat.get(f"web.body.place.{place}") or "").strip(),
                                    f"{name} cannot name {place}")


class TestTheRadarCarriesThePlace(unittest.TestCase):
    """The page must not need a lookup table of its own: whatever the engine
    knows about where a system lives travels with the answer."""

    def test_every_domain_of_a_real_radar_carries_its_place(self):
        r = lifestyle.health_radar()
        self.assertTrue(r["domains"], "the radar reported nothing; this proves nothing")
        for d in r["domains"]:
            with self.subTest(system=d["key"]):
                self.assertIn("place", d)
                self.assertTrue(any(d["place"].get(s) for s in STATES),
                                f"{d['key']} reached the page with an empty place")

    def test_a_split_domain_arrives_resolved_into_parts(self):
        """The page draws parts; it does not compute them. A `by_marker` entry that
        reached the page unresolved would draw nothing at all — quietly."""
        vocab = set(json.loads(core.knowledge_path("body_map.json")
                               .read_text(encoding="utf-8"))["vocabulary"])
        for d in lifestyle.health_radar()["domains"]:
            if not d["place"].get("by_marker"):
                continue
            with self.subTest(system=d["key"]):
                parts = d["place"].get("parts")
                self.assertTrue(parts, f"{d['key']} is split by marker and arrived unresolved")
                placed = {v for v in d["place"]["by_marker"].values() if v != "systemic"}
                self.assertEqual({p["place"] for p in parts}, placed,
                                 "the parts and the map name different places")
                for p in parts:
                    self.assertIn(p["place"], vocab)
                    self.assertTrue(p["keys"])
                    self.assertEqual(p["total"], len(p["keys"]))
                    self.assertLessEqual(p["measured"], p["total"])
                    if p["score"] is None:
                        self.assertEqual(p["status"], "nodata")
                        self.assertEqual(p["measured"], 0)
                    else:
                        self.assertTrue(p["label"], "a scored part must name its markers")


if __name__ == "__main__":
    unittest.main()
