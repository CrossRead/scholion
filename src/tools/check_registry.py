"""Reviewed paths from result producers to semantic and interface checks."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from check_interfaces import READS, select
from run_tests import ROOT


@dataclass(frozen=True)
class Family:
    key: str
    producers: tuple[str, ...]
    tests: tuple[str, ...]
    commands: tuple[str, ...]
    narrow: tuple[str, ...] = ()


FAMILIES = (
    Family('variant-reading',
           ('variant_readings.py', 'genome.py', 'engine/panel_genotype.py', 'engine/panel_intake.py',
            'web/gene-cards.js', 'web/gene-cards.css'),
           ('variant_readings', 'variant_reading_keeps_the_effect_identity',
            'gene_card_component_boundary', 'gene_cards_have_one_shape',
            'thematic_cards_preserve_personal_readings', 'gene_screening_states_reach_the_cards',
            'genetic_lab_comparison', 'prescribing_claims_require_their_own_basis'),
           ('genome', 'drug', 'system', 'clinvar', 'acmg'), ('variant_readings.py',)),
    Family('labs-and-thresholds',
           ('lab_observations.py', 'engine/labs.py', 'measurements.py', 'period_summary.py',
            'trend_qualification.py', 'threshold_basis.py', 'web/measurements.js'),
           ('attention_feed', 'measurements_are_shared_by_every_view', 'trend_qualification',
            'measurement_interface_parity', 'insight_facts_keep_bounds_and_dates',
            'a_threshold_and_its_action_need_their_own_basis', 'non_scalar_lab_results'),
           ('labs', 'overview', 'system')),
    Family('findings',
           ('genome.py', 'finding_context.py', 'acmg_scan.py', 'acmg_identity.py', 'clinvar_reference.py',
            'engine/screening.py', 'engine/thematic_panels.py', 'engine/genomics.py'),
           ('findings_distinguish_carriage_from_disease', 'an_acmg_table_is_read_with_its_provenance',
            'acmg_content_can_be_verified_after_a_move', 'a_class_is_never_clear_where_it_was_not_read',
            'longevity_nine_source_passports', 'thematic_gene_panels', 'lipid_genetics'),
           ('clinvar', 'acmg', 'genome', 'genome-status', 'screen', 'limits', 'longevity', 'lipid-genetics')),
    Family('prescribing',
           ('engine/pgx.py', 'prescribing_basis.py', 'interaction_basis.py', 'monitoring_basis.py'),
           ('prescribing_claims_require_their_own_basis', 'interaction_claims_require_their_own_basis',
            'monitoring_claims_require_their_own_basis', 'interaction_studies_do_not_change_population'),
           ('drug', 'prescription', 'medications')),
    Family('pgs',
           ('pgs_validation.py', 'pgs_reference.py', 'pgs_results.py', 'pgs_scoring.py',
            'prs.py', 'prs_recompute.py', 'engine/insight_links.py'),
           ('pgs_saved_values_remain_visible', 'pgs_independent_reference', 'pgs_called_alleles',
            'pgs_recalculation_is_installed_and_atomic', 'a_new_pgs_client_gets_a_genome_population',
            'a_polygenic_score_is_not_computed_for_an_organ_you_lack',
            'a_polygenic_score_stands_beside_the_system_and_never_inside_its_verdict',
            'attention_feed'),
           ('prs', 'recompute', 'overview', 'system'), ('pgs_validation.py',)),
    Family('review-and-composition',
           ('insight_history.py', 'conclusion_basis.py', 'recompute.py', 'web/view-lifecycle.js'),
           ('attention_feed', 'insight_source_witnesses', 'system_insight_synthesis',
            'view_lifecycle', 'a_recompute_runs_what_an_update_asks_and_shows_how_far_it_is',
            'the_recompute_path_is_one_step_on_every_face'),
           ('overview', 'system', 'insight-snapshot', 'recompute'), ('insight_history.py',)),
    Family('import-and-reconcile',
           ('ingest_labs.py', 'ingest_studies.py', 'ingest_fhir.py', 'import_csv.py',
            'reconcile.py', 'engine/sources.py'),
           ('fhir_import', 'fhir_preserves_measurement_identity', 'ingest_reads_a_table',
            'lab_dir_boundary', 'a_long_ingest_reports_how_far_it_is', 'sources_import',
            'a_point_of_the_same_draw_replaces_rather_than_doubles', 'server_guard'),
           ('sources', 'labs')),
    Family('wearables-phenotype-and-goals',
           ('garmin.py', 'wearables.py', 'goal_basis.py', 'engine/goals.py', 'engine/lifestyle.py'),
           ('the_wearables_file_is_read_through_one_door', 'cgm_reports_keep_measurement_kinds',
            'measurements_are_shared_by_every_view', 'a_goal_names_where_it_came_from',
            'a_target_the_clinician_set_stands_beside_the_corridor', 'proposed_targets_need_their_own_support'),
           ('metrics', 'lifestyle', 'goal', 'goal-suggest', 'focus')),
    Family('derived-estimates',
           ('clinical_estimates.py', 'engine/validated.py'),
           ('clinical_estimates', 'fib4_never_borrows_from_another_draw',
            'every_conclusion_carries_a_source_and_a_mechanism'),
           ('overview', 'system')),
    Family('associations-and-insights',
           ('insight_basis.py', 'insight_synthesis.py', 'engine/insights.py', 'engine/insight_events.py',
            'engine/insight_links.py'),
           ('attention_feed', 'insight_source_witnesses', 'system_insight_synthesis',
            'genetic_lab_comparison', 'radar_reads_cards_together'),
           ('overview', 'system', 'radar')),
    Family('proposals-visit-and-assistant',
           ('test_proposals.py', 'engine/visit.py', 'visit_focus.py', 'engine/brief_review.py',
            'web/system-views.js', 'web/system-views.css'),
           ('test_orders_need_their_own_support', 'visit_focus', 'system_view_component',
            'a_brief_block_due_for_a_review_opens_what_changed', 'every_door_of_the_local_server_answers'),
           ('overview', 'brief', 'focus', 'focus-log', 'suggest-tests', 'second-opinion')),
)


# Independent acceptance witnesses. The owning producer is listed first in
# each family. These inputs and failure states guide review and do not stand in
# for the executable tests listed above.
WITNESSES = {
    'import-and-reconcile': ('PDF, FHIR, delimited table and dictated entry',
                             'source identity, unit and draw survive correction',
                             'unchanged, unknown unit, stale approval'),
    'labs-and-thresholds': ('dated observations, lab intervals and separately curated thresholds',
                            'measured value and applicable interval retain distinct origins',
                            'bound, incomparable method, old result and exact threshold'),
    'wearables-phenotype-and-goals': ('device exports, dated manual points and confirmed targets',
                                     'provider and time precision survive selection',
                                     'unsupported device, wrong export, competing devices'),
    'derived-estimates': ('dated inputs and applicable clinical rule',
                          'formula applicability and input dates accompany the result',
                          'missing input, mixed draws, stale or retired estimate'),
    'variant-reading': ('VCF, array, recorded calls and prepared scoring sites',
                        'coordinate, allele and quality establish reading identity',
                        'other ALT, mismatched coordinate, covered reference, unread'),
    'findings': ('identified reading, curated association and versioned reference',
                 'classification and inheritance retain their own scope',
                 'absent coverage, unsupported inheritance, legacy record'),
    'prescribing': ('recorded medication, PGx call, clinical reference and monitoring history',
                    'each prescribing, interaction or monitoring claim has its own basis',
                    'missing reading, incompatible population or unsupported action'),
    'pgs': ('prepared scoring sites, score inputs and population assignment',
            'scored alleles, reference and coverage remain separate',
            'unknown population, insufficient coverage, cancelled or interrupted scoring'),
    'associations-and-insights': ('qualified measurements, genotype and versioned rule',
                                  'each event points back to distinct supporting facts',
                                  'inapplicable genotype, incomparable value, missing support'),
    'proposals-visit-and-assistant': ('recorded facts, candidate questions and curated wording',
                                     'questions and preferences remain separate from recorded facts',
                                     'stale wording, missing evidence, unconfirmed entry'),
    'review-and-composition': ('saved snapshot and current inputs, rules and evaluation date',
                               'confirmation binds the snapshot and comparison identifies its change',
                               'stale confirmation, legacy basis, withdrawn result, stopped work'),
}


# Separate tests cover operations whose input, side effects or available doors
# differ from the shared driver. "partial" records where those tests stop.
# Every contract route must have an explicit disposition.
ROUTE_CHECKS = {
    'GET /api/genome-updates': ('dedicated', 'registered_route_outcomes', 'CLI and Web retain the saved ClinVar release, and report missing history.'),
    'GET /api/version': ('dedicated', 'an_update_says_what_it_asks_of_the_data_until_a_person_has_read_it', 'Stored version and pending requirements.'),
    'GET /api/version/check': ('boundary', 'an_update_says_what_it_asks_of_the_data_until_a_person_has_read_it', 'Offline refusal and controlled registry replies. Live registry excluded.'),
    'GET /api/recompute/status': ('dedicated', 'a_recompute_runs_what_an_update_asks_and_shows_how_far_it_is', 'Progress and interruption persisted by the worker.'),
    'GET /api/evidence-levels': ('dedicated', 'the_evidence_legend_is_one_text_on_every_surface', 'Same legend on human and assistant surfaces.'),
    'GET /api/markers': ('dedicated', 'registered_route_outcomes', 'Exact catalogue keys through CLI and Web.'),
    'GET /api/brief-review': ('dedicated', 'a_brief_block_due_for_a_review_opens_what_changed', 'Dates, request, refusal, CLI and web control.'),
    'GET /api/panel': ('dedicated', 'a_clinician_can_read_the_panel_itself_with_its_studies', 'Evidence sources, display, listing and refusal.'),
    'GET /api/assistant': ('dedicated', 'registered_route_outcomes', 'Read-only status through CLI and Web, with local engine independence.'),
    'GET /api/patients': ('dedicated', 'a_switch_never_answers_with_the_previous_person', 'Actual two-profile HTTP switching and listing.'),
    'GET /api/targets': ('dedicated', 'a_target_the_clinician_set_stands_beside_the_corridor', 'Recorded clinician targets remain distinct from ranges.'),
    'POST /api/labs': ('dedicated', 'every_door_of_the_local_server_answers', 'Dictated point reaches the profile file.'),
    'POST /api/targets': ('dedicated', 'a_target_the_clinician_set_stands_beside_the_corridor', 'Explicit target save and refusal.'),
    'POST /api/version/seen': ('dedicated', 'an_update_says_what_it_asks_of_the_data_until_a_person_has_read_it', 'Pending releases cleared only by acknowledgement.'),
    'POST /api/update': ('boundary', 'an_update_reaches_a_person_inside_a_session', 'Consent and in-session request. No live package install in an offline test.'),
    'POST /api/recompute': ('dedicated', 'pgs_recalculation_is_installed_and_atomic', 'Confirmed installed operation with controlled scorer and atomic refusal.'),
    'POST /api/recompute/stop': ('dedicated', 'a_recompute_runs_what_an_update_asks_and_shows_how_far_it_is', 'Cooperative stop between work items.'),
    'POST /api/targets/remove': ('dedicated', 'a_target_the_clinician_set_stands_beside_the_corridor', 'Removing target preserves laboratory intervals.'),
    'POST /api/goal': ('dedicated', 'a_goal_names_where_it_came_from', 'Accepted proposal retains origin.'),
    'POST /api/medications': ('dedicated', 'every_door_of_the_local_server_answers', 'Prescription and status are persisted.'),
    'POST /api/medications/remove': ('dedicated', 'every_door_of_the_local_server_answers', 'Add and remove one recorded prescription.'),
    'POST /api/metrics': ('dedicated', 'every_door_of_the_local_server_answers', 'Dated metric point reaches the profile file.'),
    'POST /api/pick-folder': ('boundary', 'source_folders_have_a_manual_and_windows_path', 'Path handling, native dialog contract and cancellation. Native GUI excluded.'),
    'POST /api/choose-genome': ('dedicated', 'a_new_pgs_client_gets_a_genome_population', 'Controlled genome attachment and population exposed in CLI/Web.'),
    'POST /api/brief-reviewed': ('dedicated', 'registered_route_outcomes', 'Unknown block preserves bytes and confirmed review updates the date without changing wording.'),
    'POST /api/wearable-primary': ('dedicated', 'registered_route_outcomes', 'Selected device preference reaches the profile.'),
    'POST /api/ingest-wearable': ('dedicated', 'registered_route_outcomes', 'Garmin data persisted, mismatched device refused without writes.'),
    'POST /api/ingest-garmin': ('dedicated', 'registered_route_outcomes', 'Compatibility endpoint rebuilds identical readings and events.'),
    'POST /api/ingest-studies': ('dedicated', 'registered_route_outcomes', 'Controlled PDF extraction, stale confirmation refusal, confirmed save and deduplication.'),
    'POST /api/ingest-labs': ('dedicated', 'registered_route_outcomes', 'Table import and deduplication, stored value and cross-interface result.'),
    'POST /api/assistant/context': ('dedicated', 'every_door_of_the_local_server_answers', 'Writes reviewable local context with restrictive permissions.'),
    'POST /api/use': ('dedicated', 'a_switch_never_answers_with_the_previous_person', 'New profile cannot return previous profile data.'),
    'POST /api/export': ('dedicated', 'container_lifecycle', 'Explicit export and archive verification in a temporary container.'),
    'POST /api/erase': ('dedicated', 'container_lifecycle', 'Confirmation and selected container isolation.'),
}

def path_for(producer: str) -> str:
    return 'src/scholion/' + producer


def test_path(stem: str) -> str:
    return 'tests/test_' + stem + '.py'


def report(root: Path, parity: dict, plugins: dict, families=FAMILIES) -> dict:
    """Fail for missing evidence references or an unclassified product route."""
    errors = []
    entries = {}
    commands = set()
    for family in families:
        if family.key in entries:
            errors.append('Duplicate family: ' + family.key)
        if not family.producers or not family.tests or not family.commands:
            errors.append('Family needs producers, semantic tests and interface scenarios: ' + family.key)
        if set(family.narrow) - set(family.producers):
            errors.append('Narrow input is not a producer: ' + family.key)
        paths = [path_for(p) for p in family.producers]
        tests = [test_path(p) for p in family.tests]
        for path in paths + tests:
            if not (root / path).is_file():
                errors.append('Missing registered file: ' + path)
        try:
            scenarios, write = select(family.commands, parity, plugins) if family.commands else ([], False)
        except ValueError as exc:
            errors.append(str(exc))
            scenarios, write = [], False
        commands.update(family.commands)
        entries[family.key] = {
            'owner': paths[0] if paths else None,
            'producers': paths, 'tests': tests, 'commands': list(family.commands),
            'witness': dict(zip(('input', 'invariant', 'states'), WITNESSES.get(family.key, ()))),
            'routes': sorted(route for route, command in parity.items() if command in family.commands),
            'narrow': [path_for(p) for p in family.narrow],
            'scenarios': [s.name for s in scenarios] + (['focus-log'] if write else [])
            + (['insight-review-save'] if 'insight-snapshot' in family.commands else []),
        }
    mapped_routes = {case.route for case in READS} | {'POST /api/focus/log', 'POST /api/insight-snapshot'}
    unregistered = ({case.command[0] for case in READS} | {'focus-log'}) - commands
    errors.extend('Interface scenario has no family: ' + command for command in sorted(unregistered))
    routes = {route: {'kind': 'shared', 'test': 'src/tools/check_interfaces.py'} for route in mapped_routes}
    for route, (kind, test, scope) in ROUTE_CHECKS.items():
        path = test_path(test)
        if route in routes or route not in parity or not (root / path).is_file():
            errors.append('Invalid dedicated route registration: ' + route)
        routes[route] = {'kind': kind, 'test': path, 'scope': scope}
    unclassified = sorted(set(parity) - routes.keys())
    errors.extend('Route needs coverage disposition: ' + route for route in unclassified)
    return {'schema': 2, 'ok': not errors, 'errors': errors, 'families': entries,
            'routes': dict(sorted(routes.items())), 'unclassified_routes': unclassified,
            'partial_routes': sorted(route for route, row in routes.items() if row['kind'] == 'partial'),
            'semantic_test_modules': sorted({test.replace('/', '.')[:-3]
                                             for row in entries.values() for test in row['tests']}
                                            | {test_path(test).replace('/', '.')[:-3]
                                               for _, test, _ in ROUTE_CHECKS.values()}),
            'release_acceptance': False}


def main() -> int:
    sys.path.insert(0, str(ROOT / 'src'))
    from scholion import contract
    result = report(ROOT, contract.PARITY, contract.PLUGIN)
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
