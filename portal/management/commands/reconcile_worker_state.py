from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.tasks import (
    _celery_worker_snapshot,
    _expire_stale_background_jobs,
    _expire_stale_queued_campaign_runs,
    _fail_stalled_campaign_runs,
    _interrupt_unowned_campaign_runs,
    _recover_campaign_runs_interrupted_by_restart,
    _requeue_interrupted_company_research,
    _stop_stale_campaign_runs,
)


class Command(BaseCommand):
    help = 'Reconcile stale CampaignRun/BackgroundJob rows with Celery worker state.'

    def handle(self, *args, **options):
        now=timezone.now()
        snapshot=_celery_worker_snapshot(timeout=1.2)
        restart_recovery=_recover_campaign_runs_interrupted_by_restart(now,snapshot=snapshot)
        campaign_owner=_interrupt_unowned_campaign_runs(now,startup=True,snapshot=snapshot)
        bg=_expire_stale_background_jobs(now,startup=True,snapshot=snapshot)
        bg['company_research_requeued_ids']=_requeue_interrupted_company_research(bg)
        queued=_expire_stale_queued_campaign_runs(now)
        stalled=_fail_stalled_campaign_runs(now)
        stopped=_stop_stale_campaign_runs(now)
        self.stdout.write(
            'Worker state reconciled: '
            f"restart interrupted={len(restart_recovery.get('interrupted_ids') or [])}, "
            f"restart replacements={len(restart_recovery.get('replacement_run_ids') or [])}, "
            f"campaign ownership={len(campaign_owner.get('interrupted_ids') or [])}, "
            f"background running={len(bg.get('running_failed_ids') or [])}, "
            f"background queued={len(bg.get('queued_failed_ids') or [])}, "
            f"campaign queued={len(queued.get('failed_ids') or [])}, "
            f"campaign stalled={len(stalled.get('failed_ids') or [])}, "
            f"campaign stopping={len(stopped or [])}."
        )
