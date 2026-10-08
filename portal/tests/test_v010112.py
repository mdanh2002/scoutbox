from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.focus import _topic_rule_candidates
from portal.services.fresh_sources import _merge_rows_unique
from portal.services.freshness import opportunity_post_age_display_label, post_age_label_for_days
from portal.services.location import resolve_opportunity_location
from portal.services.location_values import parse_location_items
from portal.services.source_domains import direct_endpoint_variants, expand_source_domains


class Release010112LocationTests(SimpleTestCase):
    def test_jobicy_latam_display_beats_structured_country_expansion(self):
        structured=[{'@type':'Country','name':name} for name in (
            'Antigua and Barbuda','Argentina','Barbados','Bahamas','Belize'
        )]
        result=resolve_opportunity_location(
            target_url='https://jobicy.com/jobs/153171-qa-manual-test-engineer',
            inspected={'jobposting_location':structured},
            page_title='QA Manual Test Engineer',
            page_text='This is a remote role, but applicants must be located in Latin America.',
        )
        self.assertEqual(result['country'],'LATAM')
        self.assertEqual([x['label'] for x in result['locations']],['LATAM'])
        self.assertEqual(result['provenance']['source'],'explicit_page_role_location')

    def test_added_recruiter_regions_are_first_class(self):
        for raw,expected in (
            ('LATAM','LATAM'),('APAC','APAC'),('ASEAN','ASEAN'),('MENA','MENA'),
            ('EU/EEA','EU/EEA'),('Australia and New Zealand','ANZ'),
        ):
            items=parse_location_items(raw,source='test')
            self.assertEqual([x['label'] for x in items],[expected])
            self.assertEqual(items[0]['kind'],'region')


class Release010112FocusTests(SimpleTestCase):
    def test_campaign_name_cannot_trigger_embedded_focus(self):
        rows=_topic_rule_candidates(
            'QA Manual Test Engineer',
            'Validate web applications and payments workflows. Create test plans, regression testing and defect reports.',
            'Embedded Jobs',
        )
        labels=[x[0] for x in rows]
        self.assertIn('QA & Testing',labels)
        self.assertNotIn('Embedded Firmware',labels)
        self.assertNotIn('FinTech Engineering',labels)


class Release010112PostAgeTests(SimpleTestCase):
    def test_sub_week_bucket(self):
        for day in range(3):
            self.assertEqual(post_age_label_for_days(day),'< 3 days')
        for day in range(3,7):
            self.assertEqual(post_age_label_for_days(day),'< 1 week')
        for day in range(7,14):
            self.assertEqual(post_age_label_for_days(day),'~ 1 week')

    def test_exact_date_evidence_beats_legacy_bucket(self):
        # A retained exact date is evaluated before stale cached labels/counters.
        from django.utils import timezone
        now=timezone.now()
        row=SimpleNamespace(
            freshness_label='~ 1 week',freshness_confidence=98,
            declared_posted_at=now,estimated_first_seen=None,
            extracted_facts={'post_age':{'age_days':7,'exact_date':now.isoformat()}},
        )
        self.assertEqual(opportunity_post_age_display_label(row),'< 3 days')


class Release010112SourceVariantTests(SimpleTestCase):
    def test_variant_family_expands_from_non_default_member(self):
        self.assertEqual(expand_source_domains('seek.co.nz',limit=2),['seek.co.nz','seek.com.au'])
        self.assertIn('glassdoor.com',expand_source_domains('glassdoor.sg',limit=8))

    def test_direct_endpoint_variants_are_bounded(self):
        self.assertEqual(
            direct_endpoint_variants('lever','https://api.eu.lever.co/v0/postings',limit=2),
            ['https://api.eu.lever.co/v0/postings','https://api.lever.co/v0/postings'],
        )
        self.assertEqual(
            direct_endpoint_variants('jobicy','https://jobicy.com/api/v2/remote-jobs'),
            ['https://jobicy.com/api/v2/remote-jobs'],
        )

    def test_direct_rows_dedupe_across_variant_hosts(self):
        rows=[]
        _merge_rows_unique(rows,[
            {'url':'https://jobs.lever.co/acme/abc','_direct_adapter':'lever','_direct_item_id':'123','_ats_board':'acme'},
            {'url':'https://jobs.eu.lever.co/acme/abc','_direct_adapter':'lever','_direct_item_id':'123','_ats_board':'acme'},
        ])
        self.assertEqual(len(rows),1)
