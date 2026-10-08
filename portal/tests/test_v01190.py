from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.discovery_markets import MARKET_BY_CODE, market_workload_schedule
from portal.services.search import provider_market_compatible


class Release01190MarketRoutingTests(SimpleTestCase):
    def test_worldwide_without_results_is_only_an_exploration_lane(self):
        plan = {
            'markets': [MARKET_BY_CODE[x] for x in ('worldwide', 'sg', 'kr')],
            'evidence': {
                'worldwide': {'attempts': 40, 'pages': 0, 'retained': 0},
                'sg': {'attempts': 10, 'pages': 16, 'retained': 2},
                'kr': {'attempts': 10, 'pages': 8, 'retained': 1},
            },
        }
        scheduled = market_workload_schedule(plan, 8)
        self.assertLessEqual(sum(x.code == 'worldwide' for x in scheduled), 2)
        self.assertGreater(sum(x.code == 'sg' for x in scheduled), 0)

    def test_naver_remains_available_for_international_markets(self):
        provider = SimpleNamespace(name='Naver')
        self.assertTrue(provider_market_compatible(provider, MARKET_BY_CODE['sg']))
        self.assertTrue(provider_market_compatible(provider, MARKET_BY_CODE['worldwide']))
