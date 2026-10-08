from django.test import TestCase

from portal.models import Opportunity
from portal.templatetags.portal_extras import company_info_badge


class Release01097CompanyTooltipTests(TestCase):
    def test_company_age_icon_has_consistent_available_facts(self):
        opp = Opportunity.objects.create(
            title="Engineer", company="GiveDirectly", url="https://example.test/gd",
            company_intel={
                "company":"GiveDirectly", "confidence":91, "status":"complete",
                "structured":{
                    "age_range":"10+ yr", "size_range":"100-250",
                    "domain_age_domain":"givedirectly.org", "domain_age_label":"14 yrs",
                },
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn("Company: GiveDirectly", tooltip)
        self.assertIn("Company age: 10+ yr", tooltip)
        self.assertIn("Company size: 100–250 employees", tooltip)
        self.assertIn("Domain: givedirectly.org", tooltip)
        self.assertIn("Domain created:", tooltip)
        self.assertIn("(14 years)", tooltip)

    def test_domain_icon_uses_same_tooltip_field_names(self):
        opp = Opportunity.objects.create(
            title="Engineer", company="Zapier", url="https://example.test/zapier",
            company_intel={
                "company":"Zapier", "confidence":86, "status":"complete",
                "structured":{
                    "size_range":"500-1000",
                    "domain_age_domain":"zapier.com", "domain_age_label":"14 yrs",
                },
            },
        )
        tooltip = str(company_info_badge(opp))
        self.assertIn("Company: Zapier", tooltip)
        self.assertIn("Company size: 500–1,000 employees", tooltip)
        self.assertIn("Domain: zapier.com", tooltip)
        self.assertIn("Domain created:", tooltip)
        self.assertIn("(14 years)", tooltip)
        self.assertNotIn("Domain age (registration/RDAP):", tooltip)
