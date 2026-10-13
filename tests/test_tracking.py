import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gen_pages import recent_events, kst_date
from check_collection_audit import audit_summary, collection_notice, main

class TrackingTests(unittest.TestCase):
    def test_recent_dates(self):
        dates = ['2026-09-29', '2026-09-30', '2026-10-12', '2026-10-13', '2026-10-14', '2026-12-08']
        items = [{'id':'x', 'events':[{'date': d} for d in dates]}]
        self.assertEqual([e['date'] for e, _ in recent_events(items, dt.date(2026,10,13))], ['2026-10-13','2026-10-12','2026-09-30'])
    def test_kst_boundary(self):
        self.assertEqual(kst_date(dt.datetime(2026,10,12,14,59,tzinfo=dt.timezone.utc)), dt.date(2026,10,12))
        self.assertEqual(kst_date(dt.datetime(2026,10,12,15,0,tzinfo=dt.timezone.utc)), dt.date(2026,10,13))
        with self.assertRaises(ValueError):kst_date(dt.datetime(2026,10,12))
    def test_undercoverage_and_strict_gate(self):
        raw = {'run_date':'2026-10-13','audit':{'searches_R_side':3,'searches_D_side':1,'searches_topic':4,'blocked_sites':['courtlistener.com'],'notes':'원문 미확인'}}
        result = audit_summary(raw)
        self.assertEqual(result['status'], '미완료')
        self.assertEqual(len(result['problems']),2)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'2026-10-13.json';path.write_text(json.dumps(raw))
            self.assertEqual(main(['--strict',str(path)]),1)
            notice=collection_notice(Path(folder))
            for value in ['미완료','민주 측 1/3회','주제 4/5회','courtlistener.com','원문 미확인']:self.assertIn(value,notice)
    def test_last_rerun_not_sum_or_best(self):
        passed={'searches_R_side':3,'searches_D_side':3,'searches_topic':5}
        raw={'audit':passed,'audit_runs':[passed,{'searches_R_side':1,'searches_D_side':2,'searches_topic':3}]}
        self.assertEqual(audit_summary(raw)['status'],'미완료')
        raw['audit_runs'].append(passed)
        self.assertEqual(audit_summary(raw)['status'],'최소 검색 기준 충족')
    def test_invalid_missing_and_blocked(self):
        for value in [None,True,'3',-1]:
            self.assertTrue(audit_summary({'audit':{'searches_R_side':value}})['problems'])
        raw={'audit':{'searches_R_side':3,'searches_D_side':3,'searches_topic':5,'blocked_sites':['x'],'scotus':{'blocked':['x']}}}
        result=audit_summary(raw)
        self.assertEqual(result['status'],'접근 제한 있음');self.assertEqual(result['blocked'],['x'])
        raw['audit']['followups_due']=3;raw['audit']['followups_checked']=1
        self.assertEqual(audit_summary(raw)['status'],'미완료')

if __name__=='__main__':unittest.main()
