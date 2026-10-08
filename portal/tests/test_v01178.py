from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from portal.services.discovery import _search_source_with_liveness
from portal.services.discovery_markets import MARKET_BY_CODE, market_from_location
from portal.services.search import provider_region_context, provider_market_compatible


class Release01178SearchRegionTests(SimpleTestCase):
    def test_provider_region_context_uses_adapter_setting(self):
        market=MARKET_BY_CODE['gb']
        self.assertEqual(provider_region_context('Bing',market)['region_setting'],'en-GB')
        self.assertEqual(provider_region_context('DuckDuckGo',market)['region_setting'],'uk-en')
        self.assertEqual(provider_region_context('Naver',market)['region_setting'],'ko-KR')
        self.assertEqual(provider_region_context('Brave Search',market),{})

    def test_regional_provider_market_compatibility(self):
        self.assertEqual(market_from_location('Singapore'),MARKET_BY_CODE['sg'])
        self.assertTrue(provider_market_compatible('DuckDuckGo',MARKET_BY_CODE['sg']))
        self.assertTrue(provider_market_compatible('Naver',MARKET_BY_CODE['sg']))
        self.assertTrue(provider_market_compatible('Naver',MARKET_BY_CODE['kr']))

    @patch('portal.services.discovery.search_source')
    def test_liveness_status_splits_multi_site_queries_before_dispatch(self,search_source):
        search_source.side_effect=lambda provider,query,**kwargs: ([{'url':'https://example.com/'+str(search_source.call_count)}],'')
        messages=[]
        provider=SimpleNamespace(name='Bing')
        rows,error=_search_source_with_liveness(
            provider,'site:example.com site:example.org "firmware engineer"',5,
            lambda progress,message: messages.append(message),20,'unsplit',market=MARKET_BY_CODE['gb'],
        )
        self.assertFalse(error)
        self.assertEqual(search_source.call_count,2)
        for call in search_source.call_args_list:
            self.assertLessEqual(call.args[1].lower().count('site:'),1)
        self.assertTrue(messages)
        self.assertTrue(all(message.lower().count('site:')<=1 for message in messages))
        self.assertEqual(len(rows),2)
