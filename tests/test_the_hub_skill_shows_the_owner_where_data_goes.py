"""The Ouroboros skill has to answer «where do I put my files?» by itself.

Every other door is reached by somebody who already has a shell: the CLI is
typed, the web app is opened at a path, the tools module is imported by a
person who installed it. This one arrives by a click, into a container whose
paths its owner has never seen and cannot list. For three releases the skill
registered thirty tools and no surface at all, so the first answer a new owner
got was `markers: 0; genome: not connected` — a confident report about a person
whose data had never been asked for.

The tests run the plugin the way the host does — importing the file and calling
`register()` — rather than through the CLI, because the file IS the interface
here and nothing about it is reachable from a command line.

The stub below refuses a registration whose permission the manifest does not
declare, which is exactly what the real host does. That single rule is what the
shipped defect broke: the code never called `register_ui_tab`, and the manifest
never asked for `widget`, so nothing failed anywhere and the tab simply did not
exist.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

import support

# The host installs the package; here the source tree stands in for it. Done at
# import time rather than in setUp because the plugin imports `scholion` from
# inside `register()`, which the very first test calls.
if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))

SKILL_DIR = support.ROOT / "ouroboros_plugin" / "hub" / "scholion"
# The manifest, not the folder. `make_shareable.py` copies only `.py` out of
# `ouroboros_plugin/`, so in the built package the folder exists — `plugin.py`
# is in it — while `SKILL.md` never travels: it belongs to the Hub, not to the
# pip package. A guard on the folder therefore passes inside the package and the
# tests then die on a missing file. That is what stopped a release once.
MANIFEST = SKILL_DIR / "SKILL.md"

# Which permission the host requires for each registration. Read off
# `PluginAPIImpl._require(...)` in ouroboros/extension_loader.py; the manifest
# has to declare every one the plugin actually uses.
NEEDS = {
    "register_tool": "tool",
    "register_route": "route",
    "register_ui_tab": "widget",
    "register_settings_section": "widget",
    "register_ws_handler": "ws_handler",
    "register_companion_process": "companion_process",
    "register_supervised_task": "supervised_task",
    "subscribe_event": "subscribe_event",
    "get_settings": "read_settings",
}


class StubHost:
    """Enough of PluginAPI to be refused by it."""

    def __init__(self, permissions, state_dir: Path):
        self.permissions = set(permissions)
        self.state_dir = state_dir
        self.tools: list[str] = []
        self.routes: dict[str, object] = {}
        self.tabs: list[tuple] = []
        self.logs: list[tuple] = []
        self.refused: list[str] = []

    def _require(self, method: str) -> None:
        need = NEEDS[method]
        if need not in self.permissions:
            self.refused.append(f"{method} needs '{need}', manifest declares {sorted(self.permissions)}")
            raise RuntimeError(self.refused[-1])

    def register_tool(self, name, handler, **kw):
        self._require("register_tool")
        self.tools.append(name)

    def register_route(self, path, handler, methods=("GET",)):
        self._require("register_route")
        self.routes[path] = handler

    def register_ui_tab(self, tab_id, title, **kw):
        self._require("register_ui_tab")
        self.tabs.append((tab_id, title, kw.get("render") or {}))

    def get_state_dir(self) -> str:
        return str(self.state_dir)

    def log(self, level, message, **fields):
        self.logs.append((level, message))


def declared_permissions() -> list[str]:
    """The manifest's own list, read without a YAML parser — the core has none."""
    text = MANIFEST.read_text(encoding="utf-8")
    m = re.search(r"^permissions:\s*\[([^\]]*)\]", text, re.M)
    assert m, "the skill declares no permissions at all"
    return [p.strip() for p in m.group(1).split(",") if p.strip()]


def load_plugin():
    spec = importlib.util.spec_from_file_location("scholion_hub_plugin", SKILL_DIR / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HubSkillCase(unittest.TestCase):
    def setUp(self):
        if not MANIFEST.exists():
            self.skipTest("the Hub skill is not part of this build")
        # Resolved here on purpose: on macOS TMPDIR lives under a symlink, and
        # code that resolves a path handed to it returns the resolved form.
        self.state = Path(tempfile.mkdtemp()).resolve() / "skills" / "scholion"
        self.state.mkdir(parents=True)
        self._env = dict(os.environ)
        for key in ("SCHOLION_REPO_DIR", "SCHOLION_PROFILE_DIR"):
            os.environ.pop(key, None)
        os.environ["SCHOLION_OFFLINE"] = "1"
        os.environ["SCHOLION_LANG"] = "en"
        self.plugin = load_plugin()
        self.host = StubHost(declared_permissions(), self.state)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def register(self) -> StubHost:
        self.plugin.register(self.host)
        return self.host

    def call(self, name: str, body=None):
        handler = self.host.routes[name]

        class Request:
            async def json(self):
                return body or {}

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(handler(Request()))
        finally:
            loop.close()          # an unclosed loop is a ResourceWarning in the suite's output
        if hasattr(result, "body"):
            return json.loads(bytes(result.body).decode("utf-8"))
        return result


class TestItAsksForWhatItUses(HubSkillCase):

    def test_every_registration_it_makes_is_a_permission_it_declares(self):
        """The shipped defect, stated as a rule rather than as a tab.

        A missing permission does not crash the host and does not warn: the
        registration is refused, the skill keeps working, and the surface is
        just absent. Nothing but this test notices.
        """
        self.register()
        self.assertEqual([], self.host.refused, "\n".join(self.host.refused))

    def test_it_offers_the_thirty_tools_it_advertises(self):
        from scholion import ouroboros_tools
        self.register()
        self.assertEqual(len(ouroboros_tools.get_tools()), len(self.host.tools))


class TestTheFirstThingAnOwnerSees(HubSkillCase):

    def test_it_registers_the_tab_and_the_routes_that_feed_it(self):
        self.register()
        self.assertEqual(1, len(self.host.tabs), "no tab: the owner meets a tool list and no door")
        self.assertEqual({"state", "init", "folder"}, set(self.host.routes))

    def test_before_anything_exists_it_names_a_directory_and_offers_to_make_it(self):
        self.register()
        state = self.call("state")
        self.assertTrue(state["needs_profile"])
        self.assertFalse(state["ready"])
        for slot in ("data_dir", "labs_dir", "genome_dir"):
            self.assertIn(str(self.state), state[slot],
                          f"{slot} is not inside the directory the host handed out")
        self.assertTrue(state["hint"].strip(), "an empty profile with nothing to do about it")

    def test_the_tab_prints_the_real_path_rather_than_an_example(self):
        self.register()
        _tab_id, _title, render = self.host.tabs[0]
        text = " ".join(c.get("text", "") for c in render.get("components", []))
        self.assertIn(str(self.state), text,
                      "the instructions name a path that is not this installation's")


class TestTheButtonThatLaysOutTheDirectory(HubSkillCase):

    def test_it_creates_the_layout_the_readmes_describe(self):
        self.register()
        self.assertTrue(self.call("init")["ok"])
        root = Path(os.environ["SCHOLION_REPO_DIR"])
        for rel in ("profile/index.md", "raw/lab/README.md", "genome/README.md"):
            self.assertTrue((root / rel).exists(), f"{rel} was not laid out")

    def test_a_second_press_writes_nothing(self):
        """Idempotent is not a convenience here: the button is next to the data."""
        self.register()
        self.call("init")
        root = Path(os.environ["SCHOLION_REPO_DIR"])
        labs = root / "profile" / "labs.json"
        mine = '{"_meta": {"mine": true}}'
        labs.write_text(mine, encoding="utf-8")
        again = self.call("init")
        self.assertEqual([], again.get("written"), "a second press wrote files")
        self.assertEqual(mine, labs.read_text(encoding="utf-8"), "it overwrote the owner's data")

    def test_pointing_at_a_folder_writes_nothing_into_it(self):
        """Write-path confinement, which the host treats as a critical rule.

        The person names any folder they like. `set_source_folder` moves a
        domain's JSON into the chosen folder for the domains that have one —
        `labs`, `medications`, `metrics` — so the domain this route passes
        decides whether the skill writes outside the directory the host gave it.
        """
        self.register()
        self.call("init")
        theirs = Path(tempfile.mkdtemp()).resolve() / "my-pdfs"
        theirs.mkdir()
        before = {p.name for p in theirs.iterdir()}

        self.assertTrue(self.call("folder", {"path": str(theirs)}).get("ok"))

        self.assertEqual(before, {p.name for p in theirs.iterdir()},
                         "the route wrote into a folder outside the state directory")
        root = Path(os.environ["SCHOLION_REPO_DIR"])
        self.assertTrue((root / "profile" / "sources.json").exists(),
                        "the choice was not recorded where it belongs")

    def test_a_folder_that_is_not_there_is_refused_and_says_so(self):
        self.register()
        self.call("init")
        self.assertIn("required", self.call("folder", {})["error"])
        missing = self.call("folder", {"path": str(self.state / "nowhere")})
        self.assertFalse(missing.get("ok"))
        self.assertTrue(missing.get("error"))


class TestItDoesNotAnswerAboutDataItDoesNotHave(HubSkillCase):

    def test_an_empty_directory_is_not_called_a_connected_genome(self):
        """`overview()["genome"]` is a report and is always present.

        Testing the dict for truth called a freshly created, empty directory a
        connected genome — the shape of wrong answer this product exists to
        refuse, produced by the part of it meant to introduce itself.
        """
        self.register()
        self.call("init")
        self.assertEqual("not connected", self.call("state")["genome"])

    def test_a_profile_it_cannot_read_is_not_reported_as_zeroes(self):
        self.register()
        self.call("init")
        root = Path(os.environ["SCHOLION_REPO_DIR"])
        (root / "profile" / "labs.json").write_text('{"markers": []}', encoding="utf-8")
        state = self.call("state")
        self.assertNotEqual(0, state["markers"], "an unreadable profile reported as an empty one")
        self.assertIn("could not be read", state["hint"])


if __name__ == "__main__":
    unittest.main()
