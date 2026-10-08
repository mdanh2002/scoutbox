from django.test import TestCase
from django.utils import timezone

from portal.models import Opportunity
from portal.templatetags.portal_extras import (
    company_info_badge,
    post_age_provenance_tooltip,
    remote_signal,
)


class Release01099CompanyInfoTests(TestCase):
    def test_building_badge_shows_crisp_globe_and_domain_creation_year(self):
        opp = Opportunity.objects.create(
            title='Staff Engineer', company='Phantom', url='https://example.test/phantom-role',
            company_intel={
                'company': 'Phantom', 'confidence': 96, 'status': 'complete',
                'structured': {
                    'age_range': '10+ yr', 'size_range': '100-250',
                    'domain_age_domain': 'phantom.com',
                    'domain_registered_at': '1997-04-15',
                    'domain_age_years': 29,
                    'domain_age_label': '29 yrs',
                },
            },
        )
        badge = str(company_info_badge(opp))
        self.assertIn('company-domain-year-mini-globe', badge)
        self.assertIn('shape-rendering="geometricPrecision"', badge)
        self.assertIn('>1997</span>', badge)
        self.assertIn('Domain: phantom.com', badge)
        self.assertIn('Domain created: 1997 (', badge)
        self.assertNotIn('Domain age:', badge)

    def test_domain_only_globe_shows_creation_year_not_year_count(self):
        years = 14
        expected_year = timezone.localdate().year - years
        opp = Opportunity.objects.create(
            title='Engineer', company='ExampleCo', url='https://example.test/role',
            company_intel={
                'company': 'ExampleCo', 'confidence': 80, 'status': 'complete',
                'structured': {
                    'domain_age_domain': 'exampleco.com',
                    'domain_age_years': years,
                    'domain_age_label': f'{years} yrs',
                },
            },
        )
        badge = str(company_info_badge(opp))
        self.assertIn('company-domain-age-icon', badge)
        self.assertIn(f'>{expected_year}</span>', badge)
        self.assertNotIn(f'>{years} yrs</span>', badge)
        self.assertIn(f'Domain created: {expected_year} ({years} years)', badge)


class Release01099TooltipTests(TestCase):
    def test_remote_tooltip_is_multiline_company_info_style(self):
        opp = Opportunity.objects.create(
            title='Remote Engineer', company='Acme', url='https://acme.example/jobs/one',
            extracted_facts={
                'remote_classification': {
                    'status': 'remote',
                    'label': 'Remote within Canada and the United States',
                    'confidence': 91,
                    'reason': 'Role explicitly permits remote work in these countries.',
                }
            },
        )
        html = str(remote_signal(opp))
        self.assertIn('scout-multiline-tooltip', html)
        self.assertIn('data-tooltip="Remote: Remote within Canada and the United States\nConfidence: 91%\nReason:', html)
        self.assertNotIn(' · ', html)

    def test_post_age_tooltip_uses_multiline_surface_and_concise_evidence(self):
        opp = Opportunity.objects.create(
            title='Recent Engineer', company='Acme', url='https://acme.example/jobs/two',
            freshness_confidence=70,
            freshness_label='~1 week',
            extracted_facts={
                'post_age': {
                    'post_age_method': 'structured',
                    'post_age_reason': 'Best available evidence: JobPosting schema: datePosted',
                    'source': 'Page content',
                }
            },
        )
        tooltip = post_age_provenance_tooltip(opp)
        self.assertIn('Post age: ~ 1 week', tooltip)
        self.assertIn('\nSource: Page content', tooltip)
        self.assertIn('\nEvidence: JobPosting schema: datePosted', tooltip)
        self.assertNotIn('\nReason:', tooltip)
        self.assertNotIn(' · ', tooltip)
