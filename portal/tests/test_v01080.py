from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from portal.models import Campaign, CampaignRun, PortalSettings, SearchProviderStat, SearchSource, UsageMetric
from portal.services.fresh_sources import _forum_generic, forum_source_rows
from portal.services.search import ACTIVE_PROVIDER_NAMES, _degraded_provider_probe_due, provider_selection_details
from portal.tasks import _forum_primary_idle_state


class Release01080ForumPriorityTests(TestCase):
    def setUp(self):
        self.settings = PortalSettings.objects.get_or_create(pk=1)[0]
        self.campaign = Campaign.objects.create(name='Embedded systems')
        self.now = timezone.now()
        self.window_start = self.now - timedelta(minutes=10)

    def test_local_forum_waits_until_primary_search_coverage_is_complete(self):
        ok, state = _forum_primary_idle_state(
            [self.campaign], self.now, self.settings,
            cloud_primary=False, window_start=self.window_start,
            window_seconds=7200, target_attempts=2, gap_seconds=900,
        )
        self.assertFalse(ok)
        self.assertEqual(state['reason'], 'primary search coverage incomplete')

        for idx in range(2):
            CampaignRun.objects.create(
                campaign=self.campaign, status='completed',
                criteria={'forum_only': False},
                created_at=self.window_start + timedelta(minutes=idx + 1),
            )
        ok, state = _forum_primary_idle_state(
            [self.campaign], self.now, self.settings,
            cloud_primary=False, window_start=self.window_start,
            window_seconds=7200, target_attempts=2, gap_seconds=900,
        )
        self.assertTrue(ok)
        self.assertEqual(state['reason'], 'primary search coverage complete')

    def test_cloud_forum_does_not_start_when_primary_cloud_run_is_due_soon(self):
        self.settings.scraper_interval_minutes = 120
        self.settings.cloud_min_interval_minutes = 120
        self.settings.cloud_auto_runs_per_campaign_day = 5
        self.settings.save()
        run = CampaignRun.objects.create(
            campaign=self.campaign, status='completed',
            criteria={'automatic': True, 'forum_only': False},
        )
        CampaignRun.objects.filter(pk=run.pk).update(created_at=self.now - timedelta(minutes=118))
        ok, state = _forum_primary_idle_state(
            [self.campaign], self.now, self.settings,
            cloud_primary=True, window_start=self.window_start,
            window_seconds=7200, target_attempts=1, gap_seconds=7200,
        )
        self.assertFalse(ok)
        self.assertEqual(state['reason'], 'Cloud primary discovery is due soon')

    def test_forum_source_helper_clamps_long_multi_source_request(self):
        with patch('portal.services.fresh_sources.direct_source_rows', return_value=([], [], {})) as direct:
            forum_source_rows(self.campaign, {}, stage_budget_seconds=300, max_sources=8)
        kwargs = direct.call_args.kwargs
        self.assertEqual(kwargs['stage_budget_seconds'], 25)
        self.assertEqual(kwargs['max_sources'], 1)

    def test_forum_adapter_preempts_before_first_http_request(self):
        source = SearchSource.objects.create(
            name='Test Forum', category='forum', source_type='forum', enabled=True,
            base_url='https://forum.example.invalid',
            config_json={'direct_adapter': 'forum_generic', 'forum_software': 'discourse'},
        )
        with patch('portal.services.fresh_sources._request_json') as request_json, \
             patch('portal.services.fresh_sources._request_text') as request_text:
            rows, error = _forum_generic(source, self.campaign, {}, 12, should_stop=lambda: True)
        self.assertEqual(rows, [])
        self.assertIn('yielded to primary discovery', error)
        request_json.assert_not_called()
        request_text.assert_not_called()


class Release01080SearchProbeTests(TestCase):
    def setUp(self):
        SearchSource.objects.filter(name__in=ACTIVE_PROVIDER_NAMES).update(enabled=False)
        self.good, _ = SearchSource.objects.update_or_create(
            name='Naver', defaults={
                'category': 'search', 'source_type': 'regional_search', 'enabled': True,
                'preferred_initial': True, 'priority': 50, 'provider_weight': 100,
                'requires_credentials': False, 'public_fallback': True,
                'config_json': {'access_type': 'public'},
            },
        )
        self.bad, _ = SearchSource.objects.update_or_create(
            name='Yahoo Search', defaults={
                'category': 'search', 'source_type': 'search_engine', 'enabled': True,
                'preferred_initial': True, 'priority': 50, 'provider_weight': 100,
                'requires_credentials': False, 'public_fallback': True,
                'config_json': {'access_type': 'public'},
            },
        )
        SearchProviderStat.objects.update_or_create(
            source=self.good, day=timezone.localdate(),
            defaults={'requests': 100, 'results': 700, 'unique_results': 12, 'errors': 5},
        )
        SearchProviderStat.objects.update_or_create(
            source=self.bad, day=timezone.localdate(),
            defaults={'requests': 100, 'results': 0, 'unique_results': 0, 'errors': 90},
        )
        PortalSettings.objects.get_or_create(pk=1)

    def test_recent_degraded_probe_blocks_duplicate_campaign_probe(self):
        UsageMetric.objects.create(
            category='search', provider='Yahoo Search', stage='query', requests=1, errors=1,
        )
        self.assertFalse(_degraded_provider_probe_due(self.bad, minutes=240))
        selected, details = provider_selection_details(limit=2)
        names = [row.name for row in selected]
        self.assertIn('Naver', names)
        self.assertNotIn('Yahoo Search', names)
        self.assertEqual(details['adaptive_health_7d']['Yahoo Search']['query_allowance'], 1)
