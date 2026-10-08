from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from portal.services.cold import _hidden_page_is_job_like, _salvage_rejection_eligible, _hidden_lead_score
from portal.services.fresh_sources import forum_source_rows
from portal.services.mailbox import _company_focused_summary_from_record


class Release01093HiddenLeadLogicTests(SimpleTestCase):
    def test_company_page_with_careers_navigation_is_not_a_job_page(self):
        text = 'Acme builds embedded SDR products for industrial customers. About us Products Careers Contact.'
        self.assertFalse(_hidden_page_is_job_like('https://acme.example/products/radio', 'SDR Radio', text))

    def test_actual_vacancy_page_is_job_like(self):
        self.assertTrue(_hidden_page_is_job_like(
            'https://acme.example/careers/firmware-engineer', 'Firmware Engineer',
            'Job description Responsibilities Qualifications Apply now',
        ))

    def test_vacancy_level_rejection_can_be_salvaged_but_blacklist_cannot(self):
        self.assertTrue(_salvage_rejection_eligible('Role is no longer available outside Europe because equipment shipping is difficult.'))
        self.assertFalse(_salvage_rejection_eligible('Blocked by blacklist: example.com'))
        self.assertFalse(_salvage_rejection_eligible('Recruitment agency / job board result'))

    def test_hidden_lead_score_records_separate_dimensions(self):
        score, parts = _hidden_lead_score(
            'Acme', 'Acme builds embedded linux firmware and software defined radio products for customers.',
            ['embedded Linux', 'firmware'], ['building', 'firmware'], organization_confidence=85,
            contactable=True, provenance='discovered_company',
        )
        self.assertGreaterEqual(score, 50)
        for key in ('technical_relevance','company_confidence','contactability','uniqueness','commercial_plausibility','provenance_type'):
            self.assertIn(key, parts)

    def test_address_book_summary_uses_company_focused_opportunity_evidence(self):
        record = SimpleNamespace(
            company='Acme Devices', company_intel={}, contact_email='', target_url='https://acme.example',
            raw_search_snippet='Acme Devices builds embedded radio products and firmware for industrial customers.',
            recommendation_reason='', list_highlight='Senior firmware engineer role.', description='',
        )
        summary = _company_focused_summary_from_record(record)
        self.assertIn('embedded radio products', summary)


class Release01093ForumFailoverTests(SimpleTestCase):
    @mock.patch('portal.services.fresh_sources.direct_source_rows')
    def test_forum_helper_clamps_failover_to_three_sources(self, direct):
        direct.return_value = ([], [], {})
        forum_source_rows(SimpleNamespace(), max_sources=99, stage_budget_seconds=99)
        self.assertEqual(direct.call_args.kwargs['max_sources'], 3)
        self.assertLessEqual(direct.call_args.kwargs['stage_budget_seconds'], 25)
