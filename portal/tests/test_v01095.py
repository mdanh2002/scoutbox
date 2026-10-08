from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from portal.models import CompanyLead, CompanyResearchCache, Contact, Opportunity, ResourceSample
from portal.services.ai_lifecycle import usable_result
from portal.services.company_research import refresh_company_domain_registration
from portal.services.digest import build_24h_digest
from portal.templatetags.portal_extras import company_info_badge
from portal.views import _resource_sample_rows


class _RDAPResponse:
    status_code = 200
    content = b'{}'
    def raise_for_status(self):
        return None
    def json(self):
        return {'events': [{'eventAction': 'registration', 'eventDate': '2011-03-01T00:00:00Z'}]}


class Release01095CompanyDomainTests(TestCase):
    @patch('portal.services.company_research.requests.get', return_value=_RDAPResponse())
    def test_complete_company_profile_gets_domain_without_another_ai_pass(self, _get):
        opp = Opportunity.objects.create(
            title='Platform Engineer', company='Mirantis', url='https://jobs.lever.co/mirantis/role',
            company_intel={
                'company': 'Mirantis', 'status': 'complete',
                'facts': [{'label': 'Founded', 'value': '1999'}],
                'structured': {
                    'age_range': '10+ yr', 'size_range': '500-1,000',
                    'website': 'https://www.mirantis.com/', 'domain_age_refresh_needed': True,
                },
            },
            ai_state={'company': {'initial': 'success'}},
        )
        # The deterministic maintenance marker must not make this complete profile ask AI again.
        self.assertTrue(usable_result(opp, 'company'))

        result = refresh_company_domain_registration(opp)
        opp.refresh_from_db()
        structured = opp.company_intel['structured']
        self.assertEqual(result['domain'], 'mirantis.com')
        self.assertEqual(structured['domain_age_domain'], 'mirantis.com')
        self.assertIn('domain_registered_at', structured)
        self.assertFalse(structured.get('domain_age_refresh_needed', False))
        tooltip = str(company_info_badge(opp))
        self.assertIn('Domain: mirantis.com', tooltip)
        self.assertIn('Domain created:', tooltip)
        self.assertNotIn('lever.co', tooltip)

    @patch('portal.services.company_research.requests.get', return_value=_RDAPResponse())
    def test_aggregator_only_sibling_reuses_verified_company_domain_cache(self, _get):
        CompanyResearchCache.objects.create(
            domain='mirantis.com', company='Mirantis', provider='gemini', model='cached',
            data={'company':'Mirantis','status':'complete','facts':[{'label':'Founded','value':'1999'}],
                  'structured':{'domain_age_domain':'mirantis.com','domain_registered_at':'2000-05-02',
                                'domain_age_years':26,'domain_age_label':'26 yrs'}},
        )
        opp=Opportunity.objects.create(
            title='Rust Engineer', company='Mirantis',
            url='https://himalayas.app/companies/mirantis/jobs/rust-engineer',
            company_intel={'company':'Mirantis','status':'complete','facts':[{'label':'Founded','value':'1999'}],
                           'sources':[{'url':'https://himalayas.app/companies/mirantis/jobs/rust-engineer'}],
                           'structured':{'age_range':'10+ yr','size_range':'500-1,000','domain_age_refresh_needed':True}},
        )
        result=refresh_company_domain_registration(opp)
        opp.refresh_from_db()
        self.assertEqual(result['domain'],'mirantis.com')
        self.assertEqual(opp.company_intel['structured']['domain_age_domain'],'mirantis.com')
        self.assertEqual(opp.company_intel['structured']['domain_age_label'],'26 yrs')
        self.assertIn('Domain: mirantis.com',str(company_info_badge(opp)))


class Release01095ResourceUsageTests(TestCase):
    def test_seven_and_thirty_day_ranges_return_intraday_points(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        # One sample every six hours for 30 days is enough to exercise the long-range SQL path.
        ResourceSample.objects.bulk_create([
            ResourceSample(
                at=now-timedelta(hours=6*i), cpu_percent=float(i % 100),
                memory_percent=40.0 + (i % 20), memory_used_mb=4000,
                memory_total_mb=8000, disk_used_mb=10000, disk_total_mb=20000,
                gpu_percent=float((i*3) % 100), gpu_memory_percent=25.0,
                gpu_vram_used_mb=1000, gpu_vram_total_mb=8000, gpu_label='Test GPU',
            ) for i in range(121)
        ])
        for days in (7, 30):
            start = now-timedelta(days=days)
            qs = ResourceSample.objects.filter(at__gte=start, at__lte=now)
            rows = _resource_sample_rows(qs, start, now, max_points=240)
            self.assertGreater(len(rows), 1)
            self.assertIn('at', rows[0])
            self.assertIn('cpu_min', rows[0])
            self.assertIn('cpu_max', rows[0])


class Release01095DigestSubjectTests(TestCase):
    def test_scheduled_and_manual_digest_share_dated_count_subject_without_test_marker(self):
        now = timezone.now()
        Opportunity.objects.create(title='One Role', company='Acme', url='https://acme.example/jobs/one')
        CompanyLead.objects.create(company='LeadCo')
        Contact.objects.create(email='person@example.com', name='Person', company='Example')

        scheduled = build_24h_digest(now=now, test=False)
        manual = build_24h_digest(now=now, test=True)
        expected_date = timezone.localtime(now).strftime('%d %b %Y')
        expected = f'[{expected_date}] - Daily Digest (1 new opportunity, 1 new lead, 1 contact)'
        self.assertEqual(scheduled['subject'], expected)
        self.assertEqual(manual['subject'], expected)
        self.assertNotIn('TEST', scheduled['subject'].upper())
        self.assertNotIn('24-hour digest', scheduled['subject'])
