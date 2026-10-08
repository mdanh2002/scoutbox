from django.test import TestCase

from portal.models import CompanyResearchCache, Opportunity
from portal.services.company_research import company_domain_for_entity, refresh_company_domain_registration
from portal.templatetags.portal_extras import company_info_badge


class Release010100CompanyDomainDisplayTests(TestCase):
    def test_legacy_domain_age_fact_is_rendered_on_building_badge(self):
        opp=Opportunity.objects.create(
            title='Support Engineer', company='Extra Hop', url='https://jobicy.example/role',
            company_intel={
                'company':'Extra Hop','confidence':91,'status':'complete',
                'structured':{'age_range':'10+ yr','size_range':'20-50','company_domain':'extra.com'},
                'facts':[
                    {'label':'Company','value':'ExtraHop Networks, Inc.','verification':'verified'},
                    {'label':'Domain Age','value':'19 yrs (extrahop.com; registered 2006-12-11)','verification':'domain-registration'},
                ],
            },
        )
        badge=str(company_info_badge(opp))
        self.assertIn('company-domain-year-mini-globe',badge)
        self.assertIn('>2006</span>',badge)
        self.assertIn('Domain: extrahop.com',badge)
        self.assertIn('Domain created: 2006 (',badge)
        self.assertNotIn('Domain: extra.com',badge)

    def test_spacing_variant_reuses_cached_official_domain_and_registration_date(self):
        CompanyResearchCache.objects.create(
            domain='extrahop.com', company='ExtraHop',
            data={'company':'ExtraHop','structured':{
                'domain_age_domain':'extrahop.com','domain_registered_at':'2006-12-11',
                'domain_age_years':19,'domain_age_label':'19 yrs',
            }},
        )
        opp=Opportunity.objects.create(
            title='Support Engineer',company='Extra Hop',url='https://jobicy.example/role-two',
            company_intel={'company':'Extra Hop','confidence':90,'status':'complete',
                           'structured':{'age_range':'10+ yr','size_range':'20-50','company_domain':'extra.com','domain_age_refresh_needed':True}},
        )
        self.assertEqual(company_domain_for_entity(opp,opp.company_intel),'extrahop.com')
        status=refresh_company_domain_registration(opp)
        self.assertEqual(status.get('domain'),'extrahop.com')
        opp.refresh_from_db()
        st=opp.company_intel.get('structured') or {}
        self.assertEqual(st.get('domain_age_domain'),'extrahop.com')
        self.assertEqual(st.get('domain_registered_at'),'2006-12-11')
        badge=str(company_info_badge(opp))
        self.assertIn('>2006</span>',badge)
        self.assertIn('Domain created: 2006 (',badge)

    def test_partial_compound_brand_domain_is_not_accepted(self):
        opp=Opportunity.objects.create(
            title='Engineer',company='Extra Hop',url='https://jobicy.example/role-three',
            company_intel={'company':'Extra Hop','structured':{'company_domain':'extra.com'}},
        )
        self.assertNotEqual(company_domain_for_entity(opp,opp.company_intel),'extra.com')
