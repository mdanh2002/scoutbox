from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from portal.models import Campaign, CampaignRun, PortalSettings
from portal import tasks


class Release01081SchedulerTests(TestCase):
    def setUp(self):
        self.settings = PortalSettings.objects.get_or_create(pk=1)[0]
        self.campaign = Campaign.objects.create(name='Emulation', enabled=True)
        self.now = timezone.now()

    def test_campaign_criteria_writes_scheduler_flags_explicitly(self):
        criteria = tasks._campaign_criteria(self.campaign)
        self.assertIs(criteria['forum_only'], False)
        self.assertIs(criteria['deferred_local_ai'], False)
        self.assertEqual(criteria['run_kind'], 'primary')

    def test_legacy_missing_forum_flag_is_still_primary(self):
        legacy = CampaignRun.objects.create(campaign=self.campaign, status='failed', criteria={})
        forum = CampaignRun.objects.create(
            campaign=self.campaign, status='stopped',
            criteria={'forum_only': True, 'run_kind': 'forum_only'},
        )
        primary_ids = {r.pk for r in tasks._non_forum_runs(CampaignRun.objects.order_by('pk'))}
        self.assertIn(legacy.pk, primary_ids)
        self.assertNotIn(forum.pk, primary_ids)

    def test_failed_primary_attempts_count_as_window_coverage(self):
        window_start = self.now - timedelta(minutes=10)
        for _ in range(2):
            CampaignRun.objects.create(
                campaign=self.campaign,
                status='failed',
                criteria={'forum_only': False, 'deferred_local_ai': False, 'run_kind': 'primary'},
            )
        ok, state = tasks._forum_primary_idle_state(
            [self.campaign], self.now, self.settings,
            cloud_primary=False, window_start=window_start,
            window_seconds=3600, target_attempts=2, gap_seconds=900,
        )
        self.assertTrue(ok)
        self.assertEqual(state['reason'], 'primary search coverage complete')

    def test_deferred_primary_is_not_coverage_but_remains_primary_attempt(self):
        run = CampaignRun.objects.create(
            campaign=self.campaign,
            status='stopped',
            criteria={'forum_only': False, 'deferred_local_ai': True, 'run_kind': 'primary'},
        )
        rows = list(CampaignRun.objects.filter(pk=run.pk))
        self.assertEqual(tasks._primary_coverage_runs(rows), [])
        self.assertEqual([r.pk for r in tasks._non_forum_runs(rows)], [run.pk])
