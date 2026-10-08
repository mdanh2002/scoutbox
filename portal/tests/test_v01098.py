from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from portal.models import Opportunity
from portal.services.company_research import refresh_company_domain_registration
from portal.templatetags.portal_extras import company_info_badge


class _RDAPResponse:
    content = b'{}'
    def raise_for_status(self):
        return None
    def json(self):
        return {'events': [{'eventAction': 'registration', 'eventDate': '2016-01-15T00:00:00Z'}]}


class Release01098CompanyTooltipTests(TestCase):
    def test_building_badge_uses_stored_website_and_registration_date(self):
        opp = Opportunity.objects.create(
            title='Staff DevOps Engineer', company='Phantom', url='https://gulftalent.example/jobs/role',
            company_intel={
                'company': 'Phantom', 'confidence': 92, 'status': 'complete',
                'structured': {
                    'age_range': '10+ yr',
                    'website': 'https://www.phantom.com/',
                    'domain_registered_at': '2016-01-15',
                },
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn('Company: Phantom', tooltip)
        self.assertIn('Company age: 10+ yr', tooltip)
        self.assertIn('Domain: phantom.com', tooltip)
        self.assertIn('Domain created:', tooltip)

    def test_tooltip_can_use_official_matching_source_before_backfill(self):
        opp = Opportunity.objects.create(
            title='Analyst', company='Give Directly', url='https://example.test/jobs/role',
            company_intel={
                'company': 'Give Directly', 'confidence': 91, 'status': 'complete',
                'sources': [
                    {'title': 'GiveDirectly official website', 'url': 'https://www.givedirectly.org/about/'},
                    {'title': 'Job board', 'url': 'https://www.linkedin.com/jobs/view/123'},
                ],
                'structured': {'age_range': '10+ yr', 'size_range': '100-250'},
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn('Domain: givedirectly.org', tooltip)
        self.assertNotIn('linkedin.com', tooltip)

    @patch('portal.services.company_research.requests.get', return_value=_RDAPResponse())
    @patch('portal.services.company_research.search_source')
    @patch('portal.services.company_research._providers')
    def test_domain_maintenance_discovers_official_domain_without_ai(self, providers, search, _rdap):
        providers.return_value = [SimpleNamespace(name='SearchProvider')]
        search.return_value = ([
            {'title': 'Phantom - Official Website', 'url': 'https://phantom.com/', 'snippet': 'Phantom official site'},
            {'title': 'Phantom jobs', 'url': 'https://jobs.lever.co/phantom', 'snippet': ''},
        ], '')
        opp = Opportunity.objects.create(
            title='Staff DevOps Engineer', company='Phantom', url='https://gulftalent.example/jobs/role',
            company_intel={
                'company': 'Phantom', 'confidence': 92, 'status': 'complete',
                'structured': {'age_range': '10+ yr', 'domain_age_refresh_needed': True},
            },
        )
        result = refresh_company_domain_registration(opp)
        opp.refresh_from_db()
        structured = opp.company_intel['structured']
        self.assertEqual(result['domain'], 'phantom.com')
        self.assertEqual(structured['domain_age_domain'], 'phantom.com')
        self.assertTrue(structured.get('domain_age_label'))
        tooltip = str(company_info_badge(opp))
        self.assertIn('Domain: phantom.com', tooltip)
        self.assertIn('Domain created:', tooltip)
