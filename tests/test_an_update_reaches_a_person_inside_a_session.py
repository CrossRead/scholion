"""An update reaches a person inside an assistant's session, and is installed only on their word.

Somebody who uses the package through an assistant never sees the page's update
note, so a newer version went unnoticed (owner, 14.09.2026). The registry is now
asked at most once a day and never offline; the first tool answer of a session
says a newer version exists; and the install runs the command that fits this
environment only when a person confirmed it — never inside a source checkout.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import updates, upgrade


def _fetch(version, asked):
    def f(url):
        asked.append(url)
        return {"info": {"version": version}} if version else None
    return f


class _Cache(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="upg_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(support.pin_cache(self.root / "cache"))
        upgrade._SAID = False
        self.addCleanup(setattr, upgrade, "_SAID", False)


class TestTheNotice(_Cache):

    def test_a_newer_version_is_remembered_for_a_day_and_asked_again_after(self):
        asked = []
        n = upgrade.notice(fetch=_fetch("99.0.0", asked), now=1000.0)
        self.assertEqual(("newer", "99.0.0", False), (n["status"], n["latest"], n["from_cache"]))
        again = upgrade.notice(fetch=_fetch("99.0.0", asked), now=1000.0 + 3600)
        self.assertTrue(again["from_cache"])
        self.assertEqual(1, len(asked), "a check younger than a day asked the registry again")
        upgrade.notice(fetch=_fetch("99.0.0", asked), now=1000.0 + 25 * 3600)
        self.assertEqual(2, len(asked))
        self.assertEqual({updates.REGISTRY}, set(asked))

    def test_an_unreachable_registry_is_not_remembered_as_current(self):
        asked = []
        self.assertEqual("unreachable", upgrade.notice(fetch=_fetch(None, asked), now=1.0)["status"])
        upgrade.notice(fetch=_fetch(None, asked), now=2.0)
        self.assertEqual(2, len(asked))

    def test_offline_asks_nothing(self):
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}), \
                mock.patch("scholion.net.get_json", side_effect=AssertionError("asked")):
            self.assertEqual("offline", upgrade.notice(now=5.0)["status"])

    def test_a_note_for_another_build_is_not_reused(self):
        (self.root / "cache").mkdir(parents=True)
        (self.root / "cache" / upgrade.NOTICE_FILE).write_text(json.dumps(
            {"status": "newer", "installed": "0.0.1", "latest": "99.0.0", "checked_at": 10.0}),
            encoding="utf-8")
        asked = []
        self.assertFalse(upgrade.notice(fetch=_fetch(updates.installed(), asked), now=11.0)["from_cache"])
        self.assertEqual(1, len(asked))


class TestTheSessionNote(_Cache):

    def test_said_once_and_only_when_newer(self):
        with mock.patch.object(upgrade, "notice", return_value={"status": "newer", "latest": "99.0.0",
                                                                "installed": "0.5.2"}):
            first = upgrade.session_note()
            self.assertIn("99.0.0", first)
            self.assertNotIn("⟦", first)
            self.assertEqual("", upgrade.session_note())
        upgrade._SAID = False
        with mock.patch.object(upgrade, "notice", return_value={"status": "current"}):
            self.assertEqual("", upgrade.session_note())
        upgrade._SAID = False
        with mock.patch.object(upgrade, "notice", side_effect=RuntimeError("no disk")):
            self.assertEqual("", upgrade.session_note())


class TestTheRoute(unittest.TestCase):

    def test_each_environment_gets_its_own_command(self):
        tmp = Path(tempfile.mkdtemp(prefix="route_")).resolve()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = tmp / "lib" / "site-packages" / "scholion"
        pkg.mkdir(parents=True)
        self.assertEqual("pipx", upgrade.route("/home/u/.local/share/pipx/venvs/scholion", pkg)["kind"])
        self.assertEqual("uv", upgrade.route("/home/u/.local/share/uv/tools/scholion", pkg)["kind"])
        pip = upgrade.route("/usr/local", pkg, "/usr/local/bin/python3")
        self.assertEqual(["/usr/local/bin/python3", "-m", "pip", "install", "--upgrade", "scholion"], pip["command"])
        self.assertTrue(pip["installable"])
        repo = tmp / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "pyproject.toml").write_text("", encoding="utf-8")
        (repo / "src" / "scholion").mkdir(parents=True)
        src = upgrade.route("/usr/local", repo / "src" / "scholion")
        self.assertEqual(("source", False), (src["kind"], src["installable"]))
        self.assertIn("pull", src["command"])


class TestTheInstall(_Cache):

    def _pip(self):
        return {"kind": "pip", "installable": True, "command": ["python3", "-m", "pip", "install", "--upgrade", "scholion"]}

    def test_nothing_runs_without_a_confirmation(self):
        with mock.patch.object(upgrade, "route", return_value=self._pip()):
            r = upgrade.install(confirm=False, run=mock.Mock(side_effect=AssertionError("ran")))
        self.assertEqual((False, "not_confirmed"), (r["ok"], r["reason"]))

    def test_a_source_tree_is_told_to_pull_and_nothing_runs(self):
        with mock.patch.object(upgrade, "route", return_value={"kind": "source", "installable": False,
                                                               "command": ["git", "pull"]}):
            r = upgrade.install(confirm=True, run=mock.Mock(side_effect=AssertionError("ran")))
        self.assertEqual((False, "source_tree"), (r["ok"], r["reason"]))

    def test_offline_installs_nothing(self):
        with mock.patch.object(upgrade, "route", return_value=self._pip()), \
                mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}):
            r = upgrade.install(confirm=True, run=mock.Mock(side_effect=AssertionError("ran")))
        self.assertEqual((False, "offline"), (r["ok"], r["reason"]))

    def test_a_confirmed_install_runs_the_route_and_says_to_restart(self):
        ran = []
        def run(cmd, **kw):
            ran.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "Successfully installed scholion-99.0.0", "")
        with mock.patch.object(upgrade, "route", return_value=self._pip()), \
                mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": ""}):
            r = upgrade.install(confirm=True, run=run, version_after=lambda: "99.0.0")
        self.assertEqual([self._pip()["command"]], ran)
        self.assertEqual((True, "installed", "99.0.0", True), (r["ok"], r["reason"], r["after"], r["restart"]))

    def test_a_failed_install_says_why(self):
        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, "", "error: externally-managed-environment")
        with mock.patch.object(upgrade, "route", return_value=self._pip()), \
                mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": ""}):
            r = upgrade.install(confirm=True, run=run)
        self.assertEqual((False, "failed", 1), (r["ok"], r["reason"], r["code"]))
        self.assertIn("externally-managed", r["tail"])


class TestTheFaces(_Cache):

    def tools(self):
        from scholion import ouroboros_tools as ot
        return ot, {tool.name: tool for tool in ot.get_tools()}

    def test_the_version_tool_reads_and_the_update_tool_installs_only_on_yes(self):
        ot, tools = self.tools()
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}):
            self.assertIn(updates.installed(), tools["sch_version"].handler(ot.ToolContext()))
        refused = {"ok": False, "reason": "not_confirmed", "installed": "0.5.2",
                   "route": {"command": ["pip", "install"]}}
        with mock.patch.object(upgrade, "install", side_effect=lambda confirm=False: refused) as inst, \
                mock.patch.object(upgrade, "session_note", return_value=""):
            tools["sch_update"].handler(ot.ToolContext())
            tools["sch_update"].handler(ot.ToolContext(), confirm="true")
            tools["sch_update"].handler(ot.ToolContext(), confirm=True)
        self.assertEqual([mock.call(confirm=False), mock.call(confirm=True), mock.call(confirm=True)],
                         inst.call_args_list)

    def test_the_first_tool_answer_of_a_session_carries_the_note_once(self):
        ot, tools = self.tools()
        newer = {"status": "newer", "latest": "99.0.0", "installed": "0.5.2"}
        with mock.patch.object(upgrade, "notice", return_value=newer):
            first = tools["sch_rules"].handler(ot.ToolContext())
            second = tools["sch_rules"].handler(ot.ToolContext())
        self.assertIn("99.0.0", first)
        self.assertNotIn("99.0.0", second)

    def test_the_handshake_tells_the_model_to_ask_before_installing(self):
        from scholion import mcp_server
        text = mcp_server._instructions()
        self.assertIn("sch_version", text)
        self.assertIn("sch_update", text)
        self.assertIn("confirm=true", text)

    def test_the_contract_records_the_two_tools_and_the_fourth_kind(self):
        from scholion import contract
        self.assertEqual("sch_version", contract.PLUGIN["version"])
        self.assertEqual("sch_update", contract.PLUGIN["update"])
        self.assertIn("update", contract.INSTALLS)
        self.assertEqual("update", contract.PARITY["POST /api/update"])

    def test_the_command_line_answers_offline_and_a_source_tree_is_told_to_pull(self):
        code, out, err = support.run(["update"])
        self.assertEqual(0, code, err[-600:])
        self.assertIn("SCHOLION_OFFLINE", out)
        code, out, err = support.run(["update", "--yes"])
        self.assertEqual(0, code, err[-600:])
        self.assertIn("pull", out)

    def test_the_reports_name_every_outcome_without_a_hole(self):
        from scholion import format as fmt
        route = {"kind": "pip", "command": ["python3", "-m", "pip", "install", "--upgrade", "scholion"]}
        for n in ({"status": "newer", "latest": "9.9.9", "installed": "0.5.2", "route": route, "from_cache": True},
                  {"status": "newer", "latest": "9.9.9", "installed": "0.5.2", "route": {"kind": "source", "command": ["git", "pull"]}},
                  {"status": "current", "installed": "0.5.2", "route": route},
                  {"status": "offline", "route": route}, {"status": "unreachable", "route": route}):
            with self.subTest(notice=n["status"]):
                self.assertNotIn("⟦", fmt.update_report(n))
        for r in ({"reason": "installed", "installed": "0.5.2", "after": "9.9.9", "route": route},
                  {"reason": "already_current", "after": "0.5.2", "route": route},
                  {"reason": "not_confirmed", "route": route}, {"reason": "source_tree", "route": route},
                  {"reason": "offline", "route": route},
                  {"reason": "failed", "code": 1, "tail": "boom", "route": route},
                  {"reason": "failed", "code": None, "route": route}):
            with self.subTest(install=r["reason"]):
                self.assertNotIn("⟦", fmt.update_install_report(r))


if __name__ == "__main__":
    unittest.main()
