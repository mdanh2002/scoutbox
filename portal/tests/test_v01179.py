from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.discovery_markets import MARKET_BY_CODE, market_workload_schedule, multilingual_assignments
from portal.services.location import _jobicy_snapshot_role_location
from portal.services.location_values import parse_location_items
from portal.services.pagefetch import _jobposting_schema


class Release01179RegressionTests(SimpleTestCase):
    def test_market_flags_and_worldwide_globe(self):
        self.assertEqual(MARKET_BY_CODE['kr'].flag,'🇰🇷')
        self.assertEqual(MARKET_BY_CODE['worldwide'].flag,'🌐')

    def test_productive_markets_keep_three_quarters_of_early_work(self):
        plan={
            'markets':[MARKET_BY_CODE[x] for x in ('kr','de','worldwide','us')],
            'evidence':{
                'worldwide':{'attempts':10,'pages':20,'retained':2},
                'us':{'attempts':8,'pages':12,'retained':1},
                'kr':{'attempts':8,'pages':0,'retained':0},
                'de':{'attempts':8,'pages':0,'retained':0},
            },
        }
        scheduled=market_workload_schedule(plan,8)
        self.assertEqual(sum(x.code in {'worldwide','us'} for x in scheduled),6)
        self.assertEqual(sum(x.code in {'kr','de'} for x in scheduled),2)

    def test_native_market_language_is_not_starved_by_additional_languages(self):
        cfg=SimpleNamespace(
            multilingual_exploration_enabled=True,multilingual_exploration_strength='balanced',
            multilingual_languages=['French','German'],
        )
        rows=multilingual_assignments(cfg,[MARKET_BY_CODE['kr'],MARKET_BY_CODE['worldwide']])
        self.assertEqual(rows[0]['language'],'Korean')
        self.assertEqual(rows[0]['market'].code,'kr')
        self.assertEqual(rows[1]['source'],'additional')

    def test_jobicy_remote_from_preserves_multiple_regions(self):
        text='Remote from\n[APAC](https://jobicy.com/job-region/apac), [EMEA](https://jobicy.com/job-region/emea)\nSalary\nUndisclosed'
        self.assertEqual(_jobicy_snapshot_role_location(text),'APAC, EMEA')

    def test_gcc_compiler_is_not_a_location(self):
        self.assertEqual(parse_location_items('Buildroot uses the GCC compiler and GNU toolchain'),[])
        self.assertEqual([x['label'] for x in parse_location_items('Hiring across GCC countries')],['GCC'])

    def test_jobposting_schema_exposes_current_hiring_organization(self):
        from bs4 import BeautifulSoup
        soup=BeautifulSoup('<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","hiringOrganization":{"@type":"Organization","name":"Canonical"}}</script>','html.parser')
        schema=_jobposting_schema(soup)
        self.assertEqual(schema['hiringOrganization']['name'],'Canonical')
