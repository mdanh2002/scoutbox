from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from portal.models import BackgroundJob, Campaign, CampaignRun, Contact
from portal.services.fresh_sources import _reddit
from portal.services.cold import scan_hidden_market
from portal.templatetags.portal_extras import email_domain_home_url
from portal.tasks import recover_stalled_operations_state
from portal.views import _diagnostic_period


class Release01078UiRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='release-01078', password='test-password')
        self.client.force_login(self.user)

    def test_address_book_company_links_to_email_domain(self):
        Contact.objects.create(
            email='morgan@experiencedevin.com', name='Morgan', company='Experienced Devin',
            company_country='United States', source='manual', source_url='https://unrelated.example/profile',
        )
        response = self.client.get(reverse('contacts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="contact-company-line contact-company-link"')
        self.assertContains(response, 'href="https://experiencedevin.com/"')
        self.assertContains(response, 'title="experiencedevin.com"')
        self.assertNotContains(response, 'href="https://unrelated.example/profile" target="_blank" rel="noreferrer" title="experiencedevin.com"')

    def test_email_domain_home_url_is_normalized(self):
        self.assertEqual(email_domain_home_url(' Name@Example.COM '), 'https://example.com/')
        self.assertEqual(email_domain_home_url('not-an-email'), '')

    def test_diagnostic_export_supports_last_hour(self):
        request = RequestFactory().get('/settings/diagnostics/export', {'period': '1h'})
        period, start = _diagnostic_period(request)
        self.assertEqual(period, '1h')
        self.assertIsNotNone(start)
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="1h">Last 1 hour</option>', html=True)


class Release01078StallRecoveryTests(TestCase):
    @override_settings(CELERY_BROKER_URL='redis://invalid-for-test:6379/0')
    @patch('portal.tasks._clear_recovery_coordination_keys', return_value={'deleted': 2, 'patterns': {}, 'error': ''})
    @patch('portal.tasks.hidden_market_scan_job.delay', return_value=SimpleNamespace(id='hidden-recovery-task'))
    @patch('portal.tasks.run_campaign_job.delay', return_value=SimpleNamespace(id='campaign-recovery-task'))
    @patch('portal.tasks.current_app')
    def test_recovery_releases_persistent_state_and_requeues_safe_work(self, celery_app, run_delay, hidden_delay, _clear):
        campaign = Campaign.objects.create(name='Recovery Campaign')
        old_run = CampaignRun.objects.create(
            campaign=campaign, status='running', progress=47, stage='Searching Reddit',
            message='Searching Reddit', celery_task_id='old-campaign-task', criteria={'run_kind': 'normal'},
        )
        old_hidden = BackgroundJob.objects.create(
            kind='hidden_scan', label='Hidden Leads scan', status='running', progress=32,
            message='Searching providers', celery_task_id='old-hidden-task',
        )
        one_off = BackgroundJob.objects.create(
            kind='cold_draft', label='Cold outreach draft', status='queued',
            message='Queued', celery_task_id='old-one-off-task',
        )

        result = recover_stalled_operations_state()

        old_run.refresh_from_db(); old_hidden.refresh_from_db(); one_off.refresh_from_db()
        self.assertEqual(old_run.status, 'stopped')
        self.assertEqual(old_hidden.status, 'stopped')
        self.assertEqual(one_off.status, 'stopped')
        self.assertEqual(result['campaign_runs_requeued'], 1)
        self.assertTrue(result['hidden_scan_requeued'])
        self.assertEqual(result['coordination_keys_deleted'], 2)
        self.assertEqual(CampaignRun.objects.filter(campaign=campaign, status='queued').count(), 1)
        self.assertEqual(BackgroundJob.objects.filter(kind='hidden_scan', status='queued').count(), 1)
        self.assertEqual(BackgroundJob.objects.filter(kind='cold_draft', status='queued').count(), 0)
        self.assertEqual(run_delay.call_count, 1)
        self.assertEqual(hidden_delay.call_count, 1)
        self.assertGreaterEqual(celery_app.control.revoke.call_count, 3)


    @patch.dict('os.environ', {'SCOUTBOX_SEARCH_PROVIDER_MAX_CONSECUTIVE_ERRORS': '2'}, clear=False)
    @patch('portal.services.cold._providers', return_value=[SimpleNamespace(name='Slow Search', pk=7)])
    @patch('portal.services.cold._terms', return_value=['embedded'])
    @patch('portal.services.cold.search_source', return_value=([], 'provider timeout'))
    def test_hidden_leads_search_rotates_after_repeated_provider_errors(self, search_source, _terms, _providers):
        result = scan_hidden_market(max_queries=12, max_seconds=300)
        self.assertEqual(search_source.call_count, 2)
        self.assertTrue(any('stopped this provider after 2 consecutive request errors' in row for row in result['errors']))

    @patch.dict('os.environ', {
        'SCOUTBOX_REDDIT_MAX_QUERIES_PER_PASS': '8',
        'SCOUTBOX_REDDIT_MAX_CONSECUTIVE_ERRORS': '2',
        'SCOUTBOX_REDDIT_PASS_MAX_SECONDS': '75',
        'SCOUTBOX_REDDIT_REQUEST_TIMEOUT_SECONDS': '10',
    }, clear=False)
    @patch('portal.services.fresh_sources._reddit_token', return_value='')
    @patch('portal.services.fresh_sources._direct_query_variants', return_value=['one', 'two', 'three', 'four'])
    @patch('portal.services.fresh_sources._request_json', return_value=(None, 'provider timeout'))
    def test_reddit_fails_fast_after_repeated_request_errors(self, request_json, _variants, _token):
        source = SimpleNamespace(name='Reddit', pk=1)
        rows, error = _reddit(source, SimpleNamespace(), {}, 20)
        self.assertEqual(rows, [])
        self.assertEqual(request_json.call_count, 2)
        self.assertIn('error limit reached after 2 consecutive errors', error)
        for call in request_json.call_args_list:
            self.assertEqual(call.kwargs.get('timeout'), 10)
