"""An update says what it asks of the data, until a person has read it.

A doctor ran the product on 11.09.2026 three days behind the release that fixed
her own complaint, and nothing in the product could have told her. `scholion
version` now says which build this is, how old it is, which version the data was
last used with, and what every release in between asks to recompute — read from
the journal the package carries. The note stays until a person says they have
read it (`--seen`, or «Understood» on the page); an ordinary run never records it
silently. The registry is asked only on an explicit request, through one constant
address, and never when the network is switched off.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import re
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import format as fmt, store, updates


class _Profile(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="upd_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))

    def marker(self):
        p = self.profile / updates.MARKER
        return p.read_text(encoding="utf-8").strip() if p.exists() else None


class TestTheMarker(_Profile):

    def test_a_new_profile_starts_at_this_build(self):
        out = self.root / "fresh"
        r = store.init_profile(target=str(out))
        self.assertTrue(r["ok"], r)
        self.assertEqual(updates.installed(), (out / updates.MARKER).read_text(encoding="utf-8").strip())

    def test_an_older_marker_lists_what_came_after_until_it_is_seen(self):
        (self.profile / updates.MARKER).write_text("0.4.8\n", encoding="utf-8")
        st = updates.status()
        self.assertTrue(st["changed"])
        versions = [e["version"] for e in st["pending"]]
        self.assertIn("0.4.9", versions)
        self.assertIn("0.4.11", versions)
        self.assertNotIn("0.4.8", versions)
        text = fmt.version_report(st)
        self.assertIn("scholion acmg-scan", text)
        self.assertIn("scholion version --seen", text)
        self.assertEqual("0.4.8", self.marker(), "reading the status recorded nothing")
        self.assertTrue(updates.mark_seen()["ok"])
        self.assertEqual(updates.installed(), self.marker())
        after = updates.status()
        self.assertFalse(after["changed"])
        self.assertNotIn("scholion version --seen", fmt.version_report(after))

    def test_no_marker_is_said_and_since_lists_on_request(self):
        st = updates.status()
        self.assertIsNone(st["last_used"])
        self.assertEqual("not_recorded", st["why"])
        self.assertEqual([], st["pending"])
        self.assertIn("scholion version --since", fmt.version_report(st))
        asked = updates.status(since="0.4.8")
        self.assertTrue(asked["explicit_since"])
        self.assertFalse(asked["changed"])
        self.assertTrue(asked["pending"])
        self.assertIn("scholion ingest-labs --force", fmt.version_report(asked))

    def test_an_ordinary_command_never_records_the_marker(self):
        code, out, err = support.run(["version"], profile_dir=self.profile)
        self.assertEqual(0, code, err or out)
        self.assertIsNone(self.marker(), "running `version` wrote the marker — the note would vanish unread")
        code, out, err = support.run(["overview"], profile_dir=self.profile)
        self.assertIsNone(self.marker())

    def test_the_command_line_records_it_when_asked(self):
        code, out, err = support.run(["version", "--seen"], profile_dir=self.profile)
        self.assertEqual(0, code, err or out)
        self.assertIsNotNone(self.marker())


class TestTheRegistry(unittest.TestCase):

    def test_offline_asks_nothing(self):
        called = []
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": "1"}):
            with mock.patch("scholion.net.get_json", lambda url: called.append(url)):
                r = updates.check_registry()
        self.assertEqual("offline", r["status"])
        self.assertEqual([], called)

    def test_one_constant_address_and_the_three_answers(self):
        asked = []
        def fetch(v):
            def f(url):
                asked.append(url)
                return {"info": {"version": v}} if v else None
            return f
        self.assertEqual("newer", updates.check_registry(fetch("99.0.0"))["status"])
        self.assertEqual("pip install --upgrade scholion", updates.check_registry(fetch("99.0.0"))["command"])
        self.assertEqual("current", updates.check_registry(fetch(updates.installed()))["status"])
        self.assertEqual("unreachable", updates.check_registry(fetch(None))["status"])
        self.assertEqual({updates.REGISTRY}, set(asked))
        self.assertEqual("https://pypi.org/pypi/scholion/json", updates.REGISTRY)

    def test_the_command_line_says_offline_in_words(self):
        code, out, err = support.run(["version", "--check"])
        self.assertEqual(0, code, err or out)
        self.assertIn("SCHOLION_OFFLINE", out)


class TestThePageAsksOnlyWhenPressed(unittest.TestCase):

    def test_the_registry_route_is_called_from_the_button_alone(self):
        page = (Path(updates.__file__).resolve().parent / "web" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(1, page.count("/api/version/check"),
                         "the page asks the registry from more than one place")
        # Since 0.5.2 two buttons ask — the update note's and the menu's — through
        # the one function that holds the route; nothing else calls it.
        at = page.index("/api/version/check")
        holder = page.rfind("async function askRegistry(){", 0, at)
        self.assertGreater(holder, 0, "the route is asked outside askRegistry")
        self.assertLess(at - holder, 200)
        calls = [m.start() for m in re.finditer(r"askRegistry\(\)", page) if m.start() != holder + len("async function ")]
        self.assertEqual(2, len(calls), "askRegistry is called from somewhere other than the two buttons")
        for c in calls:
            before = page[max(0, c - 300):c]
            self.assertTrue("$('#upd-check').onclick" in before or "[data-menu=\"check\"]" in before,
                            "askRegistry is called outside a button's handler")


if __name__ == "__main__":
    unittest.main()
