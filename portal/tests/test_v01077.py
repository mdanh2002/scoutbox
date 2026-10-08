from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from portal.models import Application, AuditLog, Campaign, CompanyLead, Contact, Opportunity
from portal.services.mailbox import maybe_persist_addressbook_contact


class Release01077ListRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='release-test', password='test-password')
        self.client.force_login(self.user)

    def test_opportunities_page_handles_campaign_facet_queryset(self):
        campaign = Campaign.objects.create(name='A campaign name long enough to exercise the dropdown item count')
        opportunity = Opportunity.objects.create(
            title='Embedded Engineer', company='Example Devices', country='United States',
            url='https://example.test/jobs/embedded-engineer', origin_campaign=campaign,
        )
        opportunity.campaigns.add(campaign)

        response = self.client.get(reverse('opportunities'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All campaigns (1)')
        self.assertContains(response, f'{campaign.name} (1)')

    def test_opportunity_facets_do_not_double_count_campaign_join_rows(self):
        campaign = Campaign.objects.create(name='Primary Campaign')
        rediscovery = Campaign.objects.create(name='Rediscovery Campaign')
        opportunity = Opportunity.objects.create(
            title='Firmware Engineer', company='Facet Co', country='United States',
            url='https://example.test/facet', origin_campaign=campaign, status='new',
        )
        opportunity.campaigns.add(campaign, rediscovery)

        response = self.client.get(reverse('opportunities'), {'campaign': campaign.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All countries (1)')
        self.assertContains(response, 'United States (1)')
        self.assertContains(response, 'All statuses (1)')
        self.assertContains(response, 'New (1)')

    def test_country_totals_only_count_visible_country_options(self):
        # Opportunities
        Opportunity.objects.create(title='US role', company='US Co', country='United States', url='https://example.test/us')
        Opportunity.objects.create(title='DE role', company='DE Co', country='Germany', url='https://example.test/de')
        Opportunity.objects.create(title='Unknown role', company='Unknown Co', country='Not specified', url='https://example.test/unknown')
        response = self.client.get(reverse('opportunities'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All countries (2)')

        # Applications
        app_opp_1 = Opportunity.objects.create(title='Applied US', company='Applied US Co', country='United States', url='https://example.test/app-us')
        app_opp_2 = Opportunity.objects.create(title='Applied unknown', company='Applied Unknown Co', country='', url='https://example.test/app-unknown')
        Application.objects.create(opportunity=app_opp_1)
        Application.objects.create(opportunity=app_opp_2)
        response = self.client.get(reverse('applications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All countries (1)')

        # Address Book
        Contact.objects.create(email='us@example.test', name='US Contact', company='US Contact Co', company_country='United States', source='manual')
        Contact.objects.create(email='de@example.test', name='DE Contact', company='DE Contact Co', company_country='Germany', source='manual')
        Contact.objects.create(email='unknown@example.test', name='Unknown Contact', company='Unknown Contact Co', company_country='Unknown / Others', source='manual')
        response = self.client.get(reverse('contacts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All countries (2)')

    def test_hidden_lead_country_counts_use_visible_company_deduplication(self):
        CompanyLead.objects.create(company='Duplicate Labs', country='United States')
        CompanyLead.objects.create(company='Duplicate Labs', country='United States')
        CompanyLead.objects.create(company='Unique GmbH', country='Germany')
        CompanyLead.objects.create(company='Unknown Ltd', country='Unknown / Others')

        response = self.client.get(reverse('cold_contact'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All countries (2)')
        self.assertContains(response, 'United States (1)')
        self.assertContains(response, 'Germany (1)')


class Release01077AddressBookAuditTests(TestCase):
    def test_promotion_provenance_replaces_audit_noise(self):
        patches = (
            patch('portal.services.mailbox._stored_company_context', return_value=('', {})),
            patch('portal.services.mailbox.assess_addressbook_contact_fit', return_value=(False, {})),
            patch('portal.services.mailbox.enrich_company_intel_from_retained', return_value={}),
        )
        with patches[0], patches[1], patches[2]:
            contact, created, outcome = maybe_persist_addressbook_contact(
                'jane@example.test', name='Jane', company='Example', source='Automatic discovery',
                source_url='https://example.test/team', require_company_match=False,
            )
            self.assertTrue(created)
            self.assertEqual(outcome, 'created')
            self.assertEqual(AuditLog.objects.filter(action='addressbook_promotion').count(), 0)

            _, created, outcome = maybe_persist_addressbook_contact(
                'jane@example.test', name='Jane', company='Example', source='Automatic discovery',
                source_url='https://example.test/team', require_company_match=False,
            )
            self.assertFalse(created)
            self.assertEqual(outcome, 'unchanged')
            self.assertEqual(AuditLog.objects.filter(action='addressbook_promotion').count(), 0)

            _, created, outcome = maybe_persist_addressbook_contact(
                'jane@example.test', name='Jane Example', company='Example', source='Automatic discovery',
                source_url='https://example.test/team', require_company_match=False,
            )
            self.assertFalse(created)
            self.assertEqual(outcome, 'updated')
            self.assertEqual(AuditLog.objects.filter(action='addressbook_promotion').count(), 0)

            _, created, outcome = maybe_persist_addressbook_contact(
                'not-an-email', company='Example', source='Automatic discovery', require_company_match=False,
            )
            self.assertFalse(created)
            self.assertEqual(outcome, 'generic_or_invalid')
            self.assertEqual(AuditLog.objects.filter(action='addressbook_promotion').count(), 0)

        contact.refresh_from_db()
        self.assertEqual(contact.name, 'Jane Example')
        self.assertEqual(contact.origin_provenance.get('source'), 'Automatic discovery')
        self.assertEqual(contact.origin_provenance.get('source_url'), 'https://example.test/team')

    def test_cleanup_migration_removes_historical_promotion_rows_only(self):
        import importlib
        from django.apps import apps

        AuditLog.objects.create(action='addressbook_promotion', summary='legacy promotion noise')
        AuditLog.objects.create(action='chatbot.ask', summary='keep me')
        migration = importlib.import_module('portal.migrations.0107_v01077_addressbook_audit_cleanup')
        migration.remove_addressbook_promotion_history(apps, None)

        self.assertFalse(AuditLog.objects.filter(action='addressbook_promotion').exists())
        self.assertTrue(AuditLog.objects.filter(action='chatbot.ask').exists())
