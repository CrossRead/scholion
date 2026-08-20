"""Deterministic logic (a hybrid: the code computes facts and flags, the LLM words them).

One capability, one facade. The domain logic lives in the submodules --
_helpers, labs, pgx, genomics, goals, lifestyle, sources, profile_view --
and this file re-exports EVERY name, private ones included, at the address
the rest of the tree has always used: engine.<name>. Six consumers
(__init__, cli, server, ouroboros_tools, assistant, limits) and the tests
call through this facade; none of them needed a single edit when the flat
2800-line engine.py became this package.

All functions return a STRUCTURE (dict/list) -- not text. Formatting into a
string for the tools/CLI is in format.py. That way one logic feeds every face.
"""
from __future__ import annotations

from ._helpers import (  # noqa: F401 -- the facade re-exports every name
    _OPS,
    _recent,
    DISCLAIMER,
    _match_count,
    _basis,
    _basis_note,
    _active_names_by_class,
    _brief_num,
)
from .labs import (  # noqa: F401 -- the facade re-exports every name
    _latest,
    _flag_value,
    MOVE_MIN_PCT,
    MOVE_MIN_SD,
    _personal_move,
    _decision_limits,
    NEAR_LIMIT_FRACTION,
    AUTHOR_SETTINGS,
    _near_limit,
    _trend,
    analyze_labs,
    same_day_repeats,
    _latest_value,
    _eval_condition,
    _PRIORITY_ORDER,
    _marker_last_date,
    suggest_tests,
)
from .goals import (  # noqa: F401 -- the facade re-exports every name
    _goal_series,
    _goal_lv,
    _goal_merge,
    _goal_num,
    _goal_now,
    goal_dashboard,
    _GOAL_MIN_POINTS,
    _GOAL_MIN_SPAN_MONTHS,
    _GOAL_MIN_GAIN,
    _months_between,
    _marker_direction,
    _meets,
    _best_of,
    _guideline_candidate,
    suggest_goal_targets,
)
from .genomics import (  # noqa: F401 -- the facade re-exports every name
    genome_lookup,
    genome_status,
    clinvar_findings,
    _penetrance_block,
    acmg_findings,
    apoe,
    PRS_DISCLAIMER,
    prs_method_caveats,
    _annotate_prs_evidence,
    prs_findings,
    genome_updates,
    longevity_findings,
    _PCSK9_LOF,
    _PCSK9_WAITING,
    _LPA_PGS,
    _copies_of,
    lipid_genetics,
)
from .sources import (  # noqa: F401 -- the facade re-exports every name
    provenance,
)
from .pgx import (  # noqa: F401 -- the facade re-exports every name
    compute_phenotype,
    check_drug_gene,
    _guidance_for,
    _check_drug_online,
    _classes_for,
    _SEV_ORDER,
    check_interactions,
    _assess_gene,
    _genome_for_drug,
    _labs_for_drug,
    _rsids_for_genes,
    clinvar_for_drug,
    _dose_context,
    _own_safety_flags,
    check_new_prescription,
)
from .lifestyle import (  # noqa: F401 -- the facade re-exports every name
    _WATCHLIST,
    _RADAR_DOMAINS,
    _wear_status,
    lifestyle,
    _prev_point,
    _marker_health_at,
    _marker_health,
    health_radar,
    _lifestyle_overview,
    second_opinion,
    _BRIEF_TOKEN,
    _brief_lab,
    _brief_life,
    _brief_goal,
    _brief_resolve,
    _brief_newest,
    _brief_snapshot_item,
    lifestyle_brief,
    _focus_nights,
    _focus_mean,
    _focus_metric,
    _focus_lever_check,
    _focus_clock,
    _focus_journal_split,
    _focus_evidence,
    focus_dashboard,
)
from .profile_view import (  # noqa: F401 -- the facade re-exports every name
    load_profile,
    overview,
    _metrics_overview,
    metrics_summary,
)
