"""The tool names a model and a catalogue know are the ones the server offers.

A tool name is the interface a model calls and a client remembers: a saved
permission, a skill that names `sch_limits`, a catalogue listing reviewed with a
list of tools. Once the plugin is submitted to a catalogue, renaming a tool is
not a refactor — it is a new surface, with the old name answering nothing.

The list below is the set as of 0.5.11, the last release before the first
submission. A tool may be ADDED (append it here in the same change, with the
release it arrived in); none may disappear or change its name. The same rule the
public contract holds for command names, held for the other door.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import mcp_server, ouroboros_tools

#: 39 tools, frozen at 0.5.11 (27.09.2026).
FROZEN = frozenset({
    "sch_acmg", "sch_analyze_labs", "sch_array", "sch_brief", "sch_capabilities",
    "sch_check_drug_gene", "sch_check_prescription", "sch_clinvar_findings", "sch_flag_rate",
    "sch_focus", "sch_focus_log", "sch_genome_lookup", "sch_genome_status", "sch_goal",
    "sch_goal_suggest", "sch_health_metrics", "sch_ingest_labs", "sch_lab_draw", "sch_lifestyle",
    "sch_limits", "sch_lipid_genetics", "sch_longevity", "sch_marker_propose", "sch_medications",
    "sch_overview", "sch_phenoage", "sch_provenance", "sch_prs", "sch_radar", "sch_recompute",
    "sch_rules", "sch_screen", "sch_second_opinion", "sch_selfcheck", "sch_sources",
    "sch_suggest_tests", "sch_system", "sch_update", "sch_version",
})


class TestNoToolWasRenamed(unittest.TestCase):

    def test_every_frozen_name_is_still_offered(self):
        offered = {t.name for t in ouroboros_tools.get_tools()}
        self.assertEqual(set(), FROZEN - offered,
                         "a tool a model or a catalogue knows by name is gone")

    def test_the_server_lists_what_the_plugin_registers(self):
        listed = {d["name"] for d in mcp_server.tool_descriptors("2025-06-18")}
        self.assertEqual({t.name for t in ouroboros_tools.get_tools()}, listed)

    def test_a_new_tool_is_written_down_here(self):
        offered = {t.name for t in ouroboros_tools.get_tools()}
        self.assertEqual(set(), offered - FROZEN,
                         "a new tool: add it to FROZEN in the same change")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
