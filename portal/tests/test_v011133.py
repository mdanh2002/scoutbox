from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from portal.services.discovery_markets import (
    DEFAULT_MARKET_CODES, MARKET_BY_CODE, market_plan, market_workload_schedule,
    multilingual_strength_cap, multilingual_assignments,
)
from portal.services.discovery import _translation_language_for_result
from portal.services.location import resolve_opportunity_location
from portal.services.search import _searchapi_locale, _searchapi_job_rows, _searchapi_apply_link, _searchapi_request


class Release011133GlobalCoverageTests(SimpleTestCase):
    def test_world_catalogue_is_country_complete_enough_for_global_sweeps(self):
        self.assertGreaterEqual(len(DEFAULT_MARKET_CODES), 190)
        for code in ('gb','au','sg','hk','cn','tw','id','th','vn','ng','ke','ar','cl'):
            self.assertIn(code, MARKET_BY_CODE)

    def test_global_market_plan_moves_undercovered_markets_before_us(self):
        cfg=SimpleNamespace(discovery_markets=['us','gb','au','sg','hk','id','vn'], discovery_market_strategy='global')
        evidence={
            'us':{'attempts':100}, 'gb':{'attempts':40}, 'au':{'attempts':30},
            'sg':{'attempts':20}, 'hk':{'attempts':10}, 'id':{'attempts':0}, 'vn':{'attempts':0},
        }
        plan=market_plan(cfg,campaign_id=2,rotation_offset=0,evidence=evidence)
        self.assertEqual(plan['effective_strategy'],'global')
        self.assertLess(plan['ordered_codes'].index('id'), plan['ordered_codes'].index('us'))
        self.assertLess(plan['ordered_codes'].index('vn'), plan['ordered_codes'].index('us'))

    def test_global_workload_does_not_rotate_covered_market_ahead_of_deficit(self):
        cfg=SimpleNamespace(discovery_markets=['us','gb','id','vn'], discovery_market_strategy='global')
        evidence={'us':{'attempts':100},'gb':{'attempts':80},'id':{'attempts':0},'vn':{'attempts':1}}
        plan=market_plan(cfg,campaign_id=5,rotation_offset=3,evidence=evidence)
        schedule=market_workload_schedule(plan,2,rotation_offset=3)
        self.assertEqual(schedule[0].code,'id')
        self.assertEqual(schedule[1].code,'vn')

    def test_global_workload_keeps_a_core_market_lane_without_duplicate_slots(self):
        cfg=SimpleNamespace(discovery_markets=[], discovery_market_strategy='global')
        plan=market_plan(cfg,campaign_id=3,rotation_offset=3,evidence={'us':{'attempts':100},'gb':{'attempts':80}})
        schedule=market_workload_schedule(plan,12,rotation_offset=3)
        codes=[x.code for x in schedule]
        self.assertEqual(len(codes),len(set(codes)))
        self.assertTrue(any(code in {'gb','au','sg','hk','us','ca'} for code in codes))

    def test_multilingual_budget_scales_with_market_footprint_but_is_bounded(self):
        low=SimpleNamespace(multilingual_exploration_strength='low', discovery_markets=DEFAULT_MARKET_CODES)
        balanced=SimpleNamespace(multilingual_exploration_strength='balanced', discovery_markets=DEFAULT_MARKET_CODES)
        high=SimpleNamespace(multilingual_exploration_strength='high', discovery_markets=DEFAULT_MARKET_CODES)
        self.assertGreaterEqual(multilingual_strength_cap(low), 10)
        self.assertEqual(multilingual_strength_cap(balanced),16)
        self.assertEqual(multilingual_strength_cap(high),16)

    def test_native_language_assignments_rotate_across_same_language_markets(self):
        cfg=SimpleNamespace(multilingual_exploration_strength='high', multilingual_languages=[])
        markets=[MARKET_BY_CODE[x] for x in ('es','mx','ar','cl','fr','be')]
        first=multilingual_assignments(cfg,markets,rotation_offset=0)
        second=multilingual_assignments(cfg,markets,rotation_offset=1)
        first_spanish=[x['market'].code for x in first if x['language']=='Spanish']
        second_spanish=[x['market'].code for x in second if x['language']=='Spanish']
        self.assertGreaterEqual(len(first_spanish),3)
        self.assertNotEqual(first_spanish[0],second_spanish[0])

    def test_page_translation_language_can_come_from_market_or_detector(self):
        self.assertEqual(_translation_language_for_result({'_discovery_market_code':'kr'},'ko'),('Korean','market'))
        self.assertEqual(_translation_language_for_result({},'ja'),('Japanese','detector'))
        self.assertEqual(_translation_language_for_result({},'zh-cn'),('Chinese','detector'))

    def test_market_specific_source_hint_beats_unrelated_page_country_fallback(self):
        result=resolve_opportunity_location(
            target_url='https://hk.jobsdb.com/job/12345',
            inspected={}, page_title='Embedded Engineer',
            page_text='Example Corp is headquartered in the United States.',
            market_location_hint='Hong Kong',
        )
        self.assertEqual(result['country'],'Hong Kong')
        self.assertEqual(result['provenance']['source'],'discovery_market_source_fallback')
        self.assertTrue(result['provenance']['fallback'])

    def test_searchapi_locale_requires_market_and_is_explicit(self):
        with self.assertRaises(RuntimeError):
            _searchapi_locale(None)
        au=_searchapi_locale(MARKET_BY_CODE['au'])
        self.assertEqual(au['gl'],'au')
        self.assertEqual(au['hl'],'en')
        self.assertEqual(au['location'],'Australia')
        cn=_searchapi_locale(MARKET_BY_CODE['cn'])
        self.assertEqual(cn['gl'],'cn')
        self.assertEqual(cn['hl'],'zh-cn')
        self.assertEqual(cn['location'],'China')


    def test_searchapi_google_jobs_country_rejection_retries_with_location_intact(self):
        class FakeResponse:
            def __init__(self,status,data):
                import json
                self.status_code=status; self._data=data; self.content=json.dumps(data).encode(); self.text=self.content.decode()
                self.ok=200 <= status < 300
            def json(self): return self._data
            def raise_for_status(self):
                if not self.ok:
                    import requests
                    raise requests.HTTPError(f'{self.status_code} error')
        source=SimpleNamespace(name='SearchAPI · Google Jobs')
        calls=[]
        def fake_get(url,params=None,headers=None,timeout=None):
            calls.append(dict(params or {}))
            if len(calls)==1:
                return FakeResponse(400,{'error':{'message':'Unsupported gl country value'}})
            return FakeResponse(200,{'jobs':[],'search_metadata':{'status':'Success'}})
        with patch('portal.services.search._provider_secret',return_value='secret'), patch('portal.services.search.requests.get',side_effect=fake_get):
            data,_=_searchapi_request(source,'google_jobs','firmware engineer',market=MARKET_BY_CODE['au'])
        self.assertEqual(data.get('jobs'),[])
        self.assertEqual(calls[0]['gl'],'au')
        self.assertNotIn('gl',calls[1])
        self.assertEqual(calls[1]['location'],'Australia')
        self.assertEqual(calls[1]['hl'],'en')
        self.assertNotIn('lr',calls[1])

    def test_searchapi_prefers_direct_ats_apply_link_over_aggregator(self):
        item={
            'apply_link':'https://www.linkedin.com/jobs/view/123',
            'apply_links':[
                {'source':'LinkedIn','link':'https://www.linkedin.com/jobs/view/123'},
                {'source':'Example Careers','link':'https://boards.greenhouse.io/example/jobs/456'},
            ],
        }
        link,source=_searchapi_apply_link(item)
        self.assertEqual(link,'https://boards.greenhouse.io/example/jobs/456')
        self.assertEqual(source,'Example Careers')

    def test_searchapi_jobs_parser_keeps_structured_location_and_direct_evidence(self):
        data={'jobs':[{
            'title':'Firmware Engineer','company_name':'Example','location':'Singapore',
            'description':'Build embedded systems and device firmware for production products. '*4,
            'extensions':['Full-time','2 days ago'],
            'apply_link':'https://example.com/careers/jobs/firmware-123',
            'apply_links':[{'source':'Example Careers','link':'https://example.com/careers/jobs/firmware-123'}],
            'via':'Example Careers',
        }]}
        rows=_searchapi_job_rows(data,10)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['_direct_source'])
        self.assertEqual(rows[0]['_direct_adapter'],'searchapi_google_jobs')
        self.assertEqual(rows[0]['_role_location_hint'],'Singapore')
        self.assertEqual(rows[0]['company'],'Example')
