"""Deterministic logic (a hybrid: the code computes facts and flags, the LLM words them).

One capability, one facade. The domain logic lives in the submodules --
_helpers, labs, corridor, pgx, genomics, goals, lifestyle, sources,
profile_view -- and this file re-exports EVERY name, private ones included, at the address
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
    change_floor,
    CHANGE_MIN_PAIRS,
    analyze_labs,
    same_day_repeats,
    _latest_value,
    _eval_condition,
    _PRIORITY_ORDER,
    _marker_last_date,
    suggest_tests,
)
from .corridor import (  # noqa: F401 -- the facade re-exports every name
    _sex_adjusted_bounds,
    point_corridor,
    flags_comparable,
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
from .panel_reading import CLOSES_WITH, NO_TABLE, UNREAD_CLASSES, read_state, unread_block, unread_class, unread_line  # noqa: F401
from .panel_form import (  # noqa: F401 -- the facade re-exports every name
    KINDS as PANEL_KINDS,
    VERDICTS as PANEL_VERDICTS,
    one_language,
    gate,
    kind_order,
    scan_for,
    gene_row, bases_read,
    verdict as panel_verdict,
    verdict_line as panel_verdict_line,
)
from .routes import ROUTE_CLASSES, ROUTE_ORDER, ROUTE_LEVELS, ROUTE_CONDITIONAL, routes_book, route_refusal, correction_routes_for  # noqa: F401
from .panel_book import on_demand_panels, positions_by_marker  # noqa: F401
from .system_panels import (  # noqa: F401 -- the facade re-exports every name
    MODES,
    FINDING_GRADE,
    NOT_A_FINDING,
    RECESSIVE,
    STALE_MONTHS,
    REGISTERS,
    BASKETS,
    QUESTION_ORIGINS,
    POLYGENIC_HIGH_PERCENTILE,
    domains,
    systems,
    prs_system_map,
    system,
    genes_index,
    marker_systems, marker_systems_all,
    class_systems,
    prescriptions,
    composition,
)
from .screening import (  # noqa: F401 -- the facade re-exports every name
    screen,
    disease_classes,
    verdict as screen_verdict,
    verdict_line as screen_verdict_line,
    VERDICTS as SCREEN_VERDICTS,
)
from .decision import (  # noqa: F401 -- the facade re-exports every name
    KINDS,
    VERDICTS,
    curated_genes,
    classify,
    verdict,
    verdict_line,
    variant_state,
    VARIANT_STATES,
)
from .genomics import (
    COVERAGE_STATES,
    HALF_DEPTH_BELOW,
    SEX_CHROMOSOMES,
    BELOW_MEDIAN_POINTS,
    POORLY_READ_BELOW,
    gene_coverage,  # noqa: F401 -- the facade re-exports every name
    gene_verdict,
    locus_basis,
    BASIS_ORDER,
    NARROW_INPUTS,
    NARROW_FOR_SCORES,
    genome_lookup,
    genome_status,
    clinvar_findings,
    clinvar_for_gene,
    gene_layers,
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
from .sources import (
    AGEING_AFTER_DAYS,
    build_freshness,  # noqa: F401 -- the facade re-exports every name
    provenance,
)
from .pgx import (
    cpic_snapshot,  # noqa: F401 -- the facade re-exports every name
    compute_phenotype,
    name_matches,
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
from .brief_review import (  # noqa: F401 -- the facade re-exports every name
    brief_review,
)
from .panel_catalogue import (  # noqa: F401 -- the facade re-exports every name
    panel_description,
)
from .panel_gate import LINKS  # noqa: F401
from .panel_gate import HGVS, BATCH, REVIEWERS, CONFIRM_BELOW_AF, locus, risk_on_plus, refusal, review_state, reviewed_on, copies, needs_confirmation, legend, ladder, level_of  # noqa: F401,E501
from .panel_labs import panel_view  # noqa: F401 -- a system's long panel, shown not scored
from .pgx_labels import phenotype_words  # noqa: F401 -- the facade re-exports every name
from .profile_view import (  # noqa: F401 -- the facade re-exports every name
    load_profile,
    overview,
    _metrics_overview,
    metrics_summary,
)
from .prs_quality import (  # noqa: F401 -- the facade re-exports every name
    P90_P10_SD, annotate_measurement, effect_size,
)
from .targets import (  # noqa: F401 -- the facade re-exports every name
    outside_target, target_side, target_view, clinician_targets_view,
)
