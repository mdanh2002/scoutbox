from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.focus import _candidate_phrases
from portal.services.freshness import opportunity_post_age_display_label, post_age_label_for_days
from portal.services.location_values import record_location_display


class CompanyLead:
    pk=1
    focus=''
    origin_campaign=None
    def __init__(self):
        self.company='Acme Security'
        self.summary='Acme sells a cybersecurity platform for SOC teams and incident response workflows.'
        self.match_summary='Cybersecurity services and threat detection platform.'
        self.evidence='Incident response, SIEM, and threat hunting are described as company offerings.'
        self.company_intel={}


class Contact:
    pk=1
    focus=''
    def __init__(self):
        self.company='Acme Security'
        self.title='Founder'
        self.company_summary='Cybersecurity services for SOC teams and incident response.'
        self.notes=''
        self.company_intel={}


class Release010113Tests(SimpleTestCase):
    def test_post_age_newest_bucket_is_less_than_three_days(self):
        self.assertEqual(post_age_label_for_days(0),'< 3 days')
        self.assertEqual(post_age_label_for_days(2),'< 3 days')
        self.assertEqual(post_age_label_for_days(3),'< 1 week')

    def test_company_focus_does_not_reuse_opportunity_incident_response_label(self):
        labels=[x[0] for x in _candidate_phrases(CompanyLead())]
        self.assertIn('Cybersecurity Services', labels)
        self.assertNotIn('Security Incident Response', labels)

    def test_address_book_focus_uses_company_domain_label(self):
        labels=[x[0] for x in _candidate_phrases(Contact())]
        self.assertIn('Cybersecurity Services', labels)
        self.assertNotIn('Security Incident Response', labels)

    def test_worldwide_not_displayed_as_company_location(self):
        row=SimpleNamespace(country='Worldwide')
        self.assertEqual(record_location_display(row),'')
    def test_evergreen_metadata_stays_visible_post_age_value(self):
        from django.utils import timezone
        row=SimpleNamespace(
            freshness_label='< 3 days', freshness_confidence=82,
            declared_posted_at=timezone.now(), estimated_first_seen=None,
            extracted_facts={'post_age':{'post_age_class':'evergreen','evergreen':True,'evergreen_confidence':82,'age_days':0}},
        )
        self.assertEqual(opportunity_post_age_display_label(row),'Evergreen')

