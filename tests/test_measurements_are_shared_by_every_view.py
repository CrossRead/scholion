"""Every consumer sees the same observations, source and current measurement."""
from datetime import date, timedelta
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import core, engine
from scholion.measurements import history, bmi_history
from scholion.engine.goals import _goal_resolve, _goal_lv, _phenotype_rows
from scholion.engine.insight_events import _annual_events
from scholion.period_summary import period_summary


class SharedMeasurements(TestCase):
    def setUp(self):
        self.today = date.today()
        self.month = self.today.strftime('%Y-%m')
        self.previous = (self.today-timedelta(days=40)).strftime('%Y-%m')
        self.recorded = [{'date': (self.today-timedelta(days=d)).isoformat(), 'value': v}
                         for d, v in [(80, 100), (60, 99), (20, 97), (0, 96)]]
        self.data = {'profile': {'height_cm': '200'}, 'metrics': {
            'weight': {'name': 'Weight', 'unit': 'kg', 'series': self.recorded}}}
        self.wear = {'sources': {'garmin': {'metrics': {
            'Weight': {self.previous: 101, self.month: 100},
            'BMI': {self.previous: 29, self.month: 30}}}}}
        for name, value in [('metrics_json', self.data), ('wearable_trends', self.wear), ('health_goals', {})]:
            patch = mock.patch.object(core, name, return_value=value)
            patch.start(); self.addCleanup(patch.stop)

    def test_weight_history_and_latest_are_identical_everywhere(self):
        expected = history('weight')
        metric = next(r for r in engine.metrics_summary()['metrics'] if r['key'] == 'weight')
        life = next(r for r in engine.lifestyle()['metrics'] if r['key'] == 'Weight')
        goal = _phenotype_rows([{'label': 'Weight', 'source': 'wear:Weight'}])[0]['components'][0]
        for row in (metric, life, goal):
            self.assertEqual(row['series'], expected['series'])
            self.assertEqual(row['value'], 96)
            self.assertEqual(row['date'], self.today.isoformat())
            self.assertEqual(row['current_observation']['measurement_source'], 'recorded')
        self.assertEqual(_goal_resolve('wear:Weight')[0], expected['series'])
        self.assertEqual(_goal_resolve('metric:weight')[0], expected['series'])
        self.assertEqual(_goal_lv('wear:Weight')['points'], expected['series'])
        self.assertEqual(engine._brief_life('Weight')['value'], 96)
        self.assertEqual(len(expected['series']), 6)

    def test_russian_step_units_join_the_device_in_both_languages(self):
        from scholion import i18n
        self.addCleanup(i18n.set_lang, i18n.lang())
        self.data['metrics'] = {'steps': {'unit': 'шаг/день', 'series': [{'date': self.recorded[0]['date'], 'value': 6000}]}}
        self.wear['sources']['garmin']['metrics'] = {'StepsDaily': {self.month: 8300}}
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = history('steps')
            self.assertEqual(result['latest']['value'], 8300)
            self.assertEqual(len(result['series']), 2)

    def test_bmi_stored_and_goal_rows_do_not_duplicate_the_same_quantity(self):
        self.data['metrics']['bmi'] = {'name': 'BMI', 'unit': 'kg/m²', 'series': [{'date': self.today.isoformat(), 'value': 99}]}
        rows = _phenotype_rows([{'label': 'BMI', 'source': 'wear:BMI'}])
        bmi = [c for r in rows for c in r['components'] if c['ref'] in ('wear:BMI', 'metric:bmi')]
        self.assertEqual(len(bmi), 1)
        self.assertEqual(bmi[0]['value'], 24)
        self.assertEqual(bmi[0]['unit'], 'kg/m²')

    def test_month_only_manual_reading_is_not_a_monthly_mean(self):
        self.data['metrics']['weight']['series'] = [{'date': self.month, 'value': 96}]
        point = history('weight')['latest']
        self.assertEqual(point['aggregation'], 'observation')

    def test_bmi_is_derived_from_every_weight_point_with_provenance(self):
        expected = bmi_history()
        metric = engine.metrics_summary()['bmi']
        life = next(r for r in engine.lifestyle()['metrics'] if r['key'] == 'BMI')
        goal = _phenotype_rows([{'label': 'BMI', 'source': 'wear:BMI'}])[0]['components'][0]
        for row in (metric, life, goal):
            self.assertEqual(row['value'], 24)
            self.assertEqual(row['series'], expected['series'])
        for weight, bmi in zip(history('weight')['series'], expected['series']):
            self.assertEqual(bmi['value'], round(weight['value']/4, 1))
            self.assertEqual(bmi['record'], weight['record'])
            self.assertEqual(bmi['measurement_source'], weight['measurement_source'])
        self.assertNotIn('device_history', goal)

    def test_newer_month_and_same_month_tie_use_one_rule(self):
        self.data['metrics']['weight']['series'] = [self.recorded[0]]
        expected = history('weight')['latest']
        self.assertEqual(expected['measurement_source'], 'garmin')
        self.assertEqual(expected['value'], 100)
        for result in (engine.metrics_summary(), engine.lifestyle()):
            row = next(r for r in result['metrics'] if r['key'] in ('weight', 'Weight'))
            self.assertEqual((row['value'], row['date']), (expected['value'], expected['date']))

    def test_other_catalogue_mappings_share_manual_and_imported_readings(self):
        for name, spec in core.wearable_metrics()['metrics'].items():
            key = spec.get('person_metric')
            if not key:
                continue
            self.data['metrics'] = {key: {'name': key, 'unit': spec['unit'], 'series': [{'date': self.today.isoformat(), 'value': 10}]}}
            self.wear['sources']['garmin']['metrics'] = {name: {self.month: 20}}
            metric = next(r for r in engine.metrics_summary()['metrics'] if r['key'] == key)
            life = next(r for r in engine.lifestyle()['metrics'] if r['key'] == name)
            goal = _phenotype_rows([{'label': name, 'source': 'wear:'+name}])[0]['components'][0]
            for row in (metric, life, goal):
                self.assertEqual(row['value'], 10, name)
                self.assertEqual(row['series'], history(key)['series'], name)

    def test_device_only_profile_does_not_need_manual_placeholder(self):
        self.data['metrics'] = {}
        self.assertEqual(engine.metrics_summary()['bmi']['value'], 25)
        weight = next(r for r in engine.metrics_summary()['metrics'] if r['key'] == 'weight')
        self.assertEqual(weight['value'], 100)
        from scholion import limits, i18n
        self.assertNotIn(i18n.t('limits.no_weight_what'), str(limits._profile_limits()))

    def test_explicit_device_request_stays_explicit(self):
        points, src, why = _goal_resolve('wear:garmin:Weight')
        self.assertEqual((points[-1]['value'], src, why), (100, 'garmin', None))
        self.assertEqual(len(points), 2)

    def test_monthly_means_are_not_spliced_into_a_dated_trend(self):
        rows = _phenotype_rows([{'label': 'BMI', 'source': 'wear:BMI'}])
        selected = period_summary(rows, 90)[0]['components'][0]['period']
        self.assertEqual(len(selected['series']), 6)
        self.assertEqual(len(selected['comparison_series']), 4)
        self.assertEqual(selected['delta'], -1)
        self.assertEqual(selected['comparison_source'], 'recorded')
        events = [e for e in _annual_events(rows, {}, 90) if e["key"].startswith("wear:BMI")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['detail']['direction'], 'down')
        self.assertTrue(all(f['record'] == 'metrics.json' for f in events[0]['facts']))
        self.assertEqual(_annual_events(rows, {}, 365), [])

    def test_future_or_invalid_values_do_not_replace_the_current_measurement(self):
        self.data['metrics']['weight']['series'] += [
            {'date': '2099-01-01', 'value': 200}, {'date': self.today.isoformat(), 'value': float('nan')},
            {'date': 'invalid', 'value': 200}, {'date': self.today.isoformat(), 'value': True}]
        self.assertEqual(history('weight')['latest']['value'], 96)
        self.assertEqual(len(history('weight')['series']), 6)

    def test_unselected_device_conflict_is_not_a_current_value(self):
        self.data['metrics'] = {}
        self.wear['sources']['whoop'] = {'metrics': {'Weight': {self.month: 88}}}
        self.assertIsNone(history('weight')['latest'])
        self.assertEqual(len(history('weight')['series']), 3)
        self.assertIsNone(next(r for r in engine.metrics_summary()['metrics'] if r['key'] == 'weight')['value'])
        self.data['profile']['wearable_primary'] = 'whoop'
        self.assertEqual(history('weight')['latest']['value'], 88)
        self.assertEqual(_phenotype_rows([{'source': 'wear:Weight'}])[0]['components'][0]['value'], 88)
