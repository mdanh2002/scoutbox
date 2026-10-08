from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from portal.models import AuditLog


class Command(BaseCommand):
    help='Record one web-service lifecycle event in the ScoutBox audit trail.'

    def add_arguments(self, parser):
        parser.add_argument('event', choices=('started','stopped'))

    def handle(self, *args, **options):
        event=options['event']
        version=str(getattr(settings,'PORTAL_VERSION','') or '')[:32]
        if event=='started':
            last_start=AuditLog.objects.filter(action='service_started').order_by('-at').first()
            last_stop=AuditLog.objects.filter(action='service_stopped').order_by('-at').first()
            if last_start and (not last_stop or last_stop.at < last_start.at):
                AuditLog.objects.create(
                    actor='system',action='service_interrupted',version=version,
                    summary='The previous ScoutBox web service session ended without a graceful stop.',
                    metadata={'previous_start_at':last_start.at.isoformat()},
                )
            AuditLog.objects.create(actor='system',action='service_started',version=version,summary='ScoutBox web service started.')
        elif event=='stopped':
            AuditLog.objects.create(actor='system',action='service_stopped',version=version,summary='ScoutBox web service stopped gracefully.')
        else:
            raise CommandError('Unsupported lifecycle event')
