from django.test import TestCase
from django.utils import timezone

from portal.models import CompanyLead, Contact, Opportunity
from portal.services.digest import build_24h_digest
from portal.templatetags.portal_extras import company_info_badge


class Release01096CompanyTooltipTests(TestCase):
    def test_company_age_badge_gets_supplemental_domain_lines(self):
        opp = Opportunity.objects.create(
            title='Network Engineer',
            company='Zero Networks',
            url='https://example.test/zero-networks-role',
            company_intel={
                'company': 'Zero Networks',
                'confidence': 91,
                'status': 'complete',
                'structured': {
                    'age_range': '10+ yr',
                    'size_range': '100–250',
                    'domain_age_domain': 'zeronetworks.com',
                    'domain_age_label': '7 yrs',
                },
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn('Company age: 10+ yr', tooltip)
        self.assertIn('Company size: 100–250 employees', tooltip)
        self.assertIn('Domain: zeronetworks.com', tooltip)
        self.assertIn('Domain created:', tooltip)
        self.assertIn('(7 years)', tooltip)

    def test_domain_age_badge_includes_consistent_domain_pair(self):
        opp = Opportunity.objects.create(
            title='Platform Engineer',
            company='Extra Hop',
            url='https://example.test/extrahop-role',
            company_intel={
                'company': 'Extra Hop',
                'status': 'complete',
                'structured': {
                    'size_range': '500–1,000',
                    'domain_age_domain': 'extrahop.com',
                    'domain_age_label': '19 yrs',
                },
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn('Company size: 500–1,000 employees', tooltip)
        self.assertIn('Domain: extrahop.com', tooltip)
        self.assertIn('Domain created:', tooltip)
        self.assertIn('(19 years)', tooltip)
        self.assertNotIn('Domain age (registration/RDAP):', tooltip)


class Release01096DigestTests(TestCase):
    def test_subject_uses_parentheses_for_counts(self):
        now = timezone.now()
        Opportunity.objects.create(title='One Role', company='Acme', url='https://acme.example/jobs/one')
        CompanyLead.objects.create(company='LeadCo')
        Contact.objects.create(email='person@example.com', name='Person', company='Example')
        digest = build_24h_digest(now=now, test=True)
        expected_date = timezone.localtime(now).strftime('%d %b %Y')
        self.assertEqual(
            digest['subject'],
            f'[{expected_date}] - Daily Digest (1 new opportunity, 1 new lead, 1 contact)',
        )
        self.assertNotIn('Daily Digest [1 new', digest['subject'])

    def test_operational_sections_use_real_multicolumn_tables(self):
        digest = build_24h_digest(now=timezone.now(), test=False)
        html = digest['html_body']
        self.assertGreaterEqual(html.count('class="stats-table"'), 3)
        self.assertIn('width="33%"', html)
        self.assertIn('24-hour activity', html)
        self.assertIn('Current settings', html)
        self.assertIn("Today&#x27;s cloud budget", html)
        self.assertNotIn('class="stats-grid"', html)
