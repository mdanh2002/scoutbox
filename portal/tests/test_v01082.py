from unittest import mock

from django.test import TestCase

from portal import tasks
from portal.services.queryplanner import sanitize_local_search_engine_query, sanitize_search_engine_query


class Release01082ThroughputAndQueryTests(TestCase):
    def test_search_query_keeps_only_one_site_constraint(self):
        raw = 'site:facebook.com site:oracle.com "firmware engineer" linux systems hiring'
        cleaned = sanitize_local_search_engine_query(raw)
        self.assertEqual(cleaned.count('site:'), 1)
        self.assertIn('site:facebook.com', cleaned)
        self.assertNotIn('site:oracle.com', cleaned)
        self.assertIn('firmware engineer', cleaned)

    def test_generic_search_sanitizer_also_keeps_only_one_site_constraint(self):
        cleaned = sanitize_search_engine_query('site:facebook.com site:oracle.com "firmware engineer" hiring')
        self.assertEqual(cleaned.count('site:'), 1)
        self.assertEqual(cleaned.split()[0], 'site:facebook.com')

    def test_local_campaign_capacity_is_not_generation_lane_capacity(self):
        with mock.patch.dict('os.environ', {
            'SCOUTBOX_DISCOVERY_AUTO_INFLIGHT': '2',
            'SCOUTBOX_LOCAL_AI_GENERATION_LANES': '1',
        }, clear=False):
            self.assertEqual(tasks._local_discovery_capacity_limit(2), 2)

    def test_explicit_local_campaign_capacity_override_is_honored(self):
        with mock.patch.dict('os.environ', {
            'SCOUTBOX_DISCOVERY_AUTO_INFLIGHT': '2',
            'SCOUTBOX_LOCAL_AI_GENERATION_LANES': '1',
            'SCOUTBOX_LOCAL_CAMPAIGN_INFLIGHT': '1',
        }, clear=False):
            self.assertEqual(tasks._local_discovery_capacity_limit(2), 1)
