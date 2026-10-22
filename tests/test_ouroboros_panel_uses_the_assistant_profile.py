"""A visual door must not quietly open another person's data or another server."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import tempfile

from test_the_hub_skill_shows_the_owner_where_data_goes import HubSkillCase


class TestSharedConnection(HubSkillCase):
    def test_connect_previews_before_selecting_and_preserves_existing_files(self):
        from scholion import core, store, container
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve() / "existing"
            old = os.environ.get("SCHOLION_REPO_DIR")
            os.environ["SCHOLION_REPO_DIR"] = str(target)
            store.init_profile()
            container.ensure()
            before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            if old is None:
                os.environ.pop("SCHOLION_REPO_DIR", None)
            else:
                os.environ["SCHOLION_REPO_DIR"] = old
            core.reset_cache()
            self.register()
            default = core.profile_dir()
            preview = self.call("connect", {"path": str(target)})
            self.assertTrue(preview["preview"])
            self.assertEqual(default, core.profile_dir())
            self.assertFalse((self.state / "connection.json").exists())
            attached = self.call("connect", {"path": str(target), "confirm": preview["confirm"]})
            self.assertTrue(attached["ok"])
            self.assertEqual(target / "profile", core.profile_dir())
            self.assertEqual(before, {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()})
            # A genuinely new call adopts the same persisted connection.
            for key in ("SCHOLION_REPO_DIR", "SCHOLION_PROFILE_DIR"):
                os.environ.pop(key, None)
            self.register()
            self.assertEqual(str(target / "profile"), self.call("state")["profile_dir"])
            self.assertEqual(str(target / "profile"), self.plugin._binding()["SCHOLION_PROFILE_DIR"])

    def test_initialisation_records_one_connection_without_replacing_files(self):
        self.register()
        self.call("init")
        saved = (self.state / "connection.json").read_bytes()
        self.call("init")
        self.assertEqual(saved, (self.state / "connection.json").read_bytes())
        self.assertEqual(0o600, (self.state / "connection.json").stat().st_mode & 0o777)
        self.assertEqual(self.call("launch")["binding"], self.plugin._binding_id(self.plugin._binding()))

    def test_unknown_or_changed_confirmation_does_not_select_a_profile(self):
        self.register()
        self.assertFalse(self.call("connect", {"path": "relative"})["ok"])
        self.assertFalse(self.call("connect", {"path": str(self.state)})["ok"])
        self.assertFalse((self.state / "connection.json").exists())

    def test_broken_connection_fails_instead_of_falling_back_to_an_empty_profile(self):
        (self.state / "connection.json").write_text('{"broken": true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.register()

    def test_web_proxy_refuses_wrong_profile_and_nonlocal_targets(self):
        self.register()

        class Request:
            method = "GET"
            headers = {}
            query_params = {"path": "/api/labs"}

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.host.routes["web"](Request()))
            self.assertIn("profile connection changed", str(result.get("error")) if isinstance(result, dict) else result.body.decode())
            for path in ("https://example.org/", "//example.org/", "/../profile/labs.json", "/\\example.org", "/api/labs\r\n"):
                request = Request()
                request.query_params = {"path": path}
                result = loop.run_until_complete(self.host.routes["web"](request))
                self.assertIn("Invalid local route", str(result.get("error")) if isinstance(result, dict) else result.body.decode(), path)
        finally:
            loop.close()

    def test_catalogues_explain_the_shared_profile_in_both_languages(self):
        from scholion import i18n
        for lang in ("en", "ru"):
            messages = i18n.messages(lang)
            self.assertIn("hub.same_profile", messages)
            self.assertIn("hub.connect_help", messages)

    def test_setup_and_connection_are_human_actions_not_new_model_tools(self):
        self.register()
        self.assertFalse({"init", "connect", "launch", "choose", "web"} & set(self.host.tools))
        from scholion import contract
        self.assertFalse(contract.access()["doors"]["ouroboros_hub"]["human_ui"]["agent_surface"])
