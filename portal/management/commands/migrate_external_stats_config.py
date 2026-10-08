from django.core.management.base import BaseCommand
from portal.models import BlogStatsConfig
from portal.services.blogstats import migrate_legacy_config, RUNTIME_PATH

class Command(BaseCommand):
    help='Migrate legacy embedded external-statistics credentials to the sidecar runtime secret file.'
    def handle(self,*args,**opts):
        cfg=BlogStatsConfig.objects.get_or_create(pk=1,defaults={'enabled':True})[0]
        migrate_legacy_config(cfg)
        self.stdout.write(self.style.SUCCESS(f'External statistics runtime configuration ready at {RUNTIME_PATH}.'))
