from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from portal.models import Opportunity
from portal.services.platforms import is_plausible_company_name
from portal.services.role_gate import classify_role_page
from portal.templatetags.portal_extras import company_info_badge


class Release01094OpportunityIntegrityTests(SimpleTestCase):
    def test_serialized_github_gist_job_dataset_is_hard_rejected(self):
        result = classify_role_page(
            'https://gist.github.com/example/deadbeef',
            'txt 1 {:crawled true, :title Java Software Engineer, :description The Software Engineer will evaluate...',
            '{:crawled true :title "Java Software Engineer" :description "job data"} '
            '{:crawled true :title "Another Role" :description "more harvested data"}',
        )
        self.assertFalse(result['accepted'])
        self.assertTrue(result.get('hard_reject'))
        self.assertIn('Gist', result['reason'])

    def test_sentence_fragment_is_not_a_company_identity(self):
        self.assertFalse(is_plausible_company_name('collaborative security culture. About the Role OpenAI'))
        self.assertTrue(is_plausible_company_name('OpenAI'))


class Release01094CompanyInfoTooltipTests(SimpleTestCase):
    def test_resolved_company_badge_keeps_icon_and_adds_domain_tooltip_lines(self):
        row = SimpleNamespace(
            company='Mirantis',
            company_intel={
                'confidence': 90,
                'structured': {
                    'age_range': '10+ yr',
                    'size_range': '500-1,000',
                    'domain_age_domain': 'mirantis.com',
                    'domain_age_years': 15,
                },
            },
            ai_state={},
        )
        html = str(company_info_badge(row))
        self.assertIn('company-info-stage', html)
        self.assertIn('Domain: mirantis.com', html)
        self.assertIn('Domain created:', html)
        self.assertIn('(15 years)', html)
        self.assertNotIn('Domain: mirantis.com</span>', html)


class Release01094VisibleListSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='release-01094', password='test-password')
        self.client.force_login(self.user)

    def test_opportunity_search_does_not_match_hidden_description(self):
        hidden = Opportunity.objects.create(
            title='Firmware Engineer',
            company='Visible Fields Ltd',
            url='https://visible-fields.example/jobs/firmware',
            description='This hidden full description mentions technical writing repeatedly.',
            list_highlight='Embedded firmware development for industrial devices.',
        )
        visible = Opportunity.objects.create(
            title='Technical Writing Engineer',
            company='Documentation Systems',
            url='https://docs-systems.example/jobs/writer',
            description='Unrelated hidden description.',
            list_highlight='Developer documentation and engineering enablement.',
        )

        response = self.client.get(reverse('opportunities'), {'q': 'technical writing'})

        self.assertEqual(response.status_code, 200)
        rows = list(response.context['opportunities'])
        self.assertIn(visible, rows)
        self.assertNotIn(hidden, rows)
