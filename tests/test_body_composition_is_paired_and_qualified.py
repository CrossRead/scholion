"""Overlapping device estimates are observations, not body compartments or goals."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import body_composition as body, core, wearables
from scholion.engine.lifestyle import lifestyle


def record(day='2026-01-03', **fields):
    return {'metaData': {'calendarDate': day}, 'weight': fields}


class TestTheEventModel(unittest.TestCase):
    def test_overlapping_components_are_valid_and_bone_is_an_estimate(self):
        event = body.garmin_event(record(weight=60000, bodyFat=24.3, bodyWater=54.4,
                                         muscleMass=25100, boneMass=2500))
        for field in event['fields'].values():
            self.assertEqual(field['status'], 'usable', field)
        self.assertEqual(event['fields']['BoneMass']['value'], 2.5)
        self.assertEqual(event['fields']['BoneMass']['measurement_kind'], 'manufacturer_estimate')
        self.assertAlmostEqual(event['derived']['FatMass']['value'], 14.58)
        self.assertAlmostEqual(event['derived']['FatFreeMass']['value'], 45.42)
        self.assertEqual(event['derived']['FatMass']['inputs'], ['Weight', 'BodyFat'])

    def test_missing_fields_are_not_zero_and_cannot_borrow_another_weight(self):
        event = body.garmin_event(record(bodyFat=24.3))
        self.assertNotIn('BoneMass', event['fields'])
        self.assertNotIn('Weight', event['fields'])
        self.assertEqual(event['derived'], {})

    def test_invalid_values_remain_raw_without_becoming_measurements(self):
        for key, value, reason in [('bodyFat', 101, 'percentage_out_of_range'),
                                   ('weight', True, 'not_a_finite_number'),
                                   ('bodyWater', float('inf'), 'not_a_finite_number'),
                                   ('boneMass', 0, 'zero_unverified')]:
            event = body.garmin_event(record(**{key:value}))
            field = next(iter(event['fields'].values()))
            self.assertEqual(field['reason'], reason)
            self.assertIsNone(field['value'])
            self.assertIn('raw_value', field)
            json.dumps(event, allow_nan=False)

    def test_a_mass_greater_than_the_same_event_weight_is_held(self):
        event = body.garmin_event(record(weight=60000, muscleMass=70000))
        self.assertEqual(event['fields']['MuscleMass']['reason'], 'mass_exceeds_paired_weight')
        self.assertEqual(event['fields']['MuscleMass']['raw_value'], 70000)

    def test_units_are_not_guessed(self):
        event = body.garmin_event(record(weight=60, weightUnit='kg', boneMass=3, boneMassUnit='kg'))
        self.assertEqual(event['fields']['Weight']['value'], 60)
        self.assertEqual(event['fields']['BoneMass']['value'], 3)
        bad = body.garmin_event(record(weight=60, weightUnit='unknown'))
        self.assertEqual(bad['fields']['Weight']['reason'], 'unit_unverified')

    def test_epoch_metadata_is_retained_without_guessing_its_time_unit(self):
        event = body.garmin_event(record(weight=60000, timestamp=123456789))
        self.assertEqual(event['date'], '2026-01-03')
        self.assertEqual(event['source_timestamp'], 123456789)


class TestThePackagedReader(unittest.TestCase):
    def test_pairs_are_calculated_before_aggregation_and_import_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wellness = root / 'DI_CONNECT' / 'DI-Connect-Wellness'; wellness.mkdir(parents=True)
            (root/'DI_CONNECT'/'DI-Connect-Aggregator').mkdir()
            records = [record(weight=50000, bodyFat=40),
                       record('2026-01-04', weight=100000, bodyFat=10, boneMass=3000)]
            (wellness/'synthetic_userBioMetrics.json').write_text(json.dumps(records), encoding="utf-8")
            builder = wearables._builder('ingest_garmin.py')
            result = builder.build(str(root))
            events = result['body_composition']['events']
            fat = sum(e['derived']['FatMass']['value'] for e in events)/len(events)
            self.assertEqual(fat, 15)
            self.assertNotEqual(fat, result['metrics']['Weight']['2026-01'] *
                                result['metrics']['BodyFat']['2026-01']/100)
            self.assertEqual(result['metrics']['BoneMass']['2026-01'], 3)
            self.assertEqual(builder.build(str(root)), result)
            block = wearables.migrate(result)['sources']['garmin']
            self.assertEqual(len(body.event_points(block, 'Weight')), 2)
            corrections = [{'device':'garmin','metric':'Weight','month':'2026-01',
                            'action':'replace','value':72,'why':'synthetic source review'}]
            wearables.apply_corrections(block, 'garmin', corrections)
            self.assertEqual(body.event_points(block, 'Weight'), [])
            self.assertEqual(block['metrics']['Weight']['2026-01'], 72)
            self.assertEqual(len(block['body_composition']['events']), 2)


class TestInvalidImportPreservation(unittest.TestCase):
    def test_overlapping_reimports_keep_older_events_without_duplicating_shared_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            export = root / 'export'
            wellness = export / 'DI_CONNECT' / 'DI-Connect-Wellness'
            wellness.mkdir(parents=True)
            (export / 'DI_CONNECT' / 'DI-Connect-Aggregator').mkdir()
            source = wellness / 'synthetic_userBioMetrics.json'
            profile = root / 'profile'
            profile.mkdir()
            early = record('2026-01-03', weight=60000, bodyFat=24)
            shared = record('2026-01-04', weight=61000, bodyFat=25)
            later = record('2026-01-05', weight=62000, bodyFat=26)
            with mock.patch.object(core, 'profile_dir', return_value=profile), \
                    mock.patch('scholion.subject.claim_for_owner', return_value={}):
                source.write_text(json.dumps([early, shared]), encoding='utf-8')
                self.assertTrue(wearables.reingest(str(export))['ok'])
                source.write_text(json.dumps([shared, later]), encoding='utf-8')
                self.assertTrue(wearables.reingest(str(export))['ok'])
                self.assertTrue(wearables.reingest(str(export))['ok'])
            saved = json.loads((profile / 'wearable_trends.json').read_text(encoding='utf-8'))
            events = saved['sources']['garmin']['body_composition']['events']
            self.assertEqual([event['date'] for event in events], ['2026-01-03', '2026-01-04', '2026-01-05'])
            self.assertEqual(len({event['event_id'] for event in events}), 3)
            self.assertEqual([event['fields']['Weight']['value'] for event in events], [60, 61, 62])

    def test_invalid_only_export_is_saved_without_inventing_a_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root / 'export'
            wellness = export / 'DI_CONNECT' / 'DI-Connect-Wellness'
            wellness.mkdir(parents=True)
            (export/'DI_CONNECT'/'DI-Connect-Aggregator').mkdir()
            (wellness/'synthetic_userBioMetrics.json').write_text(json.dumps([record(bodyFat=150)]), encoding="utf-8")
            profile = root/'profile'; profile.mkdir()
            with mock.patch.object(core, 'profile_dir', return_value=profile), \
                    mock.patch('scholion.subject.claim_for_owner', return_value={}):
                result = wearables.reingest(str(export))
            self.assertTrue(result['ok'], result)
            saved = json.loads((profile/'wearable_trends.json').read_text(encoding="utf-8"))
            block = saved['sources']['garmin']
            self.assertFalse(block.get('metrics'))
            self.assertEqual(body.invalid_values(block, 'BodyFat')[0]['raw_value'], 150)


class TestTheSharedInterpretation(unittest.TestCase):
    def row(self, **extra):
        return {'key':'BodyFat','value':24.3,'unit':'%','date':'2026-01',
                'source':'garmin','status':'bad','score':45,'trend_good':True,'improving':True,
                'comparison':{'eligible':False,'distinguishable':None},**extra}

    def test_no_goal_means_no_universal_fat_threshold_or_improvement(self):
        with mock.patch.object(core, 'health_goals', return_value={}):
            row = body.qualify(self.row())
        self.assertEqual(row['value'], 24.3)
        self.assertEqual(row['status'], 'none')
        self.assertIsNone(row['score'])
        self.assertIsNone(row['trend_good'])
        self.assertIsNone(row['improving'])
        self.assertFalse(row['counts_toward_conclusions'])
        self.assertTrue(row['body_quality']['legacy_summary'])

    def test_explicit_applicable_goal_changes_its_label_not_a_health_score(self):
        goal = {'source':'wear:BodyFat','target':22,'dir':'lower','unit':'%',
                'target_confirmed':True,'target_source':'A recorded synthetic plan',
                'applicability':{'status':'held','context':'Synthetic case only'}}
        with mock.patch.object(core, 'health_goals', return_value={'targets':[goal]}):
            row = body.qualify(self.row())
        self.assertEqual(row['status'], 'warn')
        self.assertIn('Above', row['status_text'])
        self.assertIsNone(row['score'])
        self.assertIsNone(row['trend_good'])

    def test_a_change_of_method_cannot_be_called_an_improvement(self):
        goal = {'source':'wear:BodyFat','target':22,'dir':'lower','unit':'%',
                'target_confirmed':True,'target_source':'Synthetic plan',
                'applicability':{'status':'held','context':'Synthetic case'}}
        comparison = {'eligible':True,'distinguishable':True,'delta':-2,
                      'before':{'value':28,'method':'old','device':'scale','algorithm_version':'1','calibration':'a'},
                      'after':{'value':26,'method':'new','device':'scale','algorithm_version':'2','calibration':'b'}}
        with mock.patch.object(core, 'health_goals', return_value={'targets':[goal]}):
            row = body.qualify(self.row(comparison=comparison))
        self.assertIsNone(row['trend_good'])

    def test_a_supported_goal_and_qualified_same_method_change_are_named_as_goal_progress(self):
        goal = {'source':'wear:BodyFat','target':22,'dir':'lower','unit':'%',
                'target_confirmed':True,'target_source':'Synthetic recorded plan',
                'applicability':{'status':'held','context':'Synthetic case'}}
        common = {'method':'BIA','device':'synthetic scale','algorithm_version':'1','calibration':'a'}
        comparison = {'eligible':True,'distinguishable':True,'delta':-2,
                      'before':{**common,'value':28,'date':'2025-12'},
                      'after':{**common,'value':26,'date':'2026-01'}}
        with mock.patch.object(core, 'health_goals', return_value={'targets':[goal]}):
            result = body.qualify(self.row(comparison=comparison))
        self.assertTrue(result['trend_good'])
        self.assertEqual(result['qualified_change_text'], 'Moving toward the recorded goal')
        self.assertIsNone(result['score'])

    def test_invalid_only_records_are_visible_without_numeric_clinical_status(self):
        event = body.garmin_event(record(bodyFat=150))
        data = {'sources':{'garmin':{'metrics':{},'body_composition':{'events':[event]}}}}
        with mock.patch.object(core, 'wearable_trends', return_value=data), \
                mock.patch.object(core, 'health_goals', return_value={}), \
                mock.patch.object(core, 'metrics_json', return_value={}):
            result = lifestyle()
        row = next(m for m in result['metrics'] if m['key']=='BodyFat')
        self.assertIsNone(row['value'])
        self.assertEqual(row['body_invalid_values'][0]['raw_value'], 150)
        self.assertEqual(row['status'], 'none')

    def test_a_valid_event_only_estimate_is_not_lost_without_a_monthly_legacy_row(self):
        event = body.garmin_event(record(weight=60000, boneMass=2500))
        data = {'sources':{'garmin':{'metrics':{},'body_composition':{'events':[event]}}}}
        with mock.patch.object(core, 'wearable_trends', return_value=data), \
                mock.patch.object(core, 'health_goals', return_value={}), \
                mock.patch.object(core, 'metrics_json', return_value={}):
            result = lifestyle()
        row = next(m for m in result['metrics'] if m['key']=='BoneMass')
        self.assertEqual(row['value'], 2.5)
        self.assertEqual(row['measurement_kind'], 'manufacturer_estimate')
        self.assertEqual(row['aggregation'], 'observation')

    def test_synthetic_source_remains_synthetic(self):
        with mock.patch.object(core, 'health_goals', return_value={}):
            row = body.qualify(self.row(), {'_meta':{'synthetic':True}})
        self.assertTrue(row['synthetic'])
        self.assertEqual(row['source_kind'], 'synthetic')
        self.assertIn('Synthetic', row['composition_note'])

    def test_the_engine_uses_the_same_qualification_for_device_rows(self):
        data = {'_meta':{'synthetic':True,'source':'Garmin-shaped synthetic export'},
                'metrics':{'BodyFat':{'2025-12':26,'2026-01':24.3},'MuscleMass':{'2025-12':24,'2026-01':25.1}}}
        with mock.patch.object(core, 'wearable_trends', return_value=data), \
                mock.patch.object(core, 'health_goals', return_value={}), \
                mock.patch.object(core, 'metrics_json', return_value={}):
            result = lifestyle()
        self.assertEqual(result['conclusions'], {'good':[],'watch':[]})
        self.assertIsNone(result['fitness_score'])
        self.assertTrue(all(m['synthetic'] for m in result['metrics']))
        self.assertTrue(all(m['status']=='none' for m in result['metrics']))
        self.assertTrue(result['body_composition']['notice'])
