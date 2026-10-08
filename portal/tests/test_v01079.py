import importlib
import inspect
from unittest.mock import Mock, patch

import requests

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from portal.models import BackgroundJob, Campaign, CampaignRun, Contact, Opportunity, PortalSettings, SearchProviderStat, SearchSource
from portal.services.ai import AIEmptyOutputWarning, CloudRateLimited, LocalAILaneBusy, _cloud_campaign_call_with_backoff, _run_ollama_with_campaign_lane, cloud_web_search, generate_with_route
from portal.services.cold import _hidden_lead_organization_signal
from portal.services.fresh_sources import forum_source_rows
from portal.services.mailbox import is_generic
from portal.services.search import ACTIVE_PROVIDER_NAMES, provider_query_allowance, provider_selection_details


class Release01079SourceBalanceTests(TestCase):
    def setUp(self):
        SearchSource.objects.filter(name__in=ACTIVE_PROVIDER_NAMES).update(enabled=False)
        self.naver, _ = SearchSource.objects.update_or_create(
            name='Naver', defaults={'category':'search','source_type':'regional_search','enabled':True,'preferred_initial':True,'priority':50,'provider_weight':100,'requires_credentials':False,'public_fallback':True,'config_json':{'access_type':'public'}}
        )
        self.brave, _ = SearchSource.objects.update_or_create(
            name='Brave Search', defaults={'category':'search','source_type':'search_engine','enabled':True,'preferred_initial':True,'priority':50,'provider_weight':100,'requires_credentials':False,'public_fallback':True,'config_json':{'access_type':'public'}}
        )
        SearchProviderStat.objects.update_or_create(
            source=self.naver, day=timezone.localdate(), defaults={'requests':100,'results':800,'unique_results':12,'errors':5}
        )
        SearchProviderStat.objects.update_or_create(
            source=self.brave, day=timezone.localdate(), defaults={'requests':100,'results':10,'unique_results':0,'errors':80}
        )
        PortalSettings.objects.get_or_create(pk=1)

    def test_productive_provider_keeps_query_slice_and_degraded_provider_gets_probe(self):
        self.assertEqual(provider_query_allowance(self.naver, 6), 6)
        self.assertEqual(provider_query_allowance(self.brave, 6), 1)

    def test_retained_yield_ranks_a_productive_engine_ahead_of_high_error_engine(self):
        selected, details = provider_selection_details(limit=2)
        names = [row.name for row in selected]
        self.assertIn('Naver', names)
        self.assertLess(names.index('Naver'), names.index('Brave Search') if 'Brave Search' in names else 99)
        self.assertEqual(details['adaptive_health_7d']['Brave Search']['query_allowance'], 1)

    def test_low_yield_retained_engine_gets_diversification_slice_not_full_volume(self):
        bing, _ = SearchSource.objects.update_or_create(
            name='Bing', defaults={'category':'search','source_type':'search_engine','enabled':True,'preferred_initial':True,'priority':50,'provider_weight':100,'requires_credentials':False,'public_fallback':True,'config_json':{'access_type':'public'}}
        )
        SearchProviderStat.objects.update_or_create(
            source=bing, day=timezone.localdate(), defaults={'requests':1000,'results':6000,'unique_results':1,'errors':1}
        )
        Opportunity.objects.create(title='Rare retained hit', company='Example', url='https://example.net/job', source=bing)
        self.assertEqual(provider_query_allowance(bing, 100), 20)

    def test_forum_source_rows_accepts_bounded_stage_arguments(self):
        signature = inspect.signature(forum_source_rows)
        self.assertIn('stage_budget_seconds', signature.parameters)
        self.assertIn('max_sources', signature.parameters)


    def test_recycled_provider_is_demoted_to_recovery_probe(self):
        for idx in range(3):
            Opportunity.objects.create(
                title=f'Recycled {idx}', company='Example', url=f'https://example.com/jobs/{idx}',
                source=self.naver, user_deleted=True,
            )
        self.assertEqual(provider_query_allowance(self.naver, 6), 1)


class Release01079ForumIsolationTests(TestCase):
    def test_forum_local_ai_yields_when_primary_discovery_is_waiting(self):
        campaign = Campaign.objects.create(name='Primary campaign')
        CampaignRun.objects.create(campaign=campaign, status='queued', criteria={'forum_only': False})
        call = Mock(return_value='should not run')
        with patch('portal.services.ai.usage_context', return_value={'campaign_run_id': 9999, 'forum_only': True}), \
             patch('portal.services.ai._local_ai_lock_client', return_value=Mock()):
            with self.assertRaises(LocalAILaneBusy):
                _run_ollama_with_campaign_lane(call, stage='first_filter', timeout=60)
        call.assert_not_called()

    def test_forum_local_ai_yields_to_any_background_job(self):
        BackgroundJob.objects.create(kind='hidden_scan', label='Hidden scan', status='queued')
        call = Mock(return_value='should not run')
        lock = Mock(); lock.set.return_value = True
        with patch('portal.services.ai.usage_context', return_value={'campaign_run_id': 9999, 'forum_only': True}), \
             patch('portal.services.ai._local_ai_lock_client', return_value=lock):
            with self.assertRaises(LocalAILaneBusy):
                _run_ollama_with_campaign_lane(call, stage='first_filter', timeout=60)
        call.assert_not_called()

    def test_forum_cloud_rate_limit_does_not_sleep_through_backoff(self):
        response = requests.Response()
        response.status_code = 429
        response._content = b'RATE_LIMITED'
        exc = requests.HTTPError('429 Too Many Requests', response=response)
        call = Mock(side_effect=exc)
        with patch('portal.services.ai.usage_context', return_value={'campaign_run_id': 9999, 'forum_only': True}), \
             patch('portal.services.ai.time.sleep') as sleep:
            with self.assertRaises(CloudRateLimited):
                _cloud_campaign_call_with_backoff(call, 'gemini', 'gemini-test', 'url_scrape', {})
        self.assertEqual(call.call_count, 1)
        sleep.assert_not_called()



class Release01079QualityTests(TestCase):
    def test_functional_address_book_mailboxes_are_generic(self):
        for address in (
            'marketing@example.com', 'campaigns@example.com', 'recruit@example.com',
            'recruiter@example.com', 'work@example.com', 'askhr@example.com',
            'people.ops@example.com', 'business-development@example.com',
        ):
            with self.subTest(address=address):
                self.assertTrue(is_generic(address))
        self.assertFalse(is_generic('morgan@example.com'))

    def test_generic_repair_migration_marks_existing_functional_contacts_without_deleting(self):
        contact = Contact.objects.create(email='marketing@example.com', name='Marketing', company='Example', generic=False)
        migration = importlib.import_module('portal.migrations.0108_v01079_contact_generic_repair')
        migration.repair_functional_contact_flags(apps, None)
        contact.refresh_from_db()
        self.assertTrue(contact.generic)
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_hidden_lead_requires_first_party_organization_evidence(self):
        article = 'Embedded firmware reverse engineering article. The author is working on a driver and emulator.'
        company = 'Acme Embedded'
        self.assertFalse(_hidden_lead_organization_signal(company, article, technical_hits=3, activity_hits=2))
        first_party = 'Acme Embedded. About us. We build embedded products and provide engineering services to customers.'
        self.assertTrue(_hidden_lead_organization_signal(company, first_party, technical_hits=2, activity_hits=1))


class Release01079CloudRecoveryTests(TestCase):
    @patch('portal.services.ai.web_search_with')
    @patch('portal.services.ai.configured_cloud_web_routes', return_value=[('gemini','gemini-3.5-flash-lite','primary')])
    def test_cloud_web_retries_gemini_empty_output_with_minimal_mode(self, _routes, web_search):
        web_search.side_effect = [AIEmptyOutputWarning('empty'), ('usable response', {'provider':'gemini','model':'gemini-3.5-flash-lite'})]
        text, meta = cloud_web_search('Find a current opportunity', stage='url_scrape')
        self.assertEqual(text, 'usable response')
        self.assertTrue(meta.get('empty_output_retry'))
        self.assertEqual(web_search.call_count, 2)
        retry_kwargs = web_search.call_args_list[1].kwargs
        self.assertTrue(retry_kwargs['config_override']['_manual_empty_retry_minimal'])
        self.assertTrue(retry_kwargs['config_override']['_manual_disable_json_mime'])

    @patch('portal.services.ai.web_search_with')
    @patch('portal.services.ai.configured_cloud_web_routes', return_value=[('gemini','gemini-3.5-flash-lite','primary'), ('openai','gpt-test','fallback')])
    def test_forum_cloud_web_empty_output_does_not_retry_or_failover(self, _routes, web_search):
        web_search.side_effect = AIEmptyOutputWarning('empty')
        with patch('portal.services.ai.usage_context', return_value={'campaign_run_id': 9999, 'forum_only': True, 'discovery_mode':'cloud_web'}):
            with self.assertRaises(AIEmptyOutputWarning):
                cloud_web_search('Find a forum opportunity', stage='url_scrape')
        self.assertEqual(web_search.call_count, 1)

    @patch('portal.services.ai.generate_with')
    def test_cloud_generation_retries_gemini_empty_output_before_failover(self, generate):
        generate.side_effect = [AIEmptyOutputWarning('empty'), ('usable response', {'provider':'gemini'})]
        route = {'provider':'gemini','model':'gemini-3.5-flash-lite'}
        text = generate_with_route(route, 'Return a short answer.', stage='first_filter')
        self.assertEqual(text, 'usable response')
        self.assertEqual(generate.call_count, 2)
        retry_kwargs = generate.call_args_list[1].kwargs
        self.assertTrue(retry_kwargs['config_override']['_manual_empty_retry_minimal'])
        self.assertTrue(retry_kwargs['config_override']['_manual_disable_json_mime'])
