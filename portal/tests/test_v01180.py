from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.discovery_markets import MARKET_BY_CODE, auto_multilingual_languages, multilingual_assignments
from portal.views import _market_coverage_from_rows


class Release01180MarketCoverageTests(SimpleTestCase):
    def test_market_coverage_counts_languages_and_markets_by_requests(self):
        result=_market_coverage_from_rows([
            {'metadata__market_code':'worldwide','metadata__market':'Worldwide','metadata__multilingual_language':'','requests':8},
            {'metadata__market_code':'fr','metadata__market':'France','metadata__multilingual_language':'French','requests':3},
            {'metadata__market_code':'de','metadata__market':'Germany','metadata__multilingual_language':'German','requests':2},
        ])
        self.assertEqual(result['total_requests'],13)
        self.assertEqual([(x['label'],x['requests']) for x in result['languages']],[('English',8),('French',3),('German',2)])
        self.assertEqual(result['markets'][0]['label'],'Worldwide')
        self.assertEqual(result['markets'][1]['flag'],MARKET_BY_CODE['fr'].flag)

    def test_multilingual_work_ignores_legacy_disabled_flag(self):
        settings=SimpleNamespace(
            discovery_markets=['worldwide','fr'],
            multilingual_exploration_enabled=False,
            multilingual_exploration_strength='balanced',
            multilingual_languages=['German'],
        )
        self.assertEqual(auto_multilingual_languages(settings),['French','German'])
        self.assertEqual(len(multilingual_assignments(settings,[MARKET_BY_CODE['fr'],MARKET_BY_CODE['worldwide']])),2)
