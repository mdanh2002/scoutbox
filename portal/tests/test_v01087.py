from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from portal.models import Campaign, Opportunity


class Release01087OpportunityFacetRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='release-01087', password='test-password')
        self.client.force_login(self.user)

    def test_opportunity_status_facets_count_rows_not_distinct_ordered_groups(self):
        campaign = Campaign.objects.create(name='Status Count Campaign')
        rediscovery = Campaign.objects.create(name='Status Count Rediscovery')
        rows = [
            ('New Role 1', 'new'),
            ('New Role 2', 'new'),
            ('New Role 3', 'new'),
            ('Apply Role 1', 'apply'),
            ('Apply Role 2', 'apply'),
            ('Review Role 1', 'review'),
        ]
        for index, (title, status) in enumerate(rows, start=1):
            opportunity = Opportunity.objects.create(
                title=title,
                company=f'Facet Company {index}',
                country='United States',
                url=f'https://example.test/jobs/status-facet-{index}',
                origin_campaign=campaign,
                status=status,
            )
            # Exercise the same many-to-many campaign join that requires distinct() in
            # the list view.  The status facet must still aggregate by status only.
            opportunity.campaigns.add(campaign, rediscovery)

        response = self.client.get(reverse('opportunities'), {'campaign': campaign.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All statuses (6)')
        self.assertContains(response, 'New (3)')
        self.assertContains(response, 'Apply Now (2)')
        self.assertContains(response, 'Review (1)')
