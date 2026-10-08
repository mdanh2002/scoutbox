from django.test import TestCase

from portal.models import Campaign, Contact, CompanyLead, Opportunity, PortalSettings
from portal.services.focus import _comparison_budget, _soft_group_cap
from portal.templatetags.portal_extras import post_age_provenance_tooltip


class Release010101FocusTests(TestCase):
    def test_general_focus_defaults_and_internal_tolerance(self):
        ps = PortalSettings.objects.get_or_create(pk=1)[0]
        self.assertEqual(ps.focus_comparison_records, 100)
        self.assertEqual(ps.max_focus_groups, 15)
        for seed in range(20):
            self.assertGreaterEqual(_comparison_budget(100, seed), 80)
            self.assertLessEqual(_comparison_budget(100, seed), 120)
        self.assertEqual(_soft_group_cap(15), 18)

    def test_actual_content_outweighs_technical_writing_campaign(self):
        campaign = Campaign.objects.create(name='Technical Writing')
        opp = Opportunity.objects.create(
            title='PIC32 Embedded Firmware Engineer',
            company='Acme Devices',
            url='https://example.test/jobs/pic32',
            description='Develop PIC32 MCU firmware, UART drivers, RTOS code and board bring-up.',
            origin_campaign=campaign,
        )
        opp.refresh_from_db()
        self.assertEqual(opp.focus, 'Embedded / Firmware')

    def test_representative_focus_examples(self):
        rows = [
            ('MS-DOS Compatibility Engineer', 'DOSBox x86 real mode and legacy peripheral support', 'Retro / Legacy Systems'),
            ('QEMU Virtualization Engineer', 'KVM hypervisor and emulator development', 'Virtualization / Emulation'),
            ('Technical Writer', 'Write API documentation and developer tutorials', 'Technical Writing'),
        ]
        for i, (title, description, expected) in enumerate(rows):
            opp = Opportunity.objects.create(title=title, company='Example', url=f'https://example.test/{i}', description=description)
            opp.refresh_from_db()
            self.assertEqual(opp.focus, expected)

    def test_all_three_list_models_receive_focus_on_create(self):
        lead = CompanyLead.objects.create(company='FirmwareCo', summary='Embedded STM32 firmware and RTOS products')
        contact = Contact.objects.create(email='writer@example.test', company='DocsCo', title='Technical Writer', company_summary='API documentation and tutorials')
        lead.refresh_from_db(); contact.refresh_from_db()
        self.assertEqual(lead.focus, 'Embedded / Firmware')
        self.assertEqual(contact.focus, 'Technical Writing')


class Release010101PostAgeTests(TestCase):
    def test_recent_post_age_is_less_than_one_week_and_uses_evidence_label(self):
        opp = Opportunity.objects.create(
            title='Engineer', company='Example', url='https://example.test/recent',
            freshness_label='~1 week',
            extracted_facts={'post_age': {'source':'Page content','post_age_reason':'Best available evidence: JobPosting schema: datePosted'}},
        )
        tooltip = post_age_provenance_tooltip(opp)
        self.assertIn('Post age: ~ 1 week', tooltip)
        self.assertIn('Evidence: JobPosting schema: datePosted', tooltip)
        self.assertNotIn('Reason:', tooltip)
