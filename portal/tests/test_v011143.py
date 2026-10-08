from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from portal.models import AuditLog, BackgroundJob, Campaign, CampaignRun
from portal.tasks import (
    _activity_predates_restart,
    _expire_stale_background_jobs,
    _primary_coverage_runs,
    _recover_campaign_runs_interrupted_by_restart,
)


class RestartRecoveryTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.stop_at = self.now - timezone.timedelta(seconds=20)
        AuditLog.objects.create(
            at=self.now - timezone.timedelta(minutes=5),
            actor='system', action='service_started', summary='Old service start',
        )
        AuditLog.objects.create(
            at=self.stop_at,
            actor='system', action='service_stopped', summary='ScoutBox web service stopped gracefully.',
        )
        self.campaign = Campaign.objects.create(name='Restart recovery campaign', enabled=True)

    def _snapshot(self, available=False):
        return {'known_ids': set(), 'workers': {'worker@live'} if available else set(), 'states': {}, 'available': available}

    def test_activity_boundary_accepts_old_worker_heartbeat(self):
        self.assertTrue(_activity_predates_restart(self.stop_at - timezone.timedelta(seconds=1), self.stop_at))
        self.assertTrue(_activity_predates_restart(self.stop_at + timezone.timedelta(seconds=20), self.stop_at))
        self.assertFalse(_activity_predates_restart(self.stop_at + timezone.timedelta(seconds=60), self.stop_at))

    @patch('portal.tasks._campaign_partial_discovery_result', return_value={})
    @patch('portal.tasks._clear_restart_local_ai_lanes', return_value={'deleted': 2, 'error': ''})
    @patch('portal.tasks.run_campaign_job.delay', return_value=SimpleNamespace(id='replacement-task'))
    def test_full_restart_stops_old_run_and_queues_equivalent_replacement(self, delay, clear_lanes, partial):
        run = CampaignRun.objects.create(
            campaign=self.campaign,
            status='running',
            celery_task_id='old-task',
            progress=89,
            message='Waiting for local AI lane · first filter · 40s',
            stage='Waiting for local AI',
            started_at=self.stop_at - timezone.timedelta(minutes=10),
            heartbeat_at=self.stop_at - timezone.timedelta(seconds=2),
            criteria={'automatic': True, 'forum_only': False, 'run_kind': 'primary', 'window_attempt': 3},
        )

        result = _recover_campaign_runs_interrupted_by_restart(self.now, snapshot=self._snapshot(False))

        run.refresh_from_db()
        self.assertEqual(run.status, 'stopped')
        self.assertTrue(run.criteria['coverage_exempt'])
        self.assertTrue(run.criteria['interrupted_by_restart'])
        self.assertEqual(result['interrupted_ids'], [run.pk])
        self.assertEqual(result['local_ai_locks_cleared'], 2)
        self.assertEqual(len(result['replacement_run_ids']), 1)

        replacement = CampaignRun.objects.get(pk=result['replacement_run_ids'][0])
        self.assertEqual(replacement.status, 'queued')
        self.assertEqual(replacement.celery_task_id, 'replacement-task')
        self.assertTrue(replacement.criteria['restart_recovery'])
        self.assertEqual(replacement.criteria['restart_recovery_of_run_id'], run.pk)
        self.assertEqual(replacement.criteria['window_attempt'], 3)
        self.assertEqual([r.pk for r in _primary_coverage_runs([run, replacement])], [replacement.pk])
        delay.assert_called_once_with(replacement.pk)
        clear_lanes.assert_called_once()

    @patch('portal.tasks.run_campaign_job.delay')
    def test_live_workers_prevent_restart_takeover(self, delay):
        run = CampaignRun.objects.create(
            campaign=self.campaign,
            status='running',
            celery_task_id='still-live',
            started_at=self.stop_at - timezone.timedelta(minutes=3),
            heartbeat_at=self.stop_at - timezone.timedelta(seconds=1),
            criteria={'forum_only': False, 'run_kind': 'primary'},
        )
        result = _recover_campaign_runs_interrupted_by_restart(self.now, snapshot=self._snapshot(True))
        run.refresh_from_db()
        self.assertEqual(run.status, 'running')
        self.assertEqual(result['interrupted_ids'], [])
        delay.assert_not_called()

    def test_running_background_job_is_finalized_immediately_at_restart_boundary(self):
        job = BackgroundJob.objects.create(
            kind='other', label='Restarted background work', status='running',
            celery_task_id='lost-background-task',
            started_at=self.stop_at - timezone.timedelta(seconds=10),
            progress=45,
        )
        result = _expire_stale_background_jobs(self.now, startup=True, snapshot=self._snapshot(False))
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.result.get('state'), 'interrupted_service_restart')
        self.assertTrue(job.result.get('service_restart_interrupted'))
        self.assertEqual(result['running_failed_ids'], [job.pk])
