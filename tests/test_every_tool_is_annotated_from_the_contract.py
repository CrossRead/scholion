"""What a client is told about a tool before calling it is what the tool does.

MCP gives a server three hints per tool — it only reads, a write replaces
rather than adds, it reaches outside the machine — and a title a person can
read. A client decides from them what to ask the person before a call; the
Claude catalogue reads them as promises and holds a submission on a wrong one.

They are derived in `contract.tool_annotations` from WRITES and from the
network map `OPEN_WORLD`, not typed beside 39 tools. This file holds the
derivation to the build:

* every tool has a title in both languages, not a raw catalogue key;
* `readOnlyHint` is false exactly for the tools that answer a command in WRITES;
* `destructiveHint` is named only on writes;
* `openWorldHint` is true exactly for the tools in `OPEN_WORLD` — and the map
  itself is measured: every tool is run with the network cut at `net._open`,
  and a host asked for that the map does not name fails here;
* the union of the map is inside the inventory `scholion assistant` prints, so
  the two statements about the network cannot drift apart.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

import support
from scholion import contract, mcp_server, ouroboros_tools

#: An argument for every parameter that sends a tool to the network: a name no
#: local base knows, so the lookup has to go outside. The rest are the same
#: harmless values the wire test uses.
ARG = {"drug": "zzzunknowndrug", "rsid": "rs999999999", "folder": "", "day": "2026-01-01",
       "key": "audit_key", "names": "audit name", "date": "2026-01-02", "refresh": True}


class _Lang:
    def __init__(self, code):
        self.code = code

    def __enter__(self):
        self.old = os.environ.get("SCHOLION_LANG")
        os.environ["SCHOLION_LANG"] = self.code

    def __exit__(self, *a):
        if self.old is None:
            os.environ.pop("SCHOLION_LANG", None)
        else:
            os.environ["SCHOLION_LANG"] = self.old


class TestTheHintsAreDerived(unittest.TestCase):

    def tools(self, version="2025-06-18"):
        return {d["name"]: d for d in mcp_server.tool_descriptors(version)}

    def test_every_tool_has_a_title_in_both_languages(self):
        for code in ("en", "ru"):
            with _Lang(code):
                for name, d in self.tools().items():
                    with self.subTest(lang=code, tool=name):
                        self.assertTrue(d.get("title"), f"{name} has no title")
                        self.assertNotIn("⟦", d["title"])
                        self.assertEqual(d["title"], d["annotations"]["title"])

    def test_read_only_is_exactly_what_writes_nothing(self):
        for name, d in self.tools().items():
            writes = any(c in contract.WRITES for c in contract.tool_commands(name))
            with self.subTest(tool=name):
                self.assertEqual(not writes, d["annotations"]["readOnlyHint"])

    def test_the_writes_are_the_six_the_canon_names(self):
        writers = sorted(n for n, d in self.tools().items() if not d["annotations"]["readOnlyHint"])
        self.assertEqual(["sch_focus_log", "sch_ingest_labs", "sch_lab_draw",
                          "sch_marker_propose", "sch_recompute", "sch_update"], writers)

    def test_destructive_is_said_only_of_a_write(self):
        self.assertTrue(contract.DESTRUCTIVE <= set(self.tools()))
        for name, d in self.tools().items():
            ann = d["annotations"]
            with self.subTest(tool=name):
                if ann["readOnlyHint"]:
                    self.assertNotIn("destructiveHint", ann)
                else:
                    self.assertEqual(name in contract.DESTRUCTIVE, ann["destructiveHint"])

    def test_open_world_is_exactly_the_network_map(self):
        self.assertTrue(set(contract.OPEN_WORLD) <= set(self.tools()))
        for name, d in self.tools().items():
            with self.subTest(tool=name):
                self.assertEqual(name in contract.OPEN_WORLD, d["annotations"]["openWorldHint"])

    def test_the_map_is_inside_the_inventory_the_product_prints(self):
        from scholion import assistant
        printed = set(assistant._audit_core()["network_hosts"])
        mapped = {h for v in contract.OPEN_WORLD.values() for h in v["hosts"]}
        self.assertEqual(set(), mapped - printed,
                         "the tool map names a host the network inventory does not know")
        for name, v in contract.OPEN_WORLD.items():
            with self.subTest(tool=name):
                self.assertTrue(v["why"].strip())

    def test_an_old_client_is_handed_neither(self):
        for d in mcp_server.tool_descriptors("2024-11-05"):
            self.assertNotIn("annotations", d)
            self.assertNotIn("title", d)
        for d in mcp_server.tool_descriptors("2025-03-26"):
            self.assertIn("annotations", d)
            self.assertNotIn("title", d)


class TestTheNetworkMapIsMeasured(unittest.TestCase):
    """Every tool run once with the network cut where every request passes."""

    def setUp(self):
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)
        root = Path(tempfile.mkdtemp(prefix="openworld_")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(support.FIXTURE_PROFILE, root / "profile")
        self.addCleanup(support.pin_profile(root / "profile"))
        self.addCleanup(support.pin_cache(root / "cache"))
        saved = {k: os.environ.get(k) for k in ("SCHOLION_REPO_DIR", "SCHOLION_OFFLINE")}

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        os.environ["SCHOLION_REPO_DIR"] = str(root)
        # The suite runs offline; here the switch is lifted so that each tool
        # goes as far as it would, and the one place a request leaves is cut.
        os.environ.pop("SCHOLION_OFFLINE", None)
        (root / "empty").mkdir()
        self.empty = str(root / "empty")

        from scholion import net, prs, upgrade
        self.asked = []

        def cut(url, timeout, headers):
            self.asked.append(urllib.parse.urlsplit(url).hostname)
            raise OSError("cut by the test: no network")
        for mod, attr, value in (
                (net, "_open", cut),
                # The once-a-day question about a newer build rides on any tool
                # and is the product's, not the tool's (contract.OPEN_WORLD).
                (upgrade, "session_note", lambda *a, **k: ""),
                # The polygenic sidecar is started through uvx, not through
                # net._open; a tool that starts it has reached the network.
                (prs, "_MCP", self._sidecar)):
            old = getattr(mod, attr)
            self.addCleanup(setattr, mod, attr, old)
            setattr(mod, attr, value)

    def _sidecar(self, *a, **k):
        self.asked.append("uvx")
        raise OSError("cut by the test: no sidecar")

    def test_no_tool_asks_a_host_its_map_does_not_name(self):
        for name, params, required, handler in ouroboros_tools._TOOLS:
            args = {p: (self.empty if p == "folder" else ARG[p]) for p in params if p in ARG}
            self.asked.clear()
            mcp_server.call_tool(name, args)
            reached = {h for h in self.asked if h}
            allowed = set(contract.OPEN_WORLD.get(name, {}).get("hosts", ()))
            with self.subTest(tool=name, reached=sorted(reached)):
                self.assertEqual(set(), reached - allowed,
                                 f"{name} asked for {sorted(reached - allowed)}; add them to "
                                 f"contract.OPEN_WORLD with the reason, or stop the request")

    def test_the_lookups_the_map_names_do_go_out(self):
        """The other direction: a tool mapped as reaching out and never doing so
        would be a hint that frightens a client for nothing."""
        for name in ("sch_check_drug_gene", "sch_check_prescription", "sch_genome_lookup"):
            _n, params, _r, _h = next(t for t in ouroboros_tools._TOOLS if t[0] == name)
            self.asked.clear()
            mcp_server.call_tool(name, {p: ARG[p] for p in params if p in ARG})
            with self.subTest(tool=name):
                self.assertTrue(set(self.asked) & set(contract.OPEN_WORLD[name]["hosts"]),
                                f"{name} is mapped as reaching out and asked nothing")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
