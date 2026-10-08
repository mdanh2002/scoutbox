from django.core.management.base import BaseCommand
from portal.models import Campaign, PortalSettings
from portal.services.search import build_campaign_query_plan


class Command(BaseCommand):
    help='Preview the current Resume-first automatic query plan without running any search.'

    def add_arguments(self, parser):
        parser.add_argument('--campaign', default='Resume-first Automatic Discovery')
        parser.add_argument('--limit', type=int, default=12)

    def handle(self,*args,**opts):
        campaign=Campaign.objects.filter(name=opts['campaign'],deleted_at__isnull=True).first() or Campaign.objects.filter(enabled=True,deleted_at__isnull=True).first()
        if not campaign:
            self.stderr.write('No campaign exists. Run seed_defaults first.')
            return
        cfg=PortalSettings.objects.get_or_create(pk=1)[0]
        plan=build_campaign_query_plan(campaign,max_queries=max(1,min(opts['limit'],48)))
        sp=plan['search_profile']
        self.stdout.write(f'Campaign: {campaign.name}')
        self.stdout.write(f'Active CVs: {sp.get("cv_count",0)}')
        self.stdout.write('Top concepts: '+', '.join(x['term'] for x in sp.get('skills',[])[:15]))
        self.stdout.write(f'Configured location: {sp.get("operating_location") or "(none)"} — NOT inserted into queries')
        self.stdout.write('')
        for i,item in enumerate(plan['queries'],1):
            self.stdout.write(f'{i:02d}. [{item["kind"]}] {item["query"]}')
            self.stdout.write(f'    {item["rationale"]}')
