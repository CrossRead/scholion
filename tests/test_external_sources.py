"""External, user-named data sources: `set-folder` beyond the known domains.

Every person's raw data differs — a CGM app's screenshots, a specific sequencing
provider's export folder, tomorrow somebody else's continuous monitor under yet
another name. Until now `set-folder` refused anything outside a fixed list of
eight domain names. That was fine for those eight — the project has specific,
built-in handling for each — but wrong for everything else: a person's own
source folders have no "correct" spelling to be validated against, and
refusing them left no way to even record where they live.

The fix files a known domain under profile/sources.json → "folders" exactly as
before, and anything else under "external_sources" instead of refusing it.
`core.source_config()` — what every reader of a configured folder actually
calls — merges both sections, so the split is invisible once a folder is set;
it only matters at the moment of setting one.

The trade-off, accepted deliberately: the old refusal also had the side effect
of catching a typo of one of the eight ("grmin" for "garmin"). Opening the
domain name up removes that — a near-miss is now just an ordinary new
external_sources entry, and the intended domain is left untouched, not
corrected. Nothing reads external_sources programmatically yet, so today that
costs nothing silent (see the comment above _KNOWN_SOURCE_DOMAINS in store.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support


class _Profile:
    """A throwaway profile directory plus a throwaway folder to point a domain at.

    `set_source_folder` requires the target folder to already exist, so a
    fixture that only made the profile would fail every test on the wrong line.
    """

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.source = self.root / "my_source"
        self.source.mkdir()

    def sources_json(self) -> dict:
        p = self.profile / "sources.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def close(self):
        self.tmp.cleanup()


class TestAKnownDomainIsUnchanged(unittest.TestCase):
    """The eight vetted names behave exactly as before: "folders", typo-checked."""

    def setUp(self):
        self.p = _Profile()

    def tearDown(self):
        self.p.close()

    def test_a_known_domain_is_filed_under_folders(self):
        res = support.run_json(["set-folder", "garmin", str(self.p.source)],
                               profile_dir=self.p.profile)
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("section"), "folders")
        cfg = self.p.sources_json()
        self.assertEqual(cfg.get("folders", {}).get("garmin"), str(self.p.source))
        self.assertNotIn("garmin", cfg.get("external_sources", {}))

    def test_apple_health_is_known_too(self):
        """Documented in the project as a standard, supported source type (see
        layout.readme.raw_wearables) even though nothing ingests it yet — so it
        gets the same typo protection as the other seven, not the open door."""
        res = support.run_json(["set-folder", "apple_health", str(self.p.source)],
                               profile_dir=self.p.profile)
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("section"), "folders")
        self.assertEqual(self.p.sources_json().get("folders", {}).get("apple_health"),
                         str(self.p.source))

    def test_a_near_miss_of_a_known_domain_is_accepted_as_external_not_guessed_at(self):
        """The trade-off, made explicit and locked in: opening the domain name up
        to anything means a typo of "garmin" is no longer refused — it becomes an
        ordinary external_sources entry, and "garmin" itself is simply left as it
        was, neither overwritten nor corrected. Nothing reads external_sources
        programmatically today, so this costs nothing silent; a fuzzy "did you
        mean" guess was deliberately left out (see the comment in store.py)."""
        res = support.run_json(["set-folder", "grmin", str(self.p.source)],
                               profile_dir=self.p.profile)
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("section"), "external_sources")
        self.assertNotIn("garmin", self.p.sources_json().get("folders", {}))


class TestACustomDomainIsAcceptedAsExternal(unittest.TestCase):
    """A name nobody whitelisted — this is the point of the change."""

    def setUp(self):
        self.p = _Profile()

    def tearDown(self):
        self.p.close()

    def test_a_custom_domain_is_filed_under_external_sources(self):
        res = support.run_json(["set-folder", "cgm_screenshots", str(self.p.source)],
                               profile_dir=self.p.profile)
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("section"), "external_sources")
        cfg = self.p.sources_json()
        self.assertEqual(cfg.get("external_sources", {}).get("cgm_screenshots"), str(self.p.source))
        self.assertNotIn("cgm_screenshots", cfg.get("folders", {}))

    def test_core_source_config_reads_it_back_the_same_way_a_known_domain_is_read(self):
        """The split must be invisible on the read side — otherwise the folder
        is recorded but nothing that later looks it up ever finds it."""
        support.run_json(["set-folder", "evogen_genome_app", str(self.p.source)],
                         profile_dir=self.p.profile)
        code = ("import sys; sys.path.insert(0, %r);"
                "from scholion import core;"
                "print(core.source_config().get('evogen_genome_app', ''))" % str(support.SRC))
        env = support.env(profile_dir=self.p.profile)
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              cwd=str(support.ROOT), capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), str(self.p.source))

    def test_a_known_and_a_custom_domain_coexist(self):
        """Setting one does not clobber or hide the other."""
        support.run_json(["set-folder", "garmin", str(self.p.source)], profile_dir=self.p.profile)
        other = self.p.root / "another_source"
        other.mkdir()
        support.run_json(["set-folder", "cgm_screenshots", str(other)], profile_dir=self.p.profile)
        cfg = self.p.sources_json()
        self.assertEqual(cfg.get("folders", {}).get("garmin"), str(self.p.source))
        self.assertEqual(cfg.get("external_sources", {}).get("cgm_screenshots"), str(other))


class TestTheFolderStillHasToExist(unittest.TestCase):
    """Opening up the domain name must not open up the folder check too — a
    positive control so this suite would fail loudly if it ever did."""

    def setUp(self):
        self.p = _Profile()

    def tearDown(self):
        self.p.close()

    def test_a_custom_domain_pointed_at_a_missing_folder_is_refused(self):
        missing = self.p.root / "does_not_exist"
        res = support.run_json(["set-folder", "cgm_screenshots", str(missing)],
                               profile_dir=self.p.profile)
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(self.p.sources_json(), {})

    def test_an_empty_domain_name_is_refused_not_silently_filed(self):
        res = support.run_json(["set-folder", "", str(self.p.source)],
                               profile_dir=self.p.profile)
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(self.p.sources_json(), {})


if __name__ == "__main__":
    unittest.main()
