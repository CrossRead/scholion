"""Printed CGM facts, chart approximations and laboratory values stay distinct."""
from __future__ import annotations

import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support
from scholion import cgm, cgm_pdf, core, ingest_studies, store


def report(sha='a', path='/synthetic/report.pdf'):
    return {'format':cgm_pdf.VERSION,'sensor_identity':'b'*64,
            'period':{'start':'2026-01-10','end':'2026-01-10'},
            'source':{'sha256':sha*64,'path':path,'pages':1},
            'summary':{'mean':{'value':5.5,'unit':'mmol/L','kind':'printed_statistic','source_page':1}},
            'daily':[], 'chart_segments':[{'date':'2026-01-10','segments':[[[0,5],[600,5],[630,7],[660,5],[1440,5]]]}],
            'events':[{'date':'2026-01-10','local_time_as_printed':'10:00','type':'meal',
                       'label_as_printed':'Synthetic meal','kind':'user_event','source_page':1}],
            'timezone':None,'quality':{'exact_sensor_series':False}}


class TestChartResponses(unittest.TestCase):
    def test_sensor_context_requires_a_dated_lab_overlap_and_never_equates_methods(self):
        r=report();markers={'glucose':{'key':'glucose','date':'2026-01-10','value':6.1}}
        context=cgm.laboratory_context(r,markers)
        self.assertEqual(context['method'],'printed_sensor_summary')
        self.assertEqual(context['value'],5.5)
        self.assertEqual(context['matched_laboratory_keys'],['glucose'])
        self.assertEqual(context['source_record']['source_sha256'],'a'*64)
        self.assertFalse(context['causation_established'])
        self.assertFalse(context['individual_variant_effect_established'])
        markers['glucose']['date']='2025-12-01'
        self.assertIsNone(cgm.laboratory_context(r,markers))
        self.assertIsNone(cgm.laboratory_context(None,markers))

    def test_cgm_is_rendered_without_wearable_metrics_or_a_second_series(self):
        from scholion import engine
        from scholion.format_views import lifestyle_report
        r=report();records={};cgm.merge(records,r,'sensor.pdf')
        with patch.object(core,'studies',return_value={'studies':list(records.values())}), \
             patch.object(core,'wearable_trends',return_value={}),patch.object(core,'metrics_json',return_value={}):
            result=engine.lifestyle();text=lifestyle_report(result)
            self.assertTrue(result['cgm']['available']);self.assertIn('/synthetic/report.pdf',text)
            missing=engine.lifestyle('f'*64)
            self.assertFalse(missing['cgm']['available'])
            self.assertIn('requested',lifestyle_report(missing).lower())

    def test_known_triangle_has_separate_baseline_peak_and_positive_area(self):
        r=report();result=cgm.responses(r)[0]
        self.assertEqual(result['status'],'estimated')
        self.assertEqual(result['baseline_mean_estimate'],5)
        self.assertEqual(result['peak_estimate'],7)
        self.assertEqual(result['peak_delta_estimate'],2)
        self.assertEqual(result['time_to_peak_minutes_estimate'],30)
        self.assertEqual(result['area_above_baseline_estimate'],60)
        self.assertFalse(result['causation_established'])
        self.assertEqual(result['kind'],'approximate_chart_response')
        self.assertEqual(r['summary']['mean']['kind'],'printed_statistic')

    def test_gap_is_not_filled_and_overlapping_activity_remains_a_confounder(self):
        r=report();r['chart_segments'][0]['segments']=[[[0,5],[610,5]],[[611,6],[1440,5]]]
        r['events'].append({'date':'2026-01-10','local_time_as_printed':'10:15','type':'activity'})
        result=cgm.responses(r)[0]
        self.assertEqual(result['status'],'incomplete_chart_window')
        self.assertNotIn('peak_estimate',result)
        self.assertEqual(result['confounders'],['activity'])
        from scholion import format_cgm
        r['responses']=[result];r['night_alignment']={'message':'explicit interval unavailable'}
        text='\n'.join(format_cgm.lines({'available':True,'label':'CGM','notice':'sensor source','current':r}))
        self.assertIn('full comparison window',text)
        self.assertIn('Activity',text)

    def test_only_touching_supported_midnight_segments_join(self):
        r=report();r['chart_segments']=[{'date':'2026-01-10','segments':[[[0,5],[1440,5]]]},
                                     {'date':'2026-01-11','segments':[[[0,5],[1440,5]]]}]
        r['events'][0].update(date='2026-01-11',local_time_as_printed='00:15')
        self.assertEqual(cgm.responses(r)[0]['status'],'estimated')
        r['chart_segments'][0]['segments'][0][-1][0]=1438
        self.assertEqual(cgm.responses(r)[0]['status'],'incomplete_chart_window')

    def test_positive_area_handles_baseline_crossing_without_negative_cancellation(self):
        r=report();r['chart_segments'][0]['segments']=[[[0,5],[600,5],[630,7],[690,3],[720,5],[1440,5]]]
        # Above-baseline triangles: 30*2/2 plus 30*2/2; negative area is not subtracted.
        self.assertEqual(cgm.responses(r)[0]['area_above_baseline_estimate'],60)

    def test_sleep_requires_offsets_source_and_explicit_report_timezone(self):
        intervals={'metrics':{'sleep':{'series':[{'started_at':'2026-01-10T01:00:00Z',
                        'ended_at':'2026-01-10T03:00:00Z','source':'synthetic-wearable'}]}}}
        with patch.object(core,'metrics_json',return_value=intervals):
            self.assertEqual(cgm._night_alignment(report())['reason'],'timezone_unknown')
            r=report();r['timezone']='UTC';actual=cgm._night_alignment(r)
            self.assertEqual(actual['status'],'estimated')
            self.assertEqual(actual['intervals'][0]['minimum_estimate'],5)
            self.assertFalse(actual['daily_extrema_used_as_night'])
        with patch.object(core,'metrics_json',return_value={'metrics':{'sleep':{'series':[{'date':'2026-01-10','value':8}]}}}):
            self.assertEqual(cgm._night_alignment(r)['reason'],'sleep_intervals_not_recorded')

    def test_dst_interval_is_not_aligned_to_a_wall_clock_chart(self):
        r=report();r['timezone']='Europe/Berlin'
        m={'metrics':{'sleep':{'series':[{'started_at':'2026-03-29T00:00:00Z',
                                        'ended_at':'2026-03-29T03:00:00Z','source':'wearable'}]}}}
        with patch.object(core,'metrics_json',return_value=m):
            self.assertEqual(cgm._night_alignment(r)['status'],'not_established')


class TestVectorReading(unittest.TestCase):
    def test_bezier_is_sampled_from_its_curve_with_bounded_vertical_error(self):
        controls=((0,5),(30,12),(60,1),(90,5))
        points=[controls[0]]+cgm_pdf._cubic_points(*controls,.01)
        self.assertGreater(len(points),5)
        for n in range(901):
            t=n/900;u=1-t;x=90*t
            y=u**3*5+3*u*u*t*12+3*u*t*t*1+t**3*5
            window=cgm._window([points],x,x+.00001) if x<90 else None
            if window:self.assertAlmostEqual(window[0][1],y,delta=.011)
        simplified=cgm_pdf._simplify(points,.15)
        self.assertLess(len(simplified),len(points))
        self.assertEqual(simplified[0],controls[0]);self.assertEqual(simplified[-1],controls[-1])

    @staticmethod
    def words(end=date(2026,1,11)):
        start=date(2026,1,10);days=(end-start).days+1
        def word(text,x,y,width=12):return {'text':text,'x0':x,'x1':x+width,'top':y,'bottom':y+8}
        words=[word('Позиция',0,0)]+[word((start+timedelta(days=i)).strftime('%m/%d'),200+i*40,0) for i in range(days)]
        for j,(_,fragment,_) in enumerate(cgm_pdf.METRICS):
            words.append(word(fragment,0,20+j*20,160))
            words.extend(word(str(10+i+j),200+i*40,20+j*20) for i in range(days))
        return words

    def test_daily_columns_do_not_shift_missing_cells_or_invent_a_mean(self):
        words=self.words();words=[w for w in words if not(w['x0']==240 and w['top']==40)]
        rows=cgm_pdf.daily_table(words,date(2026,1,10),date(2026,1,11),2)
        self.assertEqual(rows[0]['statistics']['reported_mean_ambiguous']['value'],11)
        self.assertIsNone(rows[1]['statistics']['reported_mean_ambiguous']['value'])
        self.assertEqual(rows[1]['statistics']['sd']['value'],13)
        self.assertEqual(rows[0]['statistics']['reported_mean_ambiguous']['definition_status'],'ambiguous')
        self.assertEqual(rows[0]['statistics']['fraction_reported_3_9_to_10']['kind'],'printed_statistic')
        with self.assertRaisesRegex(ValueError,'columns'):
            cgm_pdf.daily_table(words,date(2026,2,10),date(2026,2,11),2)

    def test_unsupported_or_duplicate_statistic_row_is_refused(self):
        words=self.words()
        with self.assertRaisesRegex(ValueError,'incomplete'):
            cgm_pdf.daily_table([w for w in words if w['top']!=40],date(2026,1,10),date(2026,1,11),2)
        words.append({'text':'25','x0':201,'x1':213,'top':20,'bottom':28})
        with self.assertRaisesRegex(ValueError,'multiple values'):
            cgm_pdf.daily_table(words,date(2026,1,10),date(2026,1,11),2)


class TestVersionedImports(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.profile=self.root/'profile';self.profile.mkdir()
        self.forms=self.root/'forms';self.forms.mkdir();self.source=self.forms/'sensor.pdf';self.source.write_bytes(b'synthetic-pdf')
        restore=support.pin_profile(self.profile);self.addCleanup(restore)
        restore_cache=support.pin_cache(self.root/'cache');self.addCleanup(restore_cache)
        core.reset_cache();self.addCleanup(core.reset_cache)
        self.data=report(hashlib.sha256(self.source.read_bytes()).hexdigest()[0],str(self.source))
        self.data['source']['sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.path=self.profile/'studies.json';self.path.write_text('{"studies": [], "_meta":{"keep":"note"}}', encoding="utf-8")
        for obj,name,value in ((ingest_studies,'_ensure_extractor',True),
                               (ingest_studies,'_read_pdf','supported synthetic report'),
                               (cgm_pdf,'recognizes',True), (cgm_pdf,'extract',self.data)):
            mock=patch.object(obj,name,return_value=value);mock.start();self.addCleanup(mock.stop)

    def test_preview_writes_nothing_and_changed_input_cannot_use_old_confirmation(self):
        before=self.path.read_bytes();r=ingest_studies.ingest(str(self.forms),dry_run=True)
        self.assertEqual(r['would_add'],1);self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(core.ingest_manifest_path('studies').exists())
        self.source.write_bytes(b'changed')
        denied=ingest_studies.ingest(str(self.forms),approval=r['approval_token'])
        self.assertFalse(denied['ok']);self.assertEqual(self.path.read_bytes(),before)

    def test_confirmed_import_duplicate_revision_move_and_historical_selection(self):
        r=ingest_studies.ingest(str(self.forms),dry_run=True)
        result=ingest_studies.ingest(str(self.forms),approval=r['approval_token'])
        self.assertEqual(result['added'],1)
        before=self.path.read_bytes()
        self.assertEqual(ingest_studies.ingest(str(self.forms),force=True)['skipped_unchanged'],1)
        self.assertEqual(before,self.path.read_bytes())
        actual=json.loads(before);by_id={s['id']:s for s in actual['studies']}
        next_report=report('c');sid,status=cgm.merge(by_id,next_report,'new.pdf')
        self.assertEqual(status,'updated');self.assertEqual(len(by_id[sid]['cgm']['versions']),2)
        moved=copy.deepcopy(self.data);moved['source']['path']='/moved/report.pdf'
        self.assertEqual(cgm.merge(by_id,moved,'moved.pdf')[1],'updated')
        self.assertEqual(by_id[sid]['cgm']['current_version'],'c'*64)
        self.assertEqual(by_id[sid]['cgm']['versions'][0]['source']['aliases'],['/moved/report.pdf'])
        with patch.object(core,'studies',return_value={'studies':list(by_id.values())}),patch.object(core,'metrics_json',return_value={}):
            old=cgm.summary(self.data['source']['sha256']);self.assertTrue(old['available'])
            self.assertEqual(old['current']['source']['sha256'],self.data['source']['sha256'])
            self.assertFalse(cgm.summary('f'*64)['available'])
            self.assertEqual(cgm.summary()['current']['source']['sha256'],'c'*64)
        self.assertFalse((self.profile/'labs.json').exists())

    def test_source_change_during_confirmed_parse_preserves_the_saved_report(self):
        before=self.path.read_bytes()
        token=ingest_studies.ingest(str(self.forms),dry_run=True)['approval_token']
        def changed(*args,**kwargs):
            self.source.write_bytes(b'changed while reader was running')
            return self.data
        with patch.object(cgm_pdf,'extract',side_effect=changed):
            result=ingest_studies.ingest(str(self.forms),approval=token)
        self.assertFalse(result['ok']);self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(core.ingest_manifest_path('studies').exists())

    def test_unreadable_confirmation_witness_never_replaces_the_saved_report(self):
        before=self.path.read_bytes()
        original=ingest_studies._approval_token
        token=ingest_studies.ingest(str(self.forms),dry_run=True)['approval_token']
        with patch.object(ingest_studies,'_approval_token',side_effect=PermissionError('synthetic source denied')):
            self.assertFalse(ingest_studies.ingest(str(self.forms),approval=token)['ok'])
        with patch.object(ingest_studies,'_approval_token',side_effect=[original(self.forms,False),PermissionError('source disappeared after reading')]):
            self.assertFalse(ingest_studies.ingest(str(self.forms),approval=token)['ok'])
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(core.ingest_manifest_path('studies').exists())

    def test_unknown_sensors_with_equal_periods_are_not_merged(self):
        a=report('a');b=report('c');a['sensor_identity']=b['sensor_identity']='unknown';records={}
        x=cgm.merge(records,a,'a.pdf')[0];y=cgm.merge(records,b,'b.pdf')[0]
        self.assertNotEqual(x,y);self.assertEqual(len(records),2)

    def test_parse_failure_and_stop_leave_old_profile_bytes_intact(self):
        before=self.path.read_bytes()
        with patch.object(cgm_pdf,'extract',side_effect=ValueError('unsupported geometry')):
            r=ingest_studies.ingest(str(self.forms),force=True)
        self.assertEqual(len(r['not_ingested']),1);self.assertEqual(self.path.read_bytes(),before)
        def stop(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):ingest_studies.ingest(str(self.forms),force=True,progress=stop)
        self.assertEqual(self.path.read_bytes(),before)

    def test_same_timestamp_changed_bytes_are_not_skipped(self):
        ingest_studies.ingest(str(self.forms));mtime=self.source.stat().st_mtime
        self.source.write_bytes(b'changed-source')
        import os
        os.utime(self.source,(mtime,mtime))
        newer=copy.deepcopy(self.data);newer['source']['sha256']='e'*64
        with patch.object(cgm_pdf,'extract',return_value=newer):
            self.assertEqual(ingest_studies.ingest(str(self.forms))['updated'],1)

    def test_invalid_timezone_does_not_write(self):
        path=self.profile/'metrics.json';path.write_text('{"profile":{},"metrics":{}}', encoding="utf-8");before=path.read_bytes()
        with patch.object(store,'_path',return_value=path):
            self.assertFalse(store.update_metric_profile({'cgm_timezones':{'not-a-sha':'Mars/Olympus'}})['ok'])
        self.assertEqual(path.read_bytes(),before)

    def test_mcp_and_ouroboros_studies_path_requires_a_reviewed_token(self):
        import subprocess
        from scholion import mcp_server, ouroboros_tools as ot, ingest_labs
        tools={entry.name:entry for entry in ot.get_tools()};ot.unpin_session();self.addCleanup(ot.unpin_session)
        captured=[]
        def worker(command,**kwargs):
            captured.append((command,kwargs))
            return subprocess.CompletedProcess(command,0,json.dumps({'ok':True,'dry_run':True,'approval_token':'review-token'}),'')
        # This is a worker/consent test, independent of the optional PDF reader
        # in the stdlib-only Python 3.10 test interpreter. The installed-wheel
        # acceptance exercises the actual declared PDF dependency separately.
        with patch.object(ingest_labs, '_ensure_extractor', return_value='pdfplumber'), \
                patch('subprocess.run',side_effect=worker):
            text=tools['sch_ingest_labs'].handler(None,folder=str(self.forms),kind='studies')
            remote=mcp_server.call_tool('sch_ingest_labs',{'folder':str(self.forms),'kind':'studies','confirm':'review-token'})
        self.assertEqual(json.JSONDecoder().raw_decode(text)[0]['approval_token'],'review-token')
        self.assertFalse(remote['isError'])
        self.assertIn('ingest-studies',captured[0][0]);self.assertIn('--dry-run',captured[0][0])
        self.assertNotIn('--approve',captured[0][0])
        self.assertEqual(captured[1][0][-2:],['--approve','review-token'])
        self.assertEqual(captured[1][1]['env']['SCHOLION_PROFILE_DIR'],str(self.profile))
        self.assertEqual(captured[0][1]['timeout'],105)

class TestSleepComparisons(unittest.TestCase):
    def test_exact_native_whoop_intervals_keep_zone_and_ignore_naps(self):
        from scholion import wearables
        data=wearables._builder('ingest_whoop.py').build(str(support.ROOT/'tests/fixtures/whoop'),core.wearable_metrics())
        nights=data['nightly_sleep']
        self.assertEqual(nights[0]['started_at'],'2026-01-03T23:41:00+03:00')
        self.assertEqual(nights[0]['ended_at'],'2026-01-04T06:12:00+03:00')
        self.assertTrue(all(n['sleep_kind']=='main_sleep' for n in nights if 'started_at' in n))
        self.assertFalse(any('T14:10' in n.get('started_at','') for n in nights))

    def test_garmin_explicit_gmt_fields_keep_utc_without_inferred_end(self):
        from scholion import wearables
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();folder=root/'DI_CONNECT/DI-Connect-Wellness';folder.mkdir(parents=True)
            row={'calendarDate':'2026-01-10','deepSleepSeconds':3600,'lightSleepSeconds':18000,
                 'sleepStartTimestampGMT':'2026-01-09T23:15:00.000','sleepEndTimestampGMT':'2026-01-10T06:30:00.000'}
            path=folder/'synthetic_sleepData.json';path.write_text(json.dumps([row]),encoding="utf-8")
            result=wearables._builder('ingest_garmin.py').build(str(root))['nightly_sleep'][0]
            self.assertEqual(result['started_at'],'2026-01-09T23:15:00+00:00')
            self.assertEqual(result['ended_at'],'2026-01-10T06:30:00+00:00')
            del row['sleepEndTimestampGMT'];path.write_text(json.dumps([row]),encoding="utf-8")
            result=wearables._builder('ingest_garmin.py').build(str(root))['nightly_sleep'][0]
            self.assertNotIn('ended_at',result)

    def test_activity_fall_below_baseline_is_not_a_return(self):
        r=report();r['events'][0]['type']='activity'
        r['chart_segments'][0]['segments']=[[[0,5],[600,5],[630,4],[1440,4]]]
        response=cgm.responses(r)[0]
        self.assertEqual(response['minimum_estimate'],4)
        self.assertEqual(response['end_delta_estimate'],-1)
        self.assertFalse(response['return_toward_baseline_observed'])

    def test_weighted_sleep_stats_last_recorded_food_and_timed_events(self):
        r=report();r['timezone']='UTC'
        r['events']=[{'date':'2026-01-10','local_time_as_printed':'09:30','type':'meal','label_as_printed':'recorded food'},
                     {'date':'2026-01-10','local_time_as_printed':'10:30','type':'activity','label_as_printed':'recorded activity'}]
        points=[{'started_at':'2026-01-10T10:00:00Z','ended_at':'2026-01-10T11:00:00Z',
                 'source':'synthetic-wearable','sleep_kind':'main_sleep','score':77,'awake_count':2,'deep_min':12}]
        with patch.object(cgm,'_sleep_points',return_value=points):result=cgm._night_alignment(r)
        n=result['intervals'][0]
        self.assertEqual(n['mean_estimate'],6)
        self.assertEqual(n['minimum_estimate'],5)
        self.assertEqual(n['maximum_estimate'],7)
        self.assertEqual(n['sd_estimate'],.6)
        self.assertEqual(n['last_recorded_meal_gap_hours'],.5)
        self.assertEqual(n['events_during_sleep'][0]['minutes_from_sleep_start'],30)
        self.assertEqual(n['score'],77)
        self.assertEqual(n['awake_count'],2)
        self.assertFalse(n['causation_established'])
        self.assertEqual(len(result['associations']),3)
        from scholion import format_cgm,i18n
        previous=i18n.lang();self.addCleanup(i18n.set_lang,previous)
        for language in ('ru','en'):
            i18n.set_lang(language)
            text='\n'.join(format_cgm.sleep_lines(result))
            self.assertIn('77',text);self.assertIn('6',text)
            self.assertNotIn('cgm.sleep_values',text)

    def test_activity_has_own_response_not_only_a_meal_confounder(self):
        r=report();r['events'][0]['type']='activity'
        result=cgm.responses(r)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['event']['type'],'activity')
        self.assertEqual(result[0]['peak_delta_estimate'],2)

    def test_nap_dst_invalid_and_gapped_intervals_remain_explicit(self):
        r=report();r['timezone']='UTC';base={'started_at':'2026-01-10T01:00:00Z','ended_at':'2026-01-10T03:00:00Z','source':'watch'}
        points=[{**base,'sleep_kind':'nap'},{**base,'started_at':'unknown'},
                {**base,'ended_at':'2026-01-10T04:00:00Z'}]
        r['chart_segments'][0]['segments']=[[[0,5],[150,5]],[[151,5],[1440,5]]]
        with patch.object(cgm,'_sleep_points',return_value=points):out=cgm._night_alignment(r)
        self.assertEqual({n['reason'] for n in out['excluded']},{'nap_not_night','interval_or_source_unverified'})
        self.assertEqual(out['intervals'][0]['status'],'incomplete_chart_window')
        self.assertNotIn('mean_estimate',out['intervals'][0])
        from scholion import format_cgm
        text='\n'.join(format_cgm.sleep_lines(out))
        self.assertIn('nap',text.lower())
        self.assertIn('full comparison window',text)
        r['timezone']='Europe/Berlin';r['period']={'start':'2026-03-29','end':'2026-03-29'}
        with patch.object(cgm,'_sleep_points',return_value=[{**base,'started_at':'2026-03-29T00:00:00Z','ended_at':'2026-03-29T03:00:00Z'}]):
            self.assertEqual(cgm._night_alignment(r)['excluded'][0]['reason'],'dst_transition')

    def test_exploratory_comparison_is_separate_per_device_and_sensitivity_is_not_ci(self):
        rows=[{'source':'watch-a','status':'estimated','sleep_kind':'main_sleep','duration_hours':i+1,'mean_estimate':i*2,
               'score':50} for i in range(8)]
        rows += [{'source':'watch-b','status':'estimated','sleep_kind':'main_sleep','duration_hours':8,'mean_estimate':5}]
        rows += [{'source':'watch-a','status':'incomplete_chart_window','sleep_kind':'main_sleep','duration_hours':7}]
        rows += [{'source':'watch-a','status':'estimated','sleep_kind':'recorded_sleep','duration_hours':5,'mean_estimate':20}]
        by={(r['source'],r['x']):r for r in cgm._night_associations(rows)}
        a=by['watch-a','duration_hours']
        self.assertEqual(a['r'],1);self.assertEqual(a['leave_one_out_range'],[1,1])
        self.assertEqual(a['included'],8);self.assertEqual(a['excluded'],2)
        self.assertEqual(by['watch-b','duration_hours']['status'],'descriptive')
        self.assertEqual(by['watch-a','score']['status'],'descriptive')
        self.assertNotIn('confidence_interval',a);self.assertFalse(a['causation_established'])

    def test_existing_native_night_files_are_read_without_rewriting_or_duplicate_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            payload={'_meta':{'source':'whoop'},'nights':[{'date':'2026-01-10','SleepPerformance':88,
                'started_at':'2026-01-10T01:00:00+00:00','ended_at':'2026-01-10T03:00:00+00:00','sleep_kind':'main_sleep'}]}
            path=root/'sleep_nightly.whoop.json';path.write_text(json.dumps(payload),encoding="utf-8");before=path.read_bytes()
            r=report();r['timezone']='UTC'
            with patch.object(core,'profile_dir',return_value=root),patch.object(core,'metrics_json',return_value={}):out=cgm._night_alignment(r)
            self.assertEqual(out['intervals'][0]['score'],88)
            self.assertEqual(out['intervals'][0]['source_record'],'sleep_nightly.whoop.json')
            self.assertEqual(path.read_bytes(),before)
