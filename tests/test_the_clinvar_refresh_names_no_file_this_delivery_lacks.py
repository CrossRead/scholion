"""The ClinVar refresh names no file this delivery lacks.

The button labelled «Check for updates» refreshed ClinVar rather than the program,
through a shell script of the genome-preparation toolkit that a pip install does
not carry. Pressed after `pip install`, it answered with a path inside the
person's Python installation (13.09.2026). It is now called what it does, it is
not offered where it cannot run, and the refusal is a sentence naming where the
step is done — never a file.
"""
from __future__ import annotations

import re
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, server
from scholion.i18n import en, ru

PATHLIKE = re.compile(r"site-packages|/ingest/|\.sh\b|update_check")


class TestTheRefusal(unittest.TestCase):

    def test_an_installed_package_is_refused_by_a_sentence_without_a_path(self):
        with mock.patch.object(core, "is_installed_mode", lambda: True):
            key = server._update_refusal()
        self.assertEqual("server.update.not_in_this_delivery", key)
        for cat in (en.MESSAGES, ru.MESSAGES):
            with self.subTest(lang=cat is en.MESSAGES and "en" or "ru"):
                self.assertNotRegex(cat[key], PATHLIKE)
                self.assertIn("scholion version", cat[key], "the sentence points at updating the program")

    def test_a_tree_without_a_shell_is_refused_by_its_own_sentence(self):
        with mock.patch.object(core, "is_installed_mode", lambda: False), \
                mock.patch.object(server.shutil, "which", lambda name: None):
            key = server._update_refusal()
        if (server._INGEST / "update_check.sh").exists():
            self.assertEqual("server.update.no_shell", key)

    def test_the_background_run_leaves_no_path_in_its_log(self):
        with mock.patch.object(core, "is_installed_mode", lambda: True):
            server._UPD.update({"running": False, "rc": None, "log": "", "hint": ""})
            server._run_update_bg()
            for _ in range(100):
                if not server._UPD["running"] and server._UPD["rc"] is not None:
                    break
                import time; time.sleep(0.01)
        self.assertEqual(5, server._UPD["rc"])
        self.assertNotRegex(server._UPD["log"], PATHLIKE)
        self.assertEqual("server.update.not_in_this_delivery", server._UPD["hint"])


class TestTheLabel(unittest.TestCase):

    def test_the_button_says_what_it_refreshes(self):
        self.assertIn("ClinVar", en.MESSAGES["web.updates.check_btn"])
        self.assertIn("ClinVar", ru.MESSAGES["web.updates.check_btn"])
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertFalse(any("Check for updates" in v for v in cat.values() if isinstance(v, str)))


if __name__ == "__main__":
    unittest.main()
