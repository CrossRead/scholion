"""The Agent Plugins package says what it is, and the launcher installs nothing.

`agent-plugin/` is this product in the portable package format five vendors
agreed on in August 2026: `plugin.json`, a `skills/` folder of Agent Skills, and
`mcp.json` describing MCP servers. Nothing in it is new — it is the skill folder
and the tool server in one directory a client imports in a single step.

Two properties are worth a guard rather than a reading.

The first is the numbers, for the reason task 196 was opened: a manifest is prose
carrying facts the build already knows, and the one in the hub stood seven
releases stale because nobody compared it.

The second is what the launcher does when the engine is absent. The format
carries no install step by design, so the honest options were a bare command name
(which conformance forbids relying on) or a launcher of our own. It refuses and
names the command; a launcher that quietly installed software in order to read
somebody's genome would be the wrong kind of quiet, and «it used to refuse» is
exactly the kind of thing that decays without a test.
"""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path

ROOT = support.ROOT
PLUGIN = ROOT / "agent-plugin"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/"


class Package(unittest.TestCase):

    def setUp(self):
        if not (PLUGIN / "plugin.json").is_file():
            self.skipTest("the plugin folder travels with the repository, not with the package")

    def manifest(self) -> dict:
        return json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))

    def mcp(self) -> dict:
        return json.loads((PLUGIN / "mcp.json").read_text(encoding="utf-8"))


class TestTheManifestAgreesWithTheBuild(Package):

    def test_it_declares_the_schema_of_the_version_it_targets(self):
        self.assertEqual(SCHEMA + "plugin.schema.json", self.manifest()["$schema"])
        self.assertEqual(SCHEMA + "mcp.schema.json", self.mcp()["$schema"])

    def test_the_version_it_declares_is_the_version_that_ships(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, self.manifest()["version"])

    def test_the_skill_folder_is_named_after_the_plugin(self):
        name = self.manifest()["name"]
        self.assertTrue((PLUGIN / "skills" / name / "SKILL.md").is_file(),
                        f"the manifest is called «{name}» and no skill folder answers to it")

    def test_it_carries_no_field_the_schema_forbids(self):
        allowed = {"$schema", "name", "version", "description", "author", "homepage",
                   "repository", "license", "keywords", "extensions"}
        self.assertEqual(set(), set(self.manifest()) - allowed)


class TestTheSkillIsTheSameSkill(Package):
    """One edition, laid out mechanically. A second hand-kept copy is how the
    hub's entry lost a field nobody was comparing."""

    def test_the_entry_is_byte_for_byte_the_public_edition(self):
        # The source tree keeps the edition in share/skill/; the built package
        # keeps the same bytes where the engine prints them from.
        for name in ("SKILL.md", "INSTRUCTION.md"):
            source = next(p for p in (ROOT / "share" / "skill" / name,
                                      ROOT / "src" / "scholion" / "skill" / name) if p.is_file())
            with self.subTest(file=name):
                self.assertEqual(source.read_bytes(),
                                 (PLUGIN / "skills" / "scholion" / name).read_bytes(),
                                 "run `python3 src/tools/sync_rules.py --write`")


class TestTheServerEntry(Package):

    def server(self) -> dict:
        servers = self.mcp()["mcpServers"]
        self.assertEqual(1, len(servers))
        return next(iter(servers.values()))

    def test_the_command_is_plugin_relative_and_present(self):
        """A bare name would lean on how the client resolves PATH, and the
        specification says a conforming plugin must not depend on that."""
        command = self.server()["command"]
        self.assertTrue(command.startswith("./"), f"«{command}» is not plugin-relative")
        target = PLUGIN / command[2:]
        self.assertTrue(target.is_file(), f"{command} is named and is not there")
        self.assertTrue(os.access(target, os.X_OK), f"{command} is not executable")

    def test_it_speaks_over_stdio(self):
        self.assertEqual("stdio", self.server()["type"])


class TestTheLauncherRefusesRatherThanInstalls(Package):

    def run_with_nothing_on_the_path(self):
        """An environment where no engine can be found: an empty PATH, so even
        `python3` is out of reach, and no data directory from a client."""
        command = self.server_command()
        return subprocess.run(["/bin/sh", str(PLUGIN / command[2:])],
                              env={"PATH": "/nonexistent-for-this-test", "HOME": "/nonexistent"},
                              capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def server_command(self) -> str:
        return next(iter(self.mcp()["mcpServers"].values()))["command"]

    def test_it_refuses_and_says_what_to_run(self):
        r = self.run_with_nothing_on_the_path()
        self.assertNotEqual(0, r.returncode, "a launcher that cannot start must not exit clean")
        self.assertIn("scholion", r.stderr)
        self.assertIn("install scholion", r.stderr,
                      "the refusal does not name the command that fixes it")

    def test_it_says_plainly_that_it_installs_nothing(self):
        r = self.run_with_nothing_on_the_path()
        self.assertIn("does not", r.stderr)
        self.assertIn("install it for you", r.stderr)

    def test_an_engine_outside_the_path_is_still_found(self):
        """A desktop app started from the Dock gets the system PATH only. An
        engine installed per user, in ~/.local/bin, is found there by name."""
        import tempfile
        home = Path(tempfile.mkdtemp(prefix="plughome_")).resolve()
        self.addCleanup(__import__("shutil").rmtree, home, True)
        exe = home / ".local" / "bin" / "scholion"
        exe.parent.mkdir(parents=True)
        exe.write_text("#!/bin/sh\necho started \"$1\"\n", encoding="utf-8")
        exe.chmod(0o755)
        r = subprocess.run(["/bin/sh", str(PLUGIN / self.server_command()[2:])],
                           env={"PATH": "/nonexistent-for-this-test", "HOME": str(home)},
                           capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual((0, "started mcp"), (r.returncode, r.stdout.strip()), r.stderr)

    def test_the_script_runs_no_installer_itself(self):
        """The property, not the wording: outside the message it prints, the
        script never calls a package manager."""
        text = (PLUGIN / self.server_command()[2:]).read_text(encoding="utf-8")
        body = text.split("{\n    echo", 1)[0]
        for installer in ("pip", "pipx", "npm", "curl", "wget", "easy_install"):
            with self.subTest(installer=installer):
                self.assertNotIn(installer, body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
