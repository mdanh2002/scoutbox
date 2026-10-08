import json
import re
import time
import hashlib
import os
import uuid
import requests
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
from portal.models import AIProviderConfig, UsageMetric, AIRequestLog, SearchSource, PortalSettings, CampaignRun, BackgroundJob, AI_REQUEST_TIMEOUT_DEFAULTS, AI_REQUEST_TIMEOUT_LIMITS
from .crypto import decrypt
from . import ollama
from .cloud_budget import is_cloud_provider, reserve as reserve_cloud, reconcile as reconcile_cloud, metadata as usage_metadata, usage_context, limit_status, CloudLimitReached
from .resources import host_resource_totals, gpu_telemetry_detail

STAGES = [
    'url_scrape', 'jd_analysis', 'first_filter', 'company_enrichment', 'freshness',
    'page_summarization', 'cv_tailoring', 'email_draft', 'question_answers',
    'cold_contact', 'import_inference', 'chatbot',
]

# Conservative production defaults. These are routing-stage limits, not provider-wide
# account limits. They can be changed independently in AI Configuration.
STAGE_TOKEN_DEFAULTS = {
    'url_scrape': {'max_input_tokens': 9000, 'max_output_tokens': 2500},
    'jd_analysis': {'max_input_tokens': 10000, 'max_output_tokens': 1400},
    'first_filter': {'max_input_tokens': 8000, 'max_output_tokens': 700},
    'company_enrichment': {'max_input_tokens': 7000, 'max_output_tokens': 900},
    'freshness': {'max_input_tokens': 5000, 'max_output_tokens': 600},
    'page_summarization': {'max_input_tokens': 10000, 'max_output_tokens': 1200},
    'cv_tailoring': {'max_input_tokens': 14000, 'max_output_tokens': 2200},
    'email_draft': {'max_input_tokens': 11000, 'max_output_tokens': 1400},
    'question_answers': {'max_input_tokens': 12000, 'max_output_tokens': 2200},
    'cold_contact': {'max_input_tokens': 9000, 'max_output_tokens': 1400},
    'import_inference': {'max_input_tokens': 12000, 'max_output_tokens': 3500},
    'chatbot': {'max_input_tokens': 48000, 'max_output_tokens': 5000},
    'general': {'max_input_tokens': 7000, 'max_output_tokens': 900},
    'provider_test': {'max_input_tokens': 512, 'max_output_tokens': 64},
}

CLOUD_STAGE_TOKEN_DEFAULTS = {
    # Cloud reasoning models can spend a material part of maxOutputTokens on hidden
    # thinking. These defaults therefore leave enough room for both reasoning and the
    # complete structured payload ScoutBox must parse. They remain per-stage/user-editable
    # caps rather than provider-account limits.
    'url_scrape': {'max_input_tokens': 7000, 'max_output_tokens': 6000},
    'jd_analysis': {'max_input_tokens': 4500, 'max_output_tokens': 3000},
    'first_filter': {'max_input_tokens': 2200, 'max_output_tokens': 1800},
    'company_enrichment': {'max_input_tokens': 3000, 'max_output_tokens': 2200},
    'freshness': {'max_input_tokens': 1800, 'max_output_tokens': 1600},
    'page_summarization': {'max_input_tokens': 3200, 'max_output_tokens': 2200},
    'cv_tailoring': {'max_input_tokens': 10000, 'max_output_tokens': 3600},
    'email_draft': {'max_input_tokens': 6500, 'max_output_tokens': 2400},
    'question_answers': {'max_input_tokens': 9000, 'max_output_tokens': 3600},
    'cold_contact': {'max_input_tokens': 3500, 'max_output_tokens': 3000},
    'import_inference': {'max_input_tokens': 8000, 'max_output_tokens': 4200},
    'chatbot': {'max_input_tokens': 32000, 'max_output_tokens': 5000},
    'general': {'max_input_tokens': 3000, 'max_output_tokens': 1600},
    'provider_test': {'max_input_tokens': 512, 'max_output_tokens': 128},
}
CLOUD_HARD_MAX_INPUT=32000
CLOUD_HARD_MAX_OUTPUT=10000


class CloudRateLimited(RuntimeError):
    """A Cloud provider stayed rate-limited after ScoutBox's campaign backoff."""
    def __init__(self, provider, model, stage, retry_after_seconds=300):
        self.provider=str(provider or 'cloud').strip().lower()
        self.model=str(model or '').strip()
        self.stage=str(stage or 'cloud').strip()
        try:
            self.retry_after_seconds=max(30,min(1800,int(retry_after_seconds or 300)))
        except Exception:
            self.retry_after_seconds=300
        label=self.provider.title() if self.provider else 'Cloud provider'
        super().__init__(f'{label} is rate-limited after automatic backoff. Retry in about {self.retry_after_seconds} seconds.')


def _is_cloud_rate_limit_error(exc):
    response=getattr(exc,'response',None)
    status=getattr(response,'status_code',None)
    text=str(exc or '')
    return status==429 or '429' in text or 'Too Many Requests' in text or 'RESOURCE_EXHAUSTED' in text


def _cloud_retry_after_seconds(exc, default=0):
    """Read Retry-After / Gemini RetryInfo when available, without trusting huge waits."""
    response=getattr(exc,'response',None)
    value=None
    try:
        value=(getattr(response,'headers',{}) or {}).get('Retry-After')
        if value is not None:
            return max(2,min(300,int(float(value))))
    except Exception:
        pass
    try:
        body=getattr(response,'text','') or ''
        # Gemini quota responses commonly include retryDelay like "43s" or text such
        # as "Please retry in 43.2s". Keep parsing deliberately narrow.
        patterns=(r'(?i)retryDelay[^0-9]{0,30}([0-9]+(?:\.[0-9]+)?)s',r'(?i)retry in\s+([0-9]+(?:\.[0-9]+)?)s')
        for pattern in patterns:
            m=re.search(pattern,body)
            if m:
                return max(2,min(300,int(float(m.group(1))+0.999)))
    except Exception:
        pass
    try:
        return max(0,int(default or 0))
    except Exception:
        return 0


def _cloud_campaign_backoff_message(provider, stage, wait_seconds, resumed=False):
    ctx=usage_context()
    run_id=ctx.get('campaign_run_id')
    if not run_id:
        return
    label=str(provider or 'cloud').title()
    stage_label=str(stage or 'cloud').replace('_',' ')
    if resumed:
        message=f'Cloud research resumed after {label} rate-limit backoff'
        stage_text='Cloud research'
    else:
        message=f'{label} rate-limited during {stage_label}; retrying in {int(wait_seconds)}s'
        stage_text='Cloud research · provider cooldown'
    try:
        CampaignRun.objects.filter(pk=run_id,status='running').update(
            message=message[:500],stage=stage_text[:120],heartbeat_at=timezone.now())
    except Exception:
        pass


def _cloud_campaign_call_with_backoff(call, provider, model, stage, state=None):
    """Retry transient HTTP 429s for campaign Cloud calls before route failover.

    Test Selection and other interactive calls remain immediate. During a campaign, the
    run gets a visible cooldown message instead of appearing frozen at 15%. A shared
    state object caps total sleeping across Primary/Failover for one logical request.
    """
    ctx=usage_context()
    if not ctx.get('campaign_run_id'):
        return call()
    state=state if isinstance(state,dict) else {}
    state.setdefault('waited',0)
    defaults=(15,45)
    attempt=0
    while True:
        try:
            result=call()
            if attempt:
                _cloud_campaign_backoff_message(provider,stage,0,resumed=True)
            return result
        except Exception as exc:
            if not _is_cloud_rate_limit_error(exc):
                raise
            if bool(ctx.get('forum_only')):
                # Forum work is supplementary. Never spend up to 90 seconds of shared
                # Cloud rate-limit backoff on it; stop this idle pass immediately so a
                # primary Cloud campaign keeps the retry budget and worker throughput.
                retry_after=_cloud_retry_after_seconds(exc,300) or 300
                raise CloudRateLimited(provider,model,stage,retry_after_seconds=retry_after) from exc
            if attempt>=len(defaults):
                retry_after=_cloud_retry_after_seconds(exc,300) or 300
                raise CloudRateLimited(provider,model,stage,retry_after_seconds=retry_after) from exc
            remaining=max(0,90-int(state.get('waited') or 0))
            if remaining<2:
                retry_after=_cloud_retry_after_seconds(exc,300) or 300
                raise CloudRateLimited(provider,model,stage,retry_after_seconds=retry_after) from exc
            desired=_cloud_retry_after_seconds(exc,defaults[attempt]) or defaults[attempt]
            wait=max(2,min(60,int(desired),remaining))
            attempt+=1
            state['waited']=int(state.get('waited') or 0)+wait
            _cloud_campaign_backoff_message(provider,stage,wait,resumed=False)
            time.sleep(wait)


def cloud_rate_limit_cooldown(now=None, seconds=300):
    """Return a short provider-level scheduler cooldown after campaign HTTP 429s."""
    now=now or timezone.now()
    try:
        seconds=max(60,min(1800,int(seconds or 300)))
    except Exception:
        seconds=300
    cutoff=now-timedelta(seconds=seconds)
    try:
        row=(AIRequestLog.objects.filter(status='failed',runtime='cloud',subject_type='campaign',at__gte=cutoff)
             .exclude(metadata__forum_only=True)
             .filter(Q(error__icontains='429')|Q(error__icontains='Too Many Requests')|Q(error__icontains='RESOURCE_EXHAUSTED'))
             .order_by('-at').first())
    except Exception:
        row=None
    if not row:
        return None
    until=row.at+timedelta(seconds=seconds)
    if until<=now:
        return None
    return {'provider':str(row.provider or 'cloud'),'model':str(row.model or ''),'at':row.at,'until':until,'seconds_remaining':max(1,int((until-now).total_seconds()))}


def _local_ai_lane_count():
    """Number of simultaneous Ollama generation lanes permitted for background discovery.

    Campaign concurrency and model concurrency are deliberately separate. ScoutBox may run
    more than one discovery campaign, but only a small number of local-model generations
    should execute at once so the local accelerator/Ollama server is not oversubscribed.
    """
    try:
        value = int(os.environ.get('SCOUTBOX_LOCAL_AI_GENERATION_LANES', '1') or 1)
    except Exception:
        value = 1
    return max(1, min(4, value))


def _local_ai_lane_wait_seconds():
    try:
        value = int(os.environ.get('SCOUTBOX_LOCAL_AI_LANE_WAIT_SECONDS', '60') or 60)
    except Exception:
        value = 60
    return max(15, min(900, value))


def _local_ai_lock_client():
    """Return a Redis client for process-safe local-model lane locking.

    The discovery worker may run in multiple Celery processes. A Python threading lock or
    Django's locmem cache is not sufficient across processes, so use the same Redis broker
    ScoutBox already requires for Celery. If Redis is briefly unavailable we fail open so
    discovery still works rather than deadlocking on the guard rail.
    """
    try:
        import redis
        return redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
    except Exception:
        return None


def _lane_token_from_value(value):
    if value is None:
        return ''
    try:
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'replace')
        text = str(value or '')
        if text.startswith('{'):
            data = json.loads(text)
            if isinstance(data, dict):
                return str(data.get('token') or '')
        return text
    except Exception:
        return ''


def _lane_payload(token, *, run_id='', operation='', stage='', acquired_at=None):
    now = time.time()
    return json.dumps({
        'token': token,
        'run_id': str(run_id or ''),
        'operation': str(operation or ''),
        'stage': str(stage or ''),
        'pid': os.getpid(),
        'acquired_at': float(acquired_at or now),
        'heartbeat_at': now,
        'scoutbox_version': '0.10.103',
    }, separators=(',', ':'))


def _lane_payload_data(value):
    try:
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'replace')
        text = str(value or '')
        if not text.startswith('{'):
            return None
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _local_ai_lane_stale_seconds(timeout=None):
    try:
        requested = int(timeout or ai_request_timeout('ollama', 'general') or 180)
    except Exception:
        requested = 180
    try:
        override = int(os.environ.get('SCOUTBOX_LOCAL_AI_STALE_LOCK_SECONDS', '0') or 0)
    except Exception:
        override = 0
    if override:
        return max(60, min(900, override))
    return max(90, min(360, requested + 45))


def _release_local_ai_lane(client, key, token):
    try:
        current = client.get(key)
        if _lane_token_from_value(current) == str(token or ''):
            client.delete(key)
    except Exception:
        pass


def _refresh_local_ai_lane(client, key, token, *, run_id='', operation='', stage='', acquired_at=None, ttl=600):
    try:
        current = client.get(key)
        if _lane_token_from_value(current) != str(token or ''):
            return False
        client.set(key, _lane_payload(token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at), xx=True, ex=max(60, int(ttl or 600)))
        return True
    except Exception:
        return False


def _clear_stale_local_ai_lanes(client, *, timeout=None, force_legacy=True):
    """Best-effort cleanup for orphaned local-AI semaphore keys.

    Older ScoutBox builds stored only an opaque token and relied on Redis TTLs that could
    keep every campaign waiting for many minutes after a worker/container died. Newer
    locks include a heartbeat; when it stops, the next waiter may reclaim the lane.
    """
    cleared = []
    now = time.time()
    stale_after = _local_ai_lane_stale_seconds(timeout)
    try:
        lane_count = _local_ai_lane_count()
    except Exception:
        lane_count = 1
    for lane in range(lane_count):
        key = f'scoutbox:local-ai:lane:{lane}'
        try:
            value = client.get(key)
            if not value:
                continue
            data = _lane_payload_data(value)
            if data is None:
                if force_legacy:
                    client.delete(key)
                    cleared.append({'lane': lane, 'reason': 'legacy_lock'})
                continue
            heartbeat = float(data.get('heartbeat_at') or data.get('acquired_at') or 0)
            age = now - heartbeat if heartbeat else stale_after + 1
            if age >= stale_after:
                client.delete(key)
                cleared.append({'lane': lane, 'reason': 'heartbeat_stale', 'age_seconds': int(age)})
        except Exception:
            continue
    if cleared:
        try:
            UsageMetric.objects.create(
                category='local_ai_lane', provider='ollama', stage='stale_lock_reclaimed', requests=0, pages=0,
                metadata=usage_metadata({'cleared': cleared, 'stale_after_seconds': stale_after})
            )
        except Exception:
            pass
    return cleared


def local_ai_lane_busy():
    """Best-effort check used by planners to avoid queueing behind Ollama.

    This is deliberately advisory. If Redis is unavailable, return False so ScoutBox
    can still run in simple/single-process deployments.
    """
    client = _local_ai_lock_client()
    if client is None:
        return False
    try:
        _clear_stale_local_ai_lanes(client, timeout=ai_request_timeout('ollama', 'general'), force_legacy=True)
        for lane in range(_local_ai_lane_count()):
            key = f'scoutbox:local-ai:lane:{lane}'
            if not client.exists(key):
                return False
        return True
    except Exception:
        return False


def _campaign_ai_wait_message(run_id, stage, waited, lane_count):
    try:
        if not run_id:
            return
        label = str(stage or 'local AI').replace('_', ' ')
        CampaignRun.objects.filter(pk=run_id, status='running').update(
            message=f'Waiting for local AI lane · {label} · {int(waited)}s',
            stage='Waiting for local AI',
            heartbeat_at=timezone.now(),
        )
    except Exception:
        pass


def _run_ollama_with_campaign_lane(call, *, stage='general', timeout=None):
    """Serialize Ollama generation without serializing whole ScoutBox workflows.

    Only real campaign executions (``operation='campaign'``) are allowed to defer a
    CampaignRun when accelerator lanes are busy. Background enrichment and maintenance
    jobs may carry a campaign/run id for token attribution; treating those ids as active
    campaign ownership caused Company Enrichment / page-summary jobs to stall behind
    discovery forever. Those jobs now use the same cooperative lane guard briefly, then
    fail open to the historical direct call instead of changing campaign state.
    """
    ctx = usage_context()
    run_id = ctx.get('campaign_run_id')
    operation = str(ctx.get('operation') or '').strip().lower()
    forum_only = bool(ctx.get('forum_only'))
    maintenance_low_priority = bool(ctx.get('local_ai_low_priority') or ctx.get('maintenance_hidden_lead_reassessment'))
    is_campaign_operation = bool(run_id and operation == 'campaign' and not forum_only)
    if not run_id and not forum_only and not maintenance_low_priority:
        return call()
    lane_count = _local_ai_lane_count()
    client = _local_ai_lock_client()
    if client is None:
        # Primary/background work keeps the historical fail-open behavior. Optional or
        # low-priority maintenance work must yield rather than compete with discovery.
        if forum_only:
            raise LocalAILaneBusy('Forum pass yielded because the Local AI lane guard is unavailable')
        if maintenance_low_priority:
            raise LocalAILaneBusy('Automatic Hidden Lead reassessment yielded because the Local AI lane guard is unavailable')
        return call()
    token = f"{run_id or 'background'}:{operation or 'background'}:{os.getpid()}:{uuid.uuid4().hex}"
    acquired_at = time.time()
    ttl = max(120, min(900, int(timeout or 180) + 120))
    _clear_stale_local_ai_lanes(client, timeout=timeout, force_legacy=True)

    def primary_waiting():
        if not forum_only and not maintenance_low_priority:
            return False
        try:
            for criteria in CampaignRun.objects.filter(
                status__in=['queued','running','stopping']
            ).values_list('criteria',flat=True):
                data=criteria if isinstance(criteria,dict) else {}
                if not bool(data.get('forum_only') or data.get('run_kind')=='forum_only'):
                    return True
            if maintenance_low_priority:
                # Hidden Lead reassessment is catch-up maintenance. It should never
                # compete with other queued/running jobs for the GPU. Exclude its own
                # single worker row so it can acquire a lane when the system is otherwise idle.
                return BackgroundJob.objects.filter(status__in=['queued','running']).exclude(
                    kind='filter_hidden_leads', result__hidden_lead_minibrowser_reassessment=True
                ).exists()
            # Forum passes are optional acquisition. Any queued/running background
            # operation wins, including Hidden Leads and diagnostics/provider work.
            return BackgroundJob.objects.filter(status__in=['queued','running']).exists()
        except Exception:
            # Optional/maintenance work should fail safe if priority cannot be established.
            return True

    def run_in_lane(key, *, update_campaign=True):
        if update_campaign and run_id:
            try:
                CampaignRun.objects.filter(pk=run_id, status='running').update(
                    stage=str(stage or 'Local AI')[:120],
                    message=f'Running local AI · {str(stage or "generation").replace("_", " ")}'[:500],
                    heartbeat_at=timezone.now(),
                )
            except Exception:
                pass
        stop_event = None
        try:
            import threading as _threading
            stop_event = _threading.Event()
            def _lane_heartbeat():
                while not stop_event.wait(10):
                    if not _refresh_local_ai_lane(client, key, token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at, ttl=ttl):
                        break
            _threading.Thread(target=_lane_heartbeat, name=f'scoutbox-local-ai-lane-{run_id or "background"}', daemon=True).start()
        except Exception:
            stop_event = None
        try:
            return call()
        finally:
            if stop_event is not None:
                try:
                    stop_event.set()
                except Exception:
                    pass
            _release_local_ai_lane(client, key, token)

    if forum_only:
        if primary_waiting():
            raise LocalAILaneBusy('Forum pass yielded to primary discovery before Local AI qualification')
        for lane in range(lane_count):
            key = f'scoutbox:local-ai:lane:{lane}'
            try:
                if client.set(key, _lane_payload(token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at), nx=True, ex=ttl):
                    # Recheck after acquisition to close the race with a newly queued
                    # primary run. Release immediately rather than making it wait.
                    if primary_waiting():
                        _release_local_ai_lane(client, key, token)
                        raise LocalAILaneBusy('Forum pass yielded to newly queued primary discovery')
                    return run_in_lane(key, update_campaign=False)
            except LocalAILaneBusy:
                raise
            except Exception:
                raise LocalAILaneBusy('Forum pass yielded because the Local AI lane guard failed')
        raise LocalAILaneBusy('Forum pass yielded because Local AI capacity is busy')

    if maintenance_low_priority and not is_campaign_operation:
        if primary_waiting():
            raise LocalAILaneBusy('Automatic Hidden Lead reassessment yielded to active primary/background work')
        try:
            wait_limit=max(1,min(30,int(os.environ.get('SCOUTBOX_LOCAL_MAINTENANCE_AI_WAIT_SECONDS','5') or 5)))
        except Exception:
            wait_limit=5
        deadline=time.monotonic()+wait_limit
        while time.monotonic() <= deadline:
            _clear_stale_local_ai_lanes(client, timeout=timeout, force_legacy=True)
            for lane in range(lane_count):
                key=f'scoutbox:local-ai:lane:{lane}'
                try:
                    if client.set(key, _lane_payload(token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at), nx=True, ex=ttl):
                        if primary_waiting():
                            _release_local_ai_lane(client, key, token)
                            raise LocalAILaneBusy('Automatic Hidden Lead reassessment yielded to newly queued work')
                        return run_in_lane(key, update_campaign=False)
                except LocalAILaneBusy:
                    raise
                except Exception:
                    raise LocalAILaneBusy('Automatic Hidden Lead reassessment yielded because the Local AI lane guard failed')
            time.sleep(1.0)
        raise LocalAILaneBusy('Automatic Hidden Lead reassessment deferred because Local AI capacity is busy')

    if not is_campaign_operation:
        # Background enrichment should not mutate/defer a CampaignRun simply because it
        # carries campaign IDs for usage attribution. Wait briefly for a lane; when the
        # guard stays full, record the condition and use the previous fail-open behavior.
        try:
            wait_limit=max(5,min(180,int(os.environ.get('SCOUTBOX_LOCAL_BACKGROUND_AI_WAIT_SECONDS','30') or 30)))
        except Exception:
            wait_limit=30
        deadline=time.monotonic()+wait_limit
        while time.monotonic() <= deadline:
            _clear_stale_local_ai_lanes(client, timeout=timeout, force_legacy=True)
            for lane in range(lane_count):
                key=f'scoutbox:local-ai:lane:{lane}'
                try:
                    if client.set(key, _lane_payload(token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at), nx=True, ex=ttl):
                        return run_in_lane(key, update_campaign=False)
                except Exception:
                    return call()
            time.sleep(1.0)
        try:
            UsageMetric.objects.create(
                category='local_ai_lane', provider='ollama', stage='background_fallback', requests=0, pages=0,
                metadata=usage_metadata({'campaign_run_id': run_id, 'operation': operation, 'stage': stage, 'waited_seconds': wait_limit, 'lanes': lane_count})
            )
        except Exception:
            pass
        return call()

    wait_limit = _local_ai_lane_wait_seconds()
    # Query planning is an optional enrichment stage; first filtering is high-volume.
    # Neither should leave extra campaign tasks sitting in Redis/Celery for 20 minutes
    # while one local model request owns the accelerator. If the lane stays busy, the
    # caller defers this campaign and the scheduler retries later.
    if str(stage or '').strip().lower() == 'query_planning':
        wait_limit = min(wait_limit, 15)
    deadline = time.monotonic() + wait_limit
    last_notice = 0.0
    while time.monotonic() <= deadline:
        _clear_stale_local_ai_lanes(client, timeout=timeout, force_legacy=True)
        for lane in range(lane_count):
            key = f'scoutbox:local-ai:lane:{lane}'
            try:
                if client.set(key, _lane_payload(token, run_id=run_id, operation=operation, stage=stage, acquired_at=acquired_at), nx=True, ex=ttl):
                    return run_in_lane(key)
            except Exception:
                return call()
        now = time.monotonic()
        waited = max(0, int(wait_limit - max(0, deadline - now)))
        if now - last_notice >= 10:
            _campaign_ai_wait_message(run_id, stage, waited, lane_count)
            try:
                UsageMetric.objects.create(
                    category='local_ai_lane', provider='ollama', stage='wait', requests=0, pages=0,
                    metadata=usage_metadata({'campaign_run_id': run_id, 'stage': stage, 'waited_seconds': waited, 'lanes': lane_count})
                )
            except Exception:
                pass
            last_notice = now
        time.sleep(2.5)
    # Do not fail open into unbounded concurrent Ollama calls. Defer primary campaign work
    # and let the scheduler retry when accelerator capacity is available.
    try:
        CampaignRun.objects.filter(pk=run_id, status='running').update(
            message='Local AI lane busy; deferring this run',
            stage='Local AI deferred', heartbeat_at=timezone.now())
    except Exception:
        pass
    raise LocalAILaneBusy('Local AI lane remained busy; campaign run deferred')


CLOUD_PROVIDERS = ('openai','gemini','openrouter')
CLOUD_BUNDLE_STAGES = ('url_scrape','jd_analysis','first_filter','company_enrichment','freshness','page_summarization')
COST_SENSITIVE_STAGES = {'url_scrape','jd_analysis','first_filter','company_enrichment','freshness','page_summarization','cold_contact','chatbot','general'}
# When Cloud Web has a verified Secondary model, routine high-volume stages start on the
# economy lane and fall back to Primary. URL discovery and the heavier tailoring/inference
# stages stay on Primary. This keeps quality for user-facing writing while avoiding 3.7-class
# spend for straightforward extraction, classification, freshness checks and summarization.
CLOUD_ECONOMY_FIRST_STAGES = {
    'jd_analysis','first_filter','company_enrichment','freshness','page_summarization',
}

def configured_cloud_model(cfg):
    """Return the explicit model or the last resolved automatic model.

    Provider Configuration intentionally allows Default model = Automatic.  A provider test resolves that automatic choice to a concrete generation model;
    reuse that tested model for Discovery routing instead of treating Automatic as
    unconfigured.
    """
    if not cfg:
        return ''
    explicit=str(cfg.default_model or '').strip()
    if explicit:
        return explicit
    caps=dict(cfg.capabilities or {})
    tested=str(caps.get('model') or '').strip()
    if tested:
        return tested
    return ''

def cloud_provider_priority():
    """Return a deterministic cloud-provider order, never database/alphabetical accident."""
    try:
        saved=list((PortalSettings.objects.get_or_create(pk=1)[0].cloud_provider_priority or []))
    except Exception:
        saved=[]
    out=[]
    for value in saved + list(CLOUD_PROVIDERS):
        value=str(value or '').strip().lower()
        if value in CLOUD_PROVIDERS and value not in out:
            out.append(value)
    return out

def configured_cloud_configs(require_key=True, require_model=True):
    """Enabled cloud configurations ordered by the user's explicit priority."""
    configs={c.provider:c for c in AIProviderConfig.objects.filter(provider__in=CLOUD_PROVIDERS,enabled=True)}
    out=[]
    for provider in cloud_provider_priority():
        cfg=configs.get(provider)
        if not cfg: continue
        if require_model and not configured_cloud_model(cfg): continue
        if require_key:
            try:
                if not decrypt(cfg.api_key_enc): continue
            except Exception:
                continue
        out.append(cfg)
    return out

def usable_cloud_configs(require_web=False):
    """Enabled Cloud providers ordered by operator priority.

    Provider capability tests are health/diagnostic evidence, not a permanent routing
    lock. A stale or transient failed web-capability test must not disable Cloud Web when
    the provider is enabled, has credentials and has a resolved model. Runtime execution
    remains authoritative and will fall through the configured provider priority on error.
    """
    out=[]
    for cfg in configured_cloud_configs(require_key=True,require_model=True):
        model=configured_cloud_model(cfg)
        if require_web and not web_capable_cloud_route(cfg.provider,model):
            continue
        out.append(cfg)
    return out


def has_configured_cloud_model():
    return bool(usable_cloud_configs(require_web=False))


def configured_cloud_web_configs():
    """Usable Cloud Web providers in explicit operator priority order."""
    return usable_cloud_configs(require_web=True)


def _cloud_web_pipeline_stages():
    return [stage for stage in STAGES if stage != 'chatbot']


def cloud_web_stage_routes():
    """Return sanitized per-stage Cloud Web routes with legacy upgrade fallback.

    0.9.22 gives each Discovery stage its own provider + Primary/Failover pair and token
    caps. A stage may use a different Cloud provider from another stage, but its Primary
    and Failover are intentionally same-provider so an error never silently crosses vendors.
    """
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    saved=getattr(ps,'cloud_web_stage_routes',{}) or {}
    if not isinstance(saved,dict):
        saved={}
    legacy_provider=str(getattr(ps,'cloud_web_provider','') or '').strip().lower()
    legacy_primary=str(getattr(ps,'cloud_web_primary_model','') or '').strip()
    legacy_secondary=str(getattr(ps,'cloud_web_secondary_model','') or '').strip()
    out={}
    for stage in _cloud_web_pipeline_stages():
        defaults=dict(CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general']))
        raw=dict(saved.get(stage) or {})
        if not raw and legacy_provider and legacy_primary:
            raw={'provider':legacy_provider,'model':legacy_primary}
            if legacy_secondary and legacy_secondary!=legacy_primary:
                raw.update({'fallback_provider':legacy_provider,'fallback_model':legacy_secondary})
        provider=str(raw.get('provider') or '').strip().lower()
        model=str(raw.get('model') or '').strip()
        fallback_provider=str(raw.get('fallback_provider') or provider if raw.get('fallback_model') else '').strip().lower()
        fallback_model=str(raw.get('fallback_model') or '').strip()
        row={
            'max_input_tokens':_safe_int(raw.get('max_input_tokens'),defaults['max_input_tokens']),
            'max_output_tokens':_safe_int(raw.get('max_output_tokens'),defaults['max_output_tokens']),
        }
        if provider in CLOUD_PROVIDERS and model:
            row.update({'provider':provider,'model':model,'execution_mode':'cloud'})
            if fallback_model and fallback_model!=model and fallback_provider==provider:
                row.update({'fallback_provider':provider,'fallback_model':fallback_model,'fallback_execution_mode':'cloud'})
        out[stage]=row
    return out


def cloud_web_selection(stage='url_scrape'):
    """Compatibility summary for one Cloud Web stage (URL discovery by default)."""
    row=dict(cloud_web_stage_routes().get(stage) or {})
    provider=str(row.get('provider') or '').strip().lower()
    primary=str(row.get('model') or '').strip()
    secondary=str(row.get('fallback_model') or '').strip()
    cfg=AIProviderConfig.objects.filter(provider=provider,enabled=True).first() if provider else None
    configured=False
    if cfg and primary:
        try: configured=bool(decrypt(cfg.api_key_enc))
        except Exception: configured=False
    return {'provider':provider,'primary_model':primary,'secondary_model':secondary,'configured':configured}


def configured_cloud_web_routes(stage='url_scrape'):
    sel=cloud_web_selection(stage)
    if not sel.get('configured'):
        return []
    provider=sel.get('provider'); primary=sel.get('primary_model'); secondary=sel.get('secondary_model')
    if not provider or not primary:
        return []
    rows=[(provider,primary,'primary')]
    if secondary and secondary!=primary:
        rows.append((provider,secondary,'secondary'))
    return rows


def has_usable_cloud_web_model():
    # Campaign execution depends on all configured pipeline stages being routable.
    return all(bool(configured_cloud_web_routes(stage)) for stage in _cloud_web_pipeline_stages())


def automatic_cloud_route(stage, require_web=None):
    """Resolve an automatic Cloud route without consulting saved local stage routing."""
    if require_web is None:
        require_web=(stage=='url_scrape')
    configs=usable_cloud_configs(require_web=bool(require_web))
    if not configs:
        requirement=' with configured web-research routing' if require_web else ''
        raise RuntimeError(f'No configured Cloud AI provider/model is currently usable{requirement}.')
    defaults=dict(CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general']))
    primary=configs[0]
    route={
        'provider':primary.provider,
        'model':configured_cloud_model(primary),
        'execution_mode':'cloud',
        'automatic':True,
        'max_input_tokens':defaults['max_input_tokens'],
        'max_output_tokens':defaults['max_output_tokens'],
    }
    fallback=next((cfg for cfg in configs[1:] if cfg.provider!=primary.provider),None)
    if fallback:
        route.update({'fallback_provider':fallback.provider,'fallback_model':configured_cloud_model(fallback)})
    return route


def web_capable_cloud_route(provider, model=''):
    """Whether this configured route may use ScoutBox's native grounded web path.

    A capability test may explicitly mark web search false. Otherwise the three supported
    cloud adapters are considered web-capable because ScoutBox implements their native
    web/search interface and will still surface execution errors normally.
    """
    provider=str(provider or '').strip().lower()
    if provider not in CLOUD_PROVIDERS: return False
    cfg=AIProviderConfig.objects.filter(provider=provider,enabled=True).first()
    resolved_model=str(model or configured_cloud_model(cfg) or '').strip() if cfg else ''
    if not cfg or not resolved_model: return False
    try:
        if not decrypt(cfg.api_key_enc): return False
    except Exception:
        return False
    # Capability tests are deliberately advisory. A previous HTTP/tool failure can mark
    # web_search false even though the same configured model works later. Eligibility is
    # therefore based on configuration; the live request decides whether to fall back.
    return True

def bundle_owners(routes=None, discovery_mode='source_guided'):
    """Return effective upstream cloud bundle owner for legacy/local routing.

    Cloud Web 0.9.22 has an explicit Primary/Failover pair for every pipeline stage, so
    stage inheritance is disabled there. Local/source-guided routing keeps the existing
    bundle description behavior for compatibility.
    """
    result={stage:{'primary':None,'fallback':None} for stage in CLOUD_BUNDLE_STAGES}
    if discovery_mode=='cloud_web':
        return result
    routes=stage_routes_with_defaults(routes if routes is not None else _shared_routes())
    for lane,pkey,mkey in (('primary','provider','model'),('fallback','fallback_provider','fallback_model')):
        owner=None
        for stage in CLOUD_BUNDLE_STAGES:
            row=routes.get(stage) or {}
            provider=str(row.get(pkey) or '').strip().lower()
            model=str(row.get(mkey) or '').strip()
            # Cloud Web makes URL discovery itself the effective primary cloud owner when
            # Automatic URL discovery is used. Fallback still requires an explicit route.
            if lane=='primary' and stage=='url_scrape' and discovery_mode=='cloud_web' and not provider:
                # Cloud Web automatic discovery must resolve only through a route that
                # can actually execute ScoutBox's grounded/native web path.  Do not let
                # a merely configured generation-only Cloud model become a bundle owner.
                selected=configured_cloud_web_routes()
                if selected:
                    provider,model,_lane=selected[0]
            if owner:
                result[stage][lane]=dict(owner)
                continue
            if provider and web_capable_cloud_route(provider,model):
                owner={'stage':stage,'provider':provider,'model':model or configured_cloud_model(AIProviderConfig.objects.filter(provider=provider).first())}
                result[stage][lane]=None  # owner row remains explicitly editable
    return result

def effective_cloud_bundle_anchor(routes=None, discovery_mode='source_guided', lane='primary', start_stage='jd_analysis'):
    """Return a legacy bundle anchor for source-guided routing only.

    Cloud Web no longer inherits the URL-stage model downstream: every stage resolves its
    own saved provider/model pair in 0.9.22.
    """
    if discovery_mode is None:
        try: discovery_mode=PortalSettings.objects.get_or_create(pk=1)[0].discovery_mode
        except Exception: discovery_mode='source_guided'
    if discovery_mode=='cloud_web':
        return None
    return None


def _safe_int(value, default, minimum=64, maximum=200000):
    try:
        value = int(value)
    except Exception:
        return default
    return max(minimum, min(maximum, value))


def _shared_routes():
    """Return the shared route map without losing routes saved on another provider row.

    Older ScoutBox builds used an AIProviderConfig row as the routing holder.  A user can
    therefore have Chatbot routing on a cloud row and pipeline routing on the Ollama row.
    Merge all saved stage maps first, then let the Ollama holder override only the stages it
    actually contains.  This keeps exact provider/model choices stable across navigation,
    provider edits and upgrades.
    """
    merged={}
    configs=list(AIProviderConfig.objects.all().order_by('provider'))
    for cfg in configs:
        for stage,row in (cfg.stage_routes or {}).items():
            if stage not in merged and isinstance(row,dict):
                merged[stage]=dict(row)
    preferred=next((cfg for cfg in configs if cfg.provider=='ollama'),None)
    if preferred:
        for stage,row in (preferred.stage_routes or {}).items():
            if isinstance(row,dict):
                merged[stage]=dict(row)
    return merged


def pipeline_route_signature(discovery_mode='', routes_override=None):
    """Stable signature of routing/provider state used to invalidate stale model tests."""
    configs=[]
    for cfg in AIProviderConfig.objects.all().order_by('provider'):
        configs.append({
            'provider':cfg.provider, 'enabled':bool(cfg.enabled), 'default_model':cfg.default_model or '',
            'effective_model':configured_cloud_model(cfg) if cfg.provider in CLOUD_PROVIDERS else (cfg.default_model or ''),
            'base_url':cfg.base_url or '', 'max_output_tokens':cfg.max_output_tokens or 0,
        })
    search_sources=[]
    for src in SearchSource.objects.filter(enabled=True).order_by('name'):
        search_sources.append({
            'name':src.name,'enabled':bool(src.enabled),'preferred_initial':bool(src.preferred_initial),
            'base_url':src.base_url or '','public_fallback':bool(src.public_fallback),
            'config_json':src.config_json or {},
        })
    routes = stage_routes_with_defaults(routes_override if routes_override is not None else _shared_routes())
    # Treat omitted and explicitly blank Automatic/fallback fields as the same
    # selection so a persisted Automatic test remains current after navigation.
    routes={stage:{k:v for k,v in (row or {}).items() if not (k in ('provider','model','fallback_provider','fallback_model') and not v)} for stage,row in routes.items() if stage!='chatbot'}
    payload={'discovery_mode':discovery_mode or '', 'routes':routes, 'configs':configs, 'search_sources':search_sources, 'cloud_web_stage_routes':cloud_web_stage_routes()}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode('utf-8')).hexdigest()


def stage_defaults(stage):
    return dict(STAGE_TOKEN_DEFAULTS.get(stage, STAGE_TOKEN_DEFAULTS['general']))


def token_limits_for_stage(stage, provider=None):
    # Local Performance Lab stays broad; cloud lab runs are deliberately capped.
    if (stage or '').startswith('lab'):
        return {'max_input_tokens': 8000, 'max_output_tokens': 1000} if is_cloud_provider(provider) else {'max_input_tokens': None, 'max_output_tokens': None}
    cloud=is_cloud_provider(provider)
    default_table=CLOUD_STAGE_TOKEN_DEFAULTS if cloud else STAGE_TOKEN_DEFAULTS
    defaults=dict(default_table.get(stage,default_table['general']))
    # Cloud Web has its own visible per-stage caps in 0.9.22. Local stage caps remain separate.
    if cloud and stage!='chatbot' and _current_discovery_mode()=='cloud_web':
        cloud_route=(cloud_web_stage_routes().get(stage) or {})
        return {
            'max_input_tokens': _safe_int(cloud_route.get('max_input_tokens'), defaults['max_input_tokens']),
            'max_output_tokens': _safe_int(cloud_route.get('max_output_tokens'), defaults['max_output_tokens']),
        }
    route = (_shared_routes().get(stage) or {}) if stage else {}
    return {
        'max_input_tokens': _safe_int(route.get('max_input_tokens'), defaults['max_input_tokens']),
        'max_output_tokens': _safe_int(route.get('max_output_tokens'), defaults['max_output_tokens']),
    }


def _rough_tokens(text):
    # Deliberately provider-neutral. It is a guardrail, not billing-token accounting.
    if not text:
        return 0
    words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    return max(1, int(len(words) * 1.18))


def _trim_prompt(prompt, max_input_tokens):
    """Approximate preflight cap while preserving both instructions and trailing evidence."""
    if not max_input_tokens:
        return prompt, False, _rough_tokens(prompt)
    estimate = _rough_tokens(prompt)
    if estimate <= max_input_tokens:
        return prompt, False, estimate
    # ~4 chars/token is a conservative cross-model approximation. Keep the start and
    # end because prompts usually place policy at the start and source material at the end.
    char_budget = max(1200, int(max_input_tokens * 3.6))
    if len(prompt) <= char_budget:
        return prompt, False, estimate
    head = int(char_budget * 0.58)
    tail = char_budget - head
    marker = '\n\n[... input truncated by configured stage token cap ...]\n\n'
    trimmed = prompt[:head] + marker + prompt[-tail:]
    return trimmed, True, _rough_tokens(trimmed)


def _record(provider, model, stage, started, tokens_in=0, tokens_out=0, error=False, metadata=None):
    meta=metadata or {}
    try: reasoning=max(0,int(meta.get('reasoning_tokens') or meta.get('thoughtsTokenCount') or 0))
    except Exception: reasoning=0
    try: web_queries=max(0,int(meta.get('web_queries_count') or meta.get('web_search_queries') or 0))
    except Exception: web_queries=0
    UsageMetric.objects.create(
        category='lab' if stage.startswith('lab') else 'ai', provider=provider, model=model or '', stage=stage,
        requests=1, tokens_in=max(0, int(tokens_in or 0)), tokens_out=max(0, int(tokens_out or 0)),
        reasoning_tokens=reasoning, web_search_queries=web_queries,
        errors=1 if error else 0, latency_ms=int((time.time()-started)*1000), metadata=usage_metadata(meta),
    )


def estimate_tokens(text):
    """Public provider-neutral preflight estimate; never use as billing data."""
    return _rough_tokens(text)


def _gemini_thinking_config(model, stage, override=None):
    """Use low thinking for high-volume/simple work while preserving complex drafting stages."""
    override=override or {}
    force_low=bool(override.get('_configuration_test_low_thinking')) or stage in COST_SENSITIVE_STAGES
    if not force_low:
        return {}, ''
    model_l=str(model or '').lower()
    if model_l.startswith('gemini-3'):
        return {'thinkingConfig':{'thinkingLevel':'low'}}, 'low'
    if model_l.startswith('gemini-2.5'):
        return {'thinkingConfig':{'thinkingBudget':128}}, 'budget=128'
    return {}, ''


def _openai_text(data):
    if data.get('output_text'):
        return data['output_text']
    chunks=[]
    for item in data.get('output', []):
        for content in item.get('content', []):
            if content.get('type') in ('output_text','text') and content.get('text'):
                chunks.append(content['text'])
    return '\n'.join(chunks)


EMPTY_OUTPUT_WARNING_CODE='empty_output'
EMPTY_OUTPUT_WARNING_DETAIL='AI request returned no visible output.'


class AIEmptyOutputWarning(RuntimeError):
    """Provider call completed but produced no usable visible response."""


class LocalAILaneBusy(RuntimeError):
    """Local Ollama generation was busy long enough that this run should defer."""


def ai_request_timeout(provider, stage='general'):
    """Return the persisted per-attempt provider timeout for an AI request.

    Chatbot has its own lane regardless of provider. Other Ollama generation uses the
    Local AI lane and Cloud providers use the Cloud AI lane. The database value is
    clamped defensively so stale/manual database edits cannot create unbounded waits.
    """
    provider=str(provider or '').strip().lower()
    stage=str(stage or 'general').strip().lower()
    lane='chatbot' if stage=='chatbot' else ('local_ai' if provider=='ollama' else 'cloud_ai')
    field={
        'local_ai':'local_ai_request_timeout_seconds',
        'cloud_ai':'cloud_ai_request_timeout_seconds',
        'chatbot':'chatbot_provider_timeout_seconds',
    }[lane]
    default=int(AI_REQUEST_TIMEOUT_DEFAULTS[lane])
    low,high=AI_REQUEST_TIMEOUT_LIMITS[lane]
    try:
        ps=PortalSettings.objects.only(field).get(pk=1)
        value=int(getattr(ps,field) or default)
    except Exception:
        value=default
    return max(int(low),min(int(high),value))


def _forum_request_timeout(provider, timeout):
    """Cap one optional Forum AI call so it cannot occupy provider capacity for long."""
    if not bool(usage_context().get('forum_only')):
        return timeout
    provider=str(provider or '').strip().lower()
    env_name='SCOUTBOX_FORUM_LOCAL_AI_TIMEOUT_SECONDS' if provider=='ollama' else 'SCOUTBOX_FORUM_CLOUD_AI_TIMEOUT_SECONDS'
    default=30
    minimum=15 if provider=='ollama' else 10
    try:
        cap=max(minimum,min(60,int(os.environ.get(env_name,str(default)) or default)))
    except Exception:
        cap=default
    return min(int(timeout or cap),cap)


def _require_visible_output(text):
    if not str(text or '').strip():
        raise AIEmptyOutputWarning(EMPTY_OUTPUT_WARNING_DETAIL)
    return text


def generate_with(provider, model, prompt, stage='general', timeout=None, subject=None, attachments=None, limits_override=None, config_override=None, return_debug=False):
    # Runtime provider timeouts are centralized in PortalSettings, but callers may pass
    # a shorter bound for maintenance/watchdog work. The caller timeout can tighten but
    # not extend the configured provider timeout.
    configured_timeout=ai_request_timeout(provider,stage)
    if timeout is not None:
        try:
            configured_timeout=min(int(configured_timeout or timeout),max(1,int(timeout)))
        except Exception:
            pass
    timeout=_forum_request_timeout(provider,configured_timeout)
    cfg=AIProviderConfig.objects.filter(provider=provider).first()
    override=dict(config_override or {})
    limits=dict(limits_override or token_limits_for_stage(stage,provider=provider))
    discovery_mode=str(usage_context().get('discovery_mode') or '').lower()
    if is_cloud_provider(provider) and discovery_mode=='source_guided':
        raise RuntimeError('Local AI Discovery routing violation: Cloud AI execution is not permitted for this campaign run.')
    if is_cloud_provider(provider):
        if bool(usage_context().get('forum_only')):
            # Forum qualification is supplementary: one bounded request must not consume
            # the primary Cloud campaign's token/time budget.
            limits['max_input_tokens']=min(int(limits.get('max_input_tokens') or 3500),3500)
            limits['max_output_tokens']=min(int(limits.get('max_output_tokens') or 1800),1800)
        if limits.get('max_input_tokens'): limits['max_input_tokens']=min(CLOUD_HARD_MAX_INPUT,int(limits['max_input_tokens']))
        if limits.get('max_output_tokens'): limits['max_output_tokens']=min(CLOUD_HARD_MAX_OUTPUT,int(limits['max_output_tokens']))
        provider_cap=override.get('max_output_tokens') if 'max_output_tokens' in override else (cfg.max_output_tokens if cfg else None)
        if provider_cap:
            stage_cap=limits.get('max_output_tokens'); limits['max_output_tokens']=min(stage_cap,int(provider_cap)) if stage_cap else min(CLOUD_HARD_MAX_OUTPUT,int(provider_cap))
    expect_json=bool(re.search(r'(?i)return\s+(?:json\s+only|only\s+json)|one\s+complete\s+json\s+object',str(prompt or '')))
    prompt,truncated,estimated_input=_trim_prompt(prompt,limits.get('max_input_tokens'))
    cap_meta={'configured_max_input_tokens':limits.get('max_input_tokens'),'configured_max_output_tokens':limits.get('max_output_tokens'),'input_was_truncated':truncated,'estimated_input_tokens_after_cap':estimated_input,'request_timeout_seconds':timeout}
    started_at=timezone.now(); operation=((subject or {}).get('budget_operation','') if isinstance(subject,dict) else '') or usage_context().get('operation','')
    reservation=None
    if provider=='ollama':
        if str(usage_context().get('discovery_mode') or '').lower()=='cloud_web':
            raise RuntimeError('Cloud Web routing violation: local Ollama execution is not permitted for this campaign run.')
        try:
            def _ollama_call():
                return ollama.generate(prompt,model=model or None,stage=stage,timeout=timeout,max_output_tokens=limits.get('max_output_tokens'),metadata_extra=cap_meta,base_url_override=override.get('base_url'))
            text,raw=_run_ollama_with_campaign_lane(_ollama_call, stage=stage, timeout=timeout)
            actual_model=str((raw or {}).get('model') or model or '')
            _require_visible_output(text)
            request_meta=_ollama_response_metadata(raw,limits)
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'ollama',actual_model,started_at,True,subject=subject,attachments=attachments,tokens_in=(raw or {}).get('prompt_eval_count'),tokens_out=(raw or {}).get('eval_count'),reasoning_tokens=0,web_search_queries=0,request_metadata=request_meta,raw_output_text=raw_output)
            debug={'provider':'ollama','raw':raw or {},**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
            return (text,debug) if return_debug else text
        except Exception as exc:
            _write_ai_request_log(prompt,'',stage,'ollama',model or '',started_at,False,error=exc,subject=subject,attachments=attachments); raise
    enabled=bool(override.get('enabled', cfg.enabled if cfg else False))
    if not cfg and not override: raise RuntimeError(f'{provider} is not configured')
    if not enabled: raise RuntimeError(f'{provider} is not enabled')
    key=str(override.get('api_key') or '') if 'api_key' in override else (decrypt(cfg.api_key_enc) if cfg else '')
    if not key: raise RuntimeError(f'{provider} API key is not configured')
    model=model or (cfg.default_model if cfg else '')
    if not model: raise RuntimeError(f'{provider} default model is not configured')
    reservation=reserve_cloud(provider=provider,requests=1,tokens_in=estimated_input,tokens_out=int(limits.get('max_output_tokens') or 0),operation=operation)
    started=time.time()
    try:
        if provider=='openai':
            base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://api.openai.com/v1').rstrip('/'); payload={'model':model,'input':prompt}
            if limits.get('max_output_tokens'): payload['max_output_tokens']=limits['max_output_tokens']
            r=requests.post(base+'/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json=payload,timeout=timeout); r.raise_for_status(); data=r.json(); text=_openai_text(data); _require_visible_output(text); usage=data.get('usage') or {}; reasoning=((usage.get('output_tokens_details') or {}).get('reasoning_tokens') or 0)
            _record('openai',model,stage,started,usage.get('input_tokens',0),usage.get('output_tokens',0),metadata={**cap_meta,'response_id':data.get('id',''),'reasoning_tokens':reasoning})
            reconcile_cloud(reservation,actual_tokens_in=usage.get('input_tokens',0),actual_tokens_out=usage.get('output_tokens',0),reasoning_tokens=reasoning)
            _openai_finish=str(data.get('status') or '')
            request_meta={'finish_reason':_openai_finish,'configured_max_output_tokens':limits.get('max_output_tokens'),'response_truncated':_openai_finish.lower() in {'incomplete','truncated'}}
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'openai',model,started_at,True,subject=subject,attachments=attachments,tokens_in=usage.get('input_tokens'),tokens_out=usage.get('output_tokens'),reasoning_tokens=reasoning,web_search_queries=0,request_metadata=request_meta,raw_output_text=raw_output)
            debug={'provider':'openai','raw':data,**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
            return (text,debug) if return_debug else text
        if provider=='gemini':
            base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/'); payload={'contents':[{'parts':[{'text':prompt}]}]}
            generation={}
            if limits.get('max_output_tokens'): generation['maxOutputTokens']=limits['max_output_tokens']
            thinking_extra,thinking_mode=_gemini_thinking_config(model,stage,override)
            generation.update(thinking_extra)
            if override.get('_manual_empty_retry_minimal') and str(model or '').lower().startswith('gemini-3'):
                generation['thinkingConfig']={'thinkingLevel':'minimal'}; thinking_mode='minimal'
            if expect_json and not override.get('_manual_disable_json_mime'):
                generation['responseMimeType']='application/json'
            if generation: payload['generationConfig']=generation
            r=requests.post(f'{base}/models/{model}:generateContent',headers={'x-goog-api-key':key,'Content-Type':'application/json'},json=payload,timeout=timeout); http_status=r.status_code; r.raise_for_status(); data=r.json(); chunks=[]
            for cand in data.get('candidates',[]):
                for part in (cand.get('content') or {}).get('parts',[]):
                    if part.get('text'): chunks.append(part['text'])
            text='\n'.join(chunks); usage=data.get('usageMetadata') or {}; reasoning=usage.get('thoughtsTokenCount',0) or 0
            if not str(text or '').strip():
                empty_meta={**cap_meta,'reasoning_tokens':reasoning,'http_status':http_status,'thinking_mode':thinking_mode,
                            'gemini_empty_retry':bool(override.get('_manual_empty_retry_minimal')),
                            'warning_code':EMPTY_OUTPUT_WARNING_CODE,'warning_detail':EMPTY_OUTPUT_WARNING_DETAIL}
                _record('gemini',model,stage,started,usage.get('promptTokenCount',0),usage.get('candidatesTokenCount',0),error=False,metadata=empty_meta)
                reconcile_cloud(reservation,actual_tokens_in=usage.get('promptTokenCount',0),actual_tokens_out=usage.get('candidatesTokenCount',0),reasoning_tokens=reasoning)
                warning=AIEmptyOutputWarning(EMPTY_OUTPUT_WARNING_DETAIL); warning.scoutbox_accounted=True
                _write_ai_request_log(prompt,'',stage,'gemini',model,started_at,False,error=warning,subject=subject,attachments=attachments,tokens_in=usage.get('promptTokenCount'),tokens_out=usage.get('candidatesTokenCount'),reasoning_tokens=reasoning,web_search_queries=0,request_metadata={'thinking_mode':thinking_mode,'gemini_empty_retry':bool(override.get('_manual_empty_retry_minimal'))})
                raise warning
            _record('gemini',model,stage,started,usage.get('promptTokenCount',0),usage.get('candidatesTokenCount',0),metadata={**cap_meta,'reasoning_tokens':reasoning,'http_status':http_status,'thinking_mode':thinking_mode,'gemini_empty_retry':bool(override.get('_manual_empty_retry_minimal'))})
            reconcile_cloud(reservation,actual_tokens_in=usage.get('promptTokenCount',0),actual_tokens_out=usage.get('candidatesTokenCount',0),reasoning_tokens=reasoning)
            _gemini_finish=','.join(str(c.get('finishReason') or '') for c in data.get('candidates',[]) if isinstance(c,dict) and c.get('finishReason'))
            _gemini_truncated=any(str(c.get('finishReason') or '').upper() in {'MAX_TOKENS','LENGTH'} for c in data.get('candidates',[]) if isinstance(c,dict))
            request_meta={'thinking_mode':thinking_mode,'finish_reason':_gemini_finish,'configured_max_output_tokens':limits.get('max_output_tokens'),'response_truncated':_gemini_truncated}
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'gemini',model,started_at,True,subject=subject,attachments=attachments,tokens_in=usage.get('promptTokenCount'),tokens_out=usage.get('candidatesTokenCount'),reasoning_tokens=reasoning,web_search_queries=0,request_metadata=request_meta,raw_output_text=raw_output)
            debug={'provider':'gemini','raw':data,'http_status':http_status,'usage':usage,'thinking_mode':thinking_mode,'finish_reasons':[str(c.get('finishReason')) for c in data.get('candidates',[]) if isinstance(c,dict) and c.get('finishReason')],**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
            return (text,debug) if return_debug else text
        if provider=='openrouter':
            base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://openrouter.ai/api/v1').rstrip('/'); payload={'model':model,'messages':[{'role':'user','content':prompt}]}
            if limits.get('max_output_tokens'): payload['max_tokens']=limits['max_output_tokens']
            r=requests.post(base+'/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','X-Title':'ScoutBox'},json=payload,timeout=timeout); r.raise_for_status(); data=r.json(); choice=(data.get('choices') or [{}])[0]; text=str((choice.get('message') or {}).get('content') or ''); _require_visible_output(text); usage=data.get('usage') or {}; reasoning=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0; actual_model=str(data.get('model') or model)
            _record('openrouter',actual_model,stage,started,usage.get('prompt_tokens',0),usage.get('completion_tokens',0),metadata={**cap_meta,'reasoning_tokens':reasoning,'cost_usd':usage.get('cost')})
            reconcile_cloud(reservation,actual_tokens_in=usage.get('prompt_tokens',0),actual_tokens_out=usage.get('completion_tokens',0),reasoning_tokens=reasoning,actual_cost_usd=usage.get('cost'))
            _or_finish=str(choice.get('finish_reason') or '')
            request_meta={'finish_reason':_or_finish,'configured_max_output_tokens':limits.get('max_output_tokens'),'response_truncated':_or_finish.lower() in {'length','max_tokens'}}
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'openrouter',actual_model,started_at,True,subject=subject,attachments=attachments,tokens_in=usage.get('prompt_tokens'),tokens_out=usage.get('completion_tokens'),reasoning_tokens=reasoning,web_search_queries=0,request_metadata=request_meta,raw_output_text=raw_output)
            debug={'provider':'openrouter','raw':data,'actual_model':actual_model,**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
            return (text,debug) if return_debug else text
        raise RuntimeError(f'Unsupported AI provider: {provider}')
    except Exception as exc:
        if getattr(exc,'scoutbox_accounted',False):
            raise
        reconcile_cloud(reservation,actual_tokens_in=0,actual_tokens_out=0)
        empty_output_warning=isinstance(exc,AIEmptyOutputWarning)
        metric_meta={**cap_meta,'query':prompt[:500],'limit_reached':isinstance(exc,CloudLimitReached)}
        if empty_output_warning:
            metric_meta.update({'warning_code':EMPTY_OUTPUT_WARNING_CODE,'warning_detail':EMPTY_OUTPUT_WARNING_DETAIL})
        else:
            metric_meta['error']=str(exc)[:1000]
        _record(provider,model,stage,started,error=not empty_output_warning,metadata=metric_meta)
        _write_ai_request_log(prompt,'',stage,provider,model,started_at,False,error=exc,subject=subject,attachments=attachments); raise

def _ollama_model_size_billions(item_or_name):
    """Best-effort parameter-size parser used by Automatic routing.

    Automatic routing favours a capable 4B+ local model within the host RAM ceiling. This
    keeps tiny 1B/2B models from becoming the high-volume filtering default while
    still avoiding a large 14B+ model unless no normal-size model is installed.
    """
    if isinstance(item_or_name, dict):
        # Prefer the advertised Ollama model tag (for example ``:7b``) over the
        # implementation-reported parameter count (which may be 7.6B for a model
        # users reasonably know as 7B). Automatic hardware tiers are intentionally
        # based on the advertised class; manual selection remains unrestricted.
        values=[
            item_or_name.get('model'),
            item_or_name.get('name'),
            (item_or_name.get('details') or {}).get('parameter_size'),
            item_or_name.get('parameter_size'),
        ]
    else:
        values=[item_or_name]
    for value in values:
        text=str(value or '')
        match=re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?![A-Za-z])', text)
        if match:
            try: return float(match.group(1))
            except Exception: pass
    return 0.0


_AUTO_OLLAMA_CACHE={'at':0.0,'default':'','model':'','cap_b':0.0}
_AUTO_OLLAMA_RAM_CACHE={'at':0.0,'cap_b':12.0}

def automatic_ollama_model_cap_billions():
    """Conservative hardware-aware ceiling for automatic local model selection.

    The smaller of detected system RAM and discrete GPU VRAM is used. This is only an
    automatic-selection guardrail: manually selected Ollama models are never blocked.
    """
    now=time.monotonic()
    if now-float(_AUTO_OLLAMA_RAM_CACHE.get('at') or 0)<60:
        return float(_AUTO_OLLAMA_RAM_CACHE.get('cap_b') or 12.0)
    try:
        total_mb=int((host_resource_totals() or {}).get('memory_total_mb') or 0)
    except Exception:
        total_mb=0
    try:
        _gpu,_gpu_mem,_label,_vram_used,vram_total=gpu_telemetry_detail()
        vram_mb=int(vram_total or 0)
    except Exception:
        vram_mb=0
    detected=[x for x in (total_mb,vram_mb) if x>0]
    effective_mb=min(detected) if detected else 0
    effective_gib=(float(effective_mb)/1024.0) if effective_mb else 0.0
    # Hardware counters rarely report the marketing number exactly. Treat roughly
    # 29 GiB and above as the 32 GB class so 31.8 GiB cards/hosts reliably receive
    # the 7B automatic tier. Smaller systems stay deliberately conservative; users
    # can always override an automatic choice manually.
    if 0 < effective_gib <= 10.0:
        cap_b=3.0
    elif 0 < effective_gib < 29.0:
        cap_b=4.0
    elif 0 < effective_gib <= 40.0:
        cap_b=7.0
    else:
        cap_b=12.0
    _AUTO_OLLAMA_RAM_CACHE.update({'at':now,'cap_b':cap_b})
    return cap_b

def _automatic_ollama_model(configured_default=''):
    configured_default=str(configured_default or '').strip()
    cap_b=automatic_ollama_model_cap_billions()
    now=time.monotonic()
    if _AUTO_OLLAMA_CACHE.get('default')==configured_default and float(_AUTO_OLLAMA_CACHE.get('cap_b') or 0)==cap_b and now-float(_AUTO_OLLAMA_CACHE.get('at') or 0)<60 and _AUTO_OLLAMA_CACHE.get('model'):
        return _AUTO_OLLAMA_CACHE['model']
    try:
        installed=list((ollama.diagnostics() or {}).get('installed') or [])
    except Exception:
        installed=[]
    choices=[]
    for item in installed:
        name=str(item.get('model') or item.get('name') or '').strip()
        if name:
            choices.append((_ollama_model_size_billions(item),name))
    capable=[x for x in choices if 4.0 <= x[0] <= cap_b]
    configured_size=_ollama_model_size_billions(configured_default)
    configured_capable=next((x for x in capable if x[1]==configured_default),None) if configured_default else None
    if configured_capable:
        # A capable configured default is the operator's primary preference.
        selected=configured_capable[1]
    elif capable:
        # Otherwise use the strongest normal-size local model; this avoids routing
        # high-volume filtering through 1B/2B models when a 4B+ model is installed.
        selected=max(capable,key=lambda x:(x[0],x[1]))[1]
    else:
        under=[x for x in choices if 0 < x[0] <= cap_b]
        if under:
            selected=max(under,key=lambda x:(x[0],x[1]))[1]
        elif configured_default and 4.0 <= configured_size <= cap_b:
            selected=configured_default
        else:
            sized=[x for x in choices if x[0] > 0]
            if cap_b < 12.0:
                # On constrained hardware the detected ceiling is a hard automatic limit.
                # If no sized model fits, leave routing unresolved rather than silently
                # selecting an oversized model. Manual selections remain unrestricted.
                selected=''
            elif sized:
                # Preserve the previous >32 GB behavior: if every installed model is above
                # the normal 12B ceiling, choose the smallest one rather than the largest.
                selected=min(sized,key=lambda x:(x[0],x[1]))[1]
            else:
                selected=configured_default or (choices[0][1] if choices else '')
    _AUTO_OLLAMA_CACHE.update({'at':now,'default':configured_default,'model':selected,'cap_b':cap_b})
    return selected


def _current_discovery_mode():
    try:
        return PortalSettings.objects.get_or_create(pk=1)[0].discovery_mode
    except Exception:
        return 'source_guided'


def _local_route_for_stage(stage):
    """Resolve a Local AI Discovery stage through Ollama only.

    Older releases allowed Cloud models in the stage table. Those saved values are kept
    for upgrade safety but ignored while Local AI Discovery is active. A saved local fallback
    is promoted when it is the only local choice available.
    """
    route=(_shared_routes().get(stage) or {}).copy()
    defaults=stage_defaults(stage)
    route.setdefault('max_input_tokens',defaults['max_input_tokens'])
    route.setdefault('max_output_tokens',defaults['max_output_tokens'])
    oll=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
    if not oll:
        return {}
    provider=str(route.get('provider') or '').strip().lower()
    fallback_provider=str(route.get('fallback_provider') or '').strip().lower()
    if provider=='ollama':
        route['model']=str(route.get('model') or '').strip() or _automatic_ollama_model(oll.default_model)
        if fallback_provider!='ollama':
            route.pop('fallback_provider',None); route.pop('fallback_model',None)
        route['execution_mode']='local'
        return route
    if fallback_provider=='ollama' and route.get('fallback_model'):
        route['provider']='ollama'; route['model']=route.get('fallback_model')
        route.pop('fallback_provider',None); route.pop('fallback_model',None)
        route['execution_mode']='local'
        return route
    return {
        'provider':'ollama','model':_automatic_ollama_model(oll.default_model),'execution_mode':'local',
        'max_input_tokens':route.get('max_input_tokens',defaults['max_input_tokens']),
        'max_output_tokens':route.get('max_output_tokens',defaults['max_output_tokens']),
    }


def _cloud_lane_for_stage(stage):
    """Cloud Web stages start on their configured Primary; Failover is error-only."""
    return 'primary'


def route_for_stage(stage):
    # Chatbot remains independently configurable and does not follow Discovery Method.
    # Unlike pipeline stages, its optional secondary route is explicit and chatbot-only:
    # it is used only after the saved primary provider/model fails.
    if stage=='chatbot':
        route=(_shared_routes().get(stage) or {}).copy()
        provider=str(route.get('provider') or '').strip().lower()
        model=str(route.get('model') or '').strip()
        if not provider or not model:
            return {}
        cfg=AIProviderConfig.objects.filter(provider=provider,enabled=True).first()
        if not cfg:
            return {}
        defaults=stage_defaults(stage)
        route['provider']=provider; route['model']=model
        route['execution_mode']='local' if provider=='ollama' else 'cloud'
        route.setdefault('max_input_tokens',defaults['max_input_tokens'])
        route.setdefault('max_output_tokens',defaults['max_output_tokens'])
        fallback_provider=str(route.get('fallback_provider') or '').strip().lower()
        fallback_model=str(route.get('fallback_model') or '').strip()
        fallback_cfg=AIProviderConfig.objects.filter(provider=fallback_provider,enabled=True).first() if fallback_provider else None
        if fallback_provider and fallback_model and fallback_cfg:
            route['fallback_provider']=fallback_provider
            route['fallback_model']=fallback_model
            route['fallback_execution_mode']='local' if fallback_provider=='ollama' else 'cloud'
            route['fallback_allow_internet_search']=bool(route.get('fallback_allow_internet_search')) and fallback_provider in {'openai','gemini','openrouter'}
        else:
            route.pop('fallback_provider',None); route.pop('fallback_model',None)
            route.pop('fallback_execution_mode',None); route.pop('fallback_allow_internet_search',None)
        route['allow_internet_search']=bool(route.get('allow_internet_search')) and provider in {'openai','gemini','openrouter'}
        return route

    if _current_discovery_mode()=='cloud_web':
        route=cloud_discovery_route('primary',stage=stage)
        return route

    return _local_route_for_stage(stage)


def effective_route_for_stage(stage, discovery_mode=None):
    """Return the route that actually owns a stage under the selected Discovery Method."""
    if discovery_mode is None:
        discovery_mode=_current_discovery_mode()
    if stage=='chatbot':
        return route_for_stage(stage)
    if discovery_mode=='cloud_web':
        return cloud_discovery_route('primary',stage=stage)
    return _local_route_for_stage(stage)


def _attachment_log_items(attachments):
    out=[]
    for item in attachments or []:
        try:
            if isinstance(item,dict):
                name=str(item.get('name') or item.get('filename') or 'attachment')[:255]
                size=int(item.get('size') or item.get('bytes') or 0)
            else:
                name=str(getattr(item,'name','attachment') or 'attachment')[:255]
                size=int(getattr(item,'size',0) or 0)
            out.append({'name':name,'size':max(0,size)})
        except Exception:
            continue
    return out


def _expects_structured_json(prompt):
    return bool(re.search(r'(?i)return\s+(?:json\s+only|only\s+json)|one\s+complete\s+json\s+object',str(prompt or '')))


def _complete_structured_json_payload(text):
    """Return one complete JSON object/list plus extraction metadata, or ``None``.

    A structured provider is allowed to wrap the requested value in a Markdown JSON fence.
    If it also writes explanatory prose outside that fence, the fenced value remains
    unambiguous and can be safely extracted. Arbitrary JSON-looking substrings in prose are
    deliberately *not* extracted.
    """
    raw=str(text or '').strip()
    if not raw:
        return None
    try:
        parsed=json.loads(raw)
        if isinstance(parsed,(dict,list)):
            return {'text':raw,'value':parsed,'source':'raw','discarded_non_json_text':False}
    except Exception:
        pass

    valid=[]
    for match in re.finditer(r'```(?:json)?\s*(.*?)\s*```',raw,re.I|re.S):
        candidate=match.group(1).strip()
        try:
            parsed=json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed,(dict,list)):
            valid.append((match,candidate,parsed))
    # Multiple independently valid fenced values are ambiguous for a prompt that requested
    # one structured value. Refuse to choose between them.
    if len(valid)!=1:
        return None
    match,candidate,parsed=valid[0]
    outside=(raw[:match.start()]+raw[match.end():]).strip()
    return {
        'text':candidate,
        'value':parsed,
        'source':'fence',
        'discarded_non_json_text':bool(outside),
    }


def _structured_json_complete(text):
    """Return True when the response contains one unambiguous complete JSON object/list."""
    return _complete_structured_json_payload(text) is not None


def _unwrap_structured_json_text(text):
    """Remove only a leading Markdown JSON fence for truncated-response recovery.

    A complete fenced payload is handled by ``_complete_structured_json_payload`` first.
    Here we support the common truncated form where the opening fence exists but the closing
    fence was never emitted. If a closing fence exists with non-whitespace text after it, the
    payload is left untouched rather than guessing which text belongs to JSON.
    """
    raw=str(text or '').strip()
    opening=re.match(r'^```(?:json)?\s*',raw,re.I)
    if not opening:
        return raw
    body=raw[opening.end():]
    close=body.find('```')
    if close<0:
        return body.strip()
    if body[close+3:].strip():
        return raw
    return body[:close].strip()


def _safe_incomplete_json_scalar_tail(text):
    """Return True only when *text* can safely be interpreted as an EOF-cut scalar.

    Recovery never completes or invents the scalar. This helper merely decides whether the
    caller may discard that final unfinished value and keep earlier complete data.
    """
    tail=str(text or '').strip()
    if not tail:
        return True
    if tail.startswith('"'):
        escaped=False
        unicode_left=0
        i=1
        while i<len(tail):
            ch=tail[i]
            if unicode_left:
                if ch not in '0123456789abcdefABCDEF':
                    return False
                unicode_left-=1
                i+=1
                continue
            if escaped:
                if ch=='u':
                    unicode_left=4
                elif ch not in '"\\/bfnrt':
                    return False
                escaped=False
                i+=1
                continue
            if ch=='\\':
                escaped=True
            elif ch=='"':
                # A closing quote means this is not merely an unfinished string tail; any
                # following malformed syntax must be handled as malformed JSON, not repaired.
                return False
            i+=1
        return True
    if any(token.startswith(tail) and token!=tail for token in ('true','false','null')):
        return True
    # Permit only numeric prefixes that could become a valid JSON number by appending data.
    # Complete numbers are decoded before this helper is reached.
    return bool(re.fullmatch(r'-|(?:-?(?:0|[1-9]\d*)\.)|(?:-?(?:0|[1-9]\d*)[eE][+-]?)',tail))


def _recover_json_prefix_value(raw,pos,decoder):
    """Recursive JSON-prefix parser used only for conservative EOF recovery."""
    n=len(raw)
    while pos<n and raw[pos].isspace():
        pos+=1
    if pos>=n:
        return {'state':'incomplete','end':n,'dropped':1,'closed':0,'nested_recovery':False}
    if raw[pos]=='{':
        return _recover_json_prefix_object(raw,pos,decoder)
    if raw[pos]=='[':
        return _recover_json_prefix_array(raw,pos,decoder)
    try:
        value,end=decoder.raw_decode(raw,pos)
    except Exception:
        if _safe_incomplete_json_scalar_tail(raw[pos:]):
            return {'state':'incomplete','end':n,'dropped':1,'closed':0,'nested_recovery':False}
        return {'state':'fail','end':pos,'dropped':0,'closed':0,'nested_recovery':False}
    # ``raw_decode`` accepts the longest valid prefix of a number. At EOF a cut numeric
    # scalar such as ``2.`` or ``2e+`` would otherwise look like the complete value ``2``
    # followed by malformed syntax. Treat the whole EOF tail as unfinished only when it is
    # itself a valid *prefix* of a JSON scalar; the parent will discard it rather than guess.
    if end<n and not raw[end].isspace() and raw[end] not in ',]}':
        if _safe_incomplete_json_scalar_tail(raw[pos:]):
            return {'state':'incomplete','end':n,'dropped':1,'closed':0,'nested_recovery':False}
        return {'state':'fail','end':end,'dropped':0,'closed':0,'nested_recovery':False}
    return {'state':'complete','value':value,'end':end,'dropped':0,'closed':0,'nested_recovery':False}


def _recover_json_prefix_array(raw,pos,decoder):
    n=len(raw); pos+=1; items=[]; dropped=0; closed=0; nested=False; expect_value=True
    while True:
        while pos<n and raw[pos].isspace():
            pos+=1
        if pos>=n:
            # ``[`` or ``[value`` reached EOF. An empty newly opened container has no
            # completed information and should be discarded by its parent rather than kept.
            if not items:
                return {'state':'incomplete','end':n,'dropped':max(1,dropped),'closed':closed,'nested_recovery':nested}
            return {'state':'recovered','value':items,'end':n,'dropped':dropped,'closed':closed+1,'nested_recovery':True}
        if expect_value:
            if raw[pos]==']':
                return {'state':'complete','value':items,'end':pos+1,'dropped':dropped,'closed':closed,'nested_recovery':nested}
            child=_recover_json_prefix_value(raw,pos,decoder)
            if child['state']=='fail':
                return child
            if child['state']=='incomplete':
                if not items:
                    return {'state':'incomplete','end':n,'dropped':dropped+max(1,int(child.get('dropped') or 0)),'closed':closed+int(child.get('closed') or 0),'nested_recovery':nested or bool(child.get('nested_recovery'))}
                return {'state':'recovered','value':items,'end':n,'dropped':dropped+max(1,int(child.get('dropped') or 0)),'closed':closed+int(child.get('closed') or 0)+1,'nested_recovery':True}
            items.append(child['value']); pos=int(child['end'])
            dropped+=int(child.get('dropped') or 0); closed+=int(child.get('closed') or 0)
            nested=nested or child['state']=='recovered' or bool(child.get('nested_recovery'))
            if child['state']=='recovered' and pos>=n:
                return {'state':'recovered','value':items,'end':n,'dropped':dropped,'closed':closed+1,'nested_recovery':True}
            expect_value=False
            continue
        if raw[pos]==',':
            pos+=1; expect_value=True; continue
        if raw[pos]==']':
            return {'state':'complete','value':items,'end':pos+1,'dropped':dropped,'closed':closed,'nested_recovery':nested}
        return {'state':'fail','end':pos,'dropped':dropped,'closed':closed,'nested_recovery':nested}


def _recover_json_prefix_object(raw,pos,decoder):
    n=len(raw); pos+=1; value={}; dropped=0; closed=0; nested=False; expect_key=True
    while True:
        while pos<n and raw[pos].isspace():
            pos+=1
        if pos>=n:
            if not value:
                return {'state':'incomplete','end':n,'dropped':max(1,dropped),'closed':closed,'nested_recovery':nested}
            return {'state':'recovered','value':value,'end':n,'dropped':dropped,'closed':closed+1,'nested_recovery':True}
        if expect_key:
            if raw[pos]=='}':
                return {'state':'complete','value':value,'end':pos+1,'dropped':dropped,'closed':closed,'nested_recovery':nested}
            try:
                key,key_end=decoder.raw_decode(raw,pos)
            except Exception:
                if _safe_incomplete_json_scalar_tail(raw[pos:]) and value:
                    return {'state':'recovered','value':value,'end':n,'dropped':dropped+1,'closed':closed+1,'nested_recovery':True}
                return {'state':'fail','end':pos,'dropped':dropped,'closed':closed,'nested_recovery':nested}
            if not isinstance(key,str):
                return {'state':'fail','end':pos,'dropped':dropped,'closed':closed,'nested_recovery':nested}
            pos=key_end
            while pos<n and raw[pos].isspace():
                pos+=1
            if pos>=n:
                if value:
                    return {'state':'recovered','value':value,'end':n,'dropped':dropped+1,'closed':closed+1,'nested_recovery':True}
                return {'state':'incomplete','end':n,'dropped':dropped+1,'closed':closed,'nested_recovery':nested}
            if raw[pos]!=':':
                return {'state':'fail','end':pos,'dropped':dropped,'closed':closed,'nested_recovery':nested}
            pos+=1
            child=_recover_json_prefix_value(raw,pos,decoder)
            if child['state']=='fail':
                return child
            if child['state']=='incomplete':
                if not value:
                    return {'state':'incomplete','end':n,'dropped':dropped+max(1,int(child.get('dropped') or 0)),'closed':closed+int(child.get('closed') or 0),'nested_recovery':nested or bool(child.get('nested_recovery'))}
                return {'state':'recovered','value':value,'end':n,'dropped':dropped+max(1,int(child.get('dropped') or 0)),'closed':closed+int(child.get('closed') or 0)+1,'nested_recovery':True}
            value[key]=child['value']; pos=int(child['end'])
            dropped+=int(child.get('dropped') or 0); closed+=int(child.get('closed') or 0)
            nested=nested or child['state']=='recovered' or bool(child.get('nested_recovery'))
            if child['state']=='recovered' and pos>=n:
                return {'state':'recovered','value':value,'end':n,'dropped':dropped,'closed':closed+1,'nested_recovery':True}
            expect_key=False
            continue
        if raw[pos]==',':
            pos+=1; expect_key=True; continue
        if raw[pos]=='}':
            return {'state':'complete','value':value,'end':pos+1,'dropped':dropped,'closed':closed,'nested_recovery':nested}
        return {'state':'fail','end':pos,'dropped':dropped,'closed':closed,'nested_recovery':nested}


def _recover_truncated_json_value(text):
    """Conservatively salvage completed data from an EOF-truncated JSON object or array.

    Recovery is recursive, so nested objects/arrays can be closed safely. An unfinished
    scalar is never completed: that value (and only that value) is discarded. Unexpected
    syntax before EOF aborts recovery instead of being guessed around.
    """
    source=str(text or '').strip()
    raw=_unwrap_structured_json_text(source)
    # If the model closed a single Markdown fence around incomplete JSON and then added
    # prose, the fence still unambiguously identifies the structured payload. Recover only
    # that one fenced body; never choose between multiple fenced candidates.
    if raw==source:
        fences=list(re.finditer(r'```(?:json)?\s*(.*?)\s*```',source,re.I|re.S))
        if len(fences)==1:
            candidate=fences[0].group(1).strip()
            if candidate[:1] in '[{':
                raw=candidate
    if not raw or raw[0] not in '[{':
        return None
    try:
        json.loads(raw)
        return None
    except Exception:
        pass
    result=_recover_json_prefix_value(raw,0,json.JSONDecoder())
    if result.get('state')!='recovered' or int(result.get('end') or 0)!=len(raw):
        return None
    recovered=result.get('value')
    if not isinstance(recovered,(dict,list)) or not recovered:
        return None
    corrected=json.dumps(recovered,ensure_ascii=False,indent=2,default=str)
    try:
        json.loads(corrected)
    except Exception:
        return None
    top_count=len(recovered)
    wrapper_key=''
    if isinstance(recovered,dict) and len(recovered)==1:
        key,next_value=next(iter(recovered.items()))
        if isinstance(next_value,list):
            wrapper_key=str(key); top_count=len(next_value)
    return {
        'text':corrected,
        'top_level_type':'array' if isinstance(recovered,list) else 'object',
        'values_kept':len(recovered),
        'items_kept':top_count,
        'wrapper_key':wrapper_key,
        'dropped_trailing_value':bool(int(result.get('dropped') or 0)),
        'dropped_trailing_item':bool(int(result.get('dropped') or 0)),
        'discarded_value_count':int(result.get('dropped') or 0),
        'closed_container_count':int(result.get('closed') or 0),
        'recovered_nested_container':bool(result.get('nested_recovery')),
        # Backward-compatible metadata keys retained for the AI Requests detail view.
        'recovered_partial_item':False,
        'partial_item_fields_kept':0,
    }


def _recover_truncated_json_list(text):
    """Backward-compatible name for the now general object/array recovery routine."""
    return _recover_truncated_json_value(text)


def _ollama_response_metadata(raw,limits=None):
    """Normalize Ollama stop metadata and infer old-server output-cap truncation."""
    data=raw if isinstance(raw,dict) else {}
    limits=dict(limits or {})
    reason=str(data.get('done_reason') or data.get('stop_reason') or '').strip()
    reason_low=reason.lower()
    try:
        cap=max(0,int(limits.get('max_output_tokens') or 0))
    except Exception:
        cap=0
    try:
        output_tokens=max(0,int(data.get('eval_count') or 0))
    except Exception:
        output_tokens=0
    cap_reached=bool(cap and output_tokens>=cap)
    explicit_length=reason_low in {'length','max_tokens','max_token','token_limit','num_predict'}
    explicit_stop=reason_low in {'stop','eos','end_turn','complete','completed'}
    # Older Ollama releases may omit done_reason. Reaching num_predict exactly is then the
    # only provider-side signal available that generation was capped.
    truncated=bool(explicit_length or (cap_reached and not explicit_stop))
    return {
        'finish_reason':reason,
        'configured_max_output_tokens':cap or None,
        'response_token_limit_reached':cap_reached,
        'response_truncated':truncated,
    }


def _prepare_structured_response(prompt,text,request_metadata=None):
    """Return canonical usable JSON plus recovery metadata when it can be salvaged safely."""
    meta=dict(request_metadata or {})
    raw=str(text or '')
    if not _expects_structured_json(prompt) or not raw.strip():
        return raw,meta,''

    provider_truncated=bool(meta.get('response_truncated'))
    complete=_complete_structured_json_payload(raw)
    if complete:
        corrected=str(complete.get('text') or '')
        discarded=bool(complete.get('discarded_non_json_text'))
        fenced=str(complete.get('source') or '')=='fence'
        if discarded or provider_truncated:
            parsed=complete.get('value')
            kept=len(parsed) if isinstance(parsed,(dict,list)) else 0
            if discarded:
                detail='Recovered one complete JSON payload from a Markdown fence and discarded non-JSON text outside the fence.'
            else:
                detail='Provider reported an output-token stop, but the returned JSON is syntactically complete; ScoutBox kept the usable payload.'
            meta.update({
                'response_recovered':True,
                'response_incomplete':False,
                'response_issue_code':'recovered_structured_response',
                'response_issue_detail':detail,
                'recovered_item_count':kept,
                'discarded_non_json_text':discarded,
                'extracted_fenced_json':fenced,
                'discarded_incomplete_trailing_item':False,
            })
            return corrected,meta,raw
        if fenced:
            # A plain fence is only presentation noise: normalize it for every downstream
            # parser without inflating the warning/recovery count.
            meta.update({'response_normalized':True,'extracted_fenced_json':True,'response_incomplete':False})
            return corrected,meta,raw
        return corrected,meta,''

    recovery=_recover_truncated_json_value(raw)
    if recovery:
        corrected=str(recovery.get('text') or '')
        kept=int(recovery.get('items_kept') or recovery.get('values_kept') or 0)
        discarded=int(recovery.get('discarded_value_count') or 0)
        closed=int(recovery.get('closed_container_count') or 0)
        detail=(
            f'Recovered a truncated JSON {recovery.get("top_level_type") or "value"} with {kept} complete '
            f'value{"" if kept==1 else "s"}; '
            + (f'discarded {discarded} unfinished trailing value{"" if discarded==1 else "s"} and ' if discarded else '')
            + f'safely closed {closed} JSON container{"" if closed==1 else "s"}.'
        )
        meta.update({
            'response_recovered':True,
            'response_incomplete':False,
            'response_issue_code':'recovered_structured_response',
            'response_issue_detail':detail,
            'recovered_item_count':kept,
            'recovery_wrapper_key':str(recovery.get('wrapper_key') or ''),
            'discarded_incomplete_trailing_item':bool(recovery.get('dropped_trailing_item')),
            'discarded_incomplete_value_count':discarded,
            'recovered_nested_container':bool(recovery.get('recovered_nested_container')),
            'closed_json_container_count':closed,
        })
        return corrected,meta,raw

    meta['response_incomplete']=True
    return raw,meta,''


def _write_ai_request_log(prompt, output, stage, provider, model, started_at, ok=True, error='', subject=None, attachments=None, tokens_in=None, tokens_out=None, reasoning_tokens=None, web_search_queries=None, request_metadata=None, raw_output_text=''):
    try:
        subject=subject or {}
        def exact_or_estimate(value, fallback):
            if value is None:
                return max(0,int(fallback or 0)), False
            try:
                return max(0,int(value)), True
            except (TypeError,ValueError):
                return max(0,int(fallback or 0)), False
        exact_in,in_reported=exact_or_estimate(tokens_in,_rough_tokens(prompt))
        exact_out,out_reported=exact_or_estimate(tokens_out,_rough_tokens(output))
        usage_source='provider_reported' if in_reported and out_reported else 'estimated'
        try: reasoning=max(0,int(reasoning_tokens or 0))
        except Exception: reasoning=0
        try: web_queries=max(0,int(web_search_queries or 0))
        except Exception: web_queries=0
        try:
            duration_ms=max(0,int((timezone.now()-started_at).total_seconds()*1000)) if started_at else None
        except Exception:
            duration_ms=None
        empty_output_issue=isinstance(error,AIEmptyOutputWarning) or (bool(ok) and bool(str(provider or '').strip()) and not str(output or '').strip())
        request_meta=dict(request_metadata or {})
        provider_truncated=bool(request_meta.get('response_truncated'))
        malformed_structured=bool(
            bool(ok) and str(output or '').strip() and _expects_structured_json(prompt)
            and not _structured_json_complete(output)
        )
        recovered_response=bool(request_meta.get('response_recovered'))
        malformed_response=bool((provider_truncated or request_meta.get('response_incomplete') or malformed_structured) and not recovered_response)
        if empty_output_issue:
            request_status='empty_response'
        elif recovered_response:
            request_status='recovered_response'
        elif malformed_response:
            request_status='malformed_response'
        else:
            request_status='completed' if bool(ok) else 'failed'
        log_error='' if (empty_output_issue or recovered_response or malformed_response) else str(error or '')[:4000]
        meta={'input_truncated_by_log':False,'token_usage_source':usage_source, **request_meta}
        if empty_output_issue:
            meta['warning_code']=EMPTY_OUTPUT_WARNING_CODE
            meta['warning_detail']=EMPTY_OUTPUT_WARNING_DETAIL
            meta['response_issue_code']='empty_output'
            meta['response_issue_detail']=EMPTY_OUTPUT_WARNING_DETAIL
        elif recovered_response:
            detail=str(meta.get('response_issue_detail') or 'ScoutBox recovered complete items from a truncated structured response and discarded the incomplete trailing fragment.')
            meta['warning_code']='recovered_structured_response'
            meta['warning_detail']=detail
            meta['response_issue_code']='recovered_structured_response'
            meta['response_issue_detail']=detail
            meta['response_incomplete']=False
        elif malformed_response:
            detail=(
                'Provider stopped at its output-token limit and ScoutBox could not safely recover a valid structured payload. The configured retry/failover route can be used.'
                if provider_truncated else
                'The model returned malformed or incomplete structured JSON that ScoutBox could not safely recover. The configured retry/failover route can be used.'
            )
            meta['warning_code']='malformed_structured_response'
            meta['warning_detail']=detail
            meta['response_issue_code']='malformed_structured_response'
            meta['response_issue_detail']=detail
            meta['response_incomplete']=True
        AIRequestLog.objects.create(
            status=request_status, provider=provider or '',model=model or '',stage=stage or '',runtime='local' if provider=='ollama' else 'cloud',
            subject_type=str(subject.get('type') or 'task')[:60],subject_id=str(subject.get('id') or '')[:120],
            subject_label=str(subject.get('label') or stage or 'AI task')[:300],input_text=str(prompt or ''),output_text=str(output or ''),raw_output_text=str(raw_output_text or ''),
            attachments=_attachment_log_items(attachments),tokens_in=exact_in,tokens_out=exact_out,reasoning_tokens=reasoning,web_search_queries=web_queries,token_usage_source=usage_source,duration_ms=duration_ms,
            ok=bool(ok) and not empty_output_issue and not malformed_response,error=log_error,metadata=usage_metadata(meta),
        )
    except Exception:
        # Logging must never break the model request itself.
        pass


def generate_with_route(route, prompt, stage='general', timeout=None, subject=None, attachments=None, limits_override=None):
    """Execute one explicit Primary/Fallback route without inventing a model.

    Cloud structured responses are validated before they are accepted. A provider-native
    truncation or malformed JSON-only payload gets one larger-cap retry on the same model;
    if it is still unusable, the configured failover model is attempted. Local Ollama
    does not use the Cloud retry loop, but it shares the same structured-output normalization
    and conservative recovery before task code receives the response.
    """
    route=dict(route or {})
    provider=str(route.get('provider') or '').strip().lower()
    model=str(route.get('model') or '').strip()
    if not provider or not model:
        raise RuntimeError('No explicit AI provider/model route is configured')

    rate_state={'waited':0}
    ctx=usage_context()
    forum_only=bool(ctx.get('forum_only'))
    disable_fallback=bool((subject or {}).get('disable_ai_fallback') if isinstance(subject,dict) else False) or bool(ctx.get('disable_ai_fallback') or ctx.get('maintenance_hidden_lead_reassessment'))

    def execute(selected_provider,selected_model):
        if not is_cloud_provider(selected_provider):
            return generate_with(selected_provider,selected_model,prompt,stage,timeout,subject=subject,attachments=attachments,limits_override=limits_override)
        base_limits=dict(limits_override or token_limits_for_stage(stage,provider=selected_provider))
        def _initial_call():
            return generate_with(selected_provider,selected_model,prompt,stage,timeout,subject=subject,attachments=attachments,limits_override=base_limits,return_debug=True)
        try:
            text,debug=_cloud_campaign_call_with_backoff(_initial_call,selected_provider,selected_model,stage,rate_state)
        except AIEmptyOutputWarning:
            if forum_only or selected_provider!='gemini':
                raise
            def _gemini_empty_retry_call():
                return generate_with(
                    selected_provider,selected_model,prompt,stage,timeout,subject=subject,attachments=attachments,
                    limits_override=base_limits,config_override={'_manual_empty_retry_minimal':True,'_manual_disable_json_mime':True},return_debug=True,
                )
            text,debug=_cloud_campaign_call_with_backoff(_gemini_empty_retry_call,selected_provider,selected_model,stage,rate_state)
            debug=dict(debug or {}); debug['empty_output_retry']=True; debug['empty_output_retry_mode']='minimal_thinking_no_json_mime'
        issue=_cloud_web_structured_issue(prompt,text,debug)
        if issue and not forum_only:
            current=max(64,int(base_limits.get('max_output_tokens') or CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general'])['max_output_tokens']))
            expanded=min(CLOUD_HARD_MAX_OUTPUT,max(current+1800,int(current*1.75)))
            if expanded>current:
                retry_limits=dict(base_limits); retry_limits['max_output_tokens']=expanded
                def _structured_retry_call():
                    return generate_with(selected_provider,selected_model,prompt,stage,timeout,subject=subject,attachments=attachments,limits_override=retry_limits,return_debug=True)
                text,debug=_cloud_campaign_call_with_backoff(_structured_retry_call,selected_provider,selected_model,stage,rate_state)
                issue=_cloud_web_structured_issue(prompt,text,debug)
        if issue:
            suffix=' without retry (Forum throughput isolation)' if forum_only else ' after structured-output retry'
            raise RuntimeError(f'{selected_provider} {selected_model}: {issue}{suffix}')
        return text

    try:
        return execute(provider,model)
    except Exception:
        if forum_only or disable_fallback:
            raise
        fallback_provider=str(route.get('fallback_provider') or '').strip().lower()
        fallback_model=str(route.get('fallback_model') or '').strip()
        if fallback_provider and fallback_model and (fallback_provider,fallback_model)!=(provider,model):
            return execute(fallback_provider,fallback_model)
        raise


def generate(prompt, stage='general', provider=None, model=None, timeout=None, subject=None, attachments=None):
    route=route_for_stage(stage) if not provider else {'provider':provider,'model':model or ''}
    if not route:
        raise RuntimeError('No AI provider is configured')
    return generate_with_route(route,prompt,stage,timeout,subject=subject,attachments=attachments)

def stage_routes_with_defaults(existing=None):
    """Fill missing route/cap fields for display without overwriting saved caps."""
    existing=existing or {}
    routes={}
    for stage in STAGES:
        old=(existing.get(stage) or {}).copy()
        d=stage_defaults(stage)
        old.setdefault('max_input_tokens',d['max_input_tokens'])
        old.setdefault('max_output_tokens',d['max_output_tokens'])
        routes[stage]=old
    return routes


def default_stage_routes(existing=None):
    """Return a route map with sensible token defaults while preserving chosen models."""
    existing=existing or {}
    routes={}
    for stage in STAGES:
        old=(existing.get(stage) or {}).copy()
        d=stage_defaults(stage)
        old['max_input_tokens']=d['max_input_tokens']
        old['max_output_tokens']=d['max_output_tokens']
        routes[stage]=old
    return routes



def web_search_with(provider, model, prompt, stage='url_scrape', timeout=None, limits_override=None, budget_operation='', config_override=None, subject=None):
    """Cloud-native search/grounding with hard ScoutBox budget enforcement."""
    timeout=_forum_request_timeout(provider,ai_request_timeout(provider,stage))
    if str(usage_context().get('discovery_mode') or '').lower()=='source_guided':
        raise RuntimeError('Local AI Discovery routing violation: Cloud Web research is not permitted for this campaign run.')
    if provider not in ('openai','gemini','openrouter'):
        raise RuntimeError('Cloud web research requires OpenAI, Gemini, or OpenRouter.')
    cfg=AIProviderConfig.objects.filter(provider=provider).first()
    override=dict(config_override or {})
    enabled=bool(override.get('enabled', cfg.enabled if cfg else False))
    if not cfg and not override: raise RuntimeError(f'{provider} is not configured')
    if not enabled: raise RuntimeError(f'{provider} is not enabled')
    key=str(override.get('api_key') or '') if 'api_key' in override else (decrypt(cfg.api_key_enc) if cfg else '')
    if not key: raise RuntimeError(f'{provider} API key is not configured')
    model=model or (cfg.default_model if cfg else '')
    if not model: raise RuntimeError(f'{provider} default model is not configured')
    limits=dict(limits_override or token_limits_for_stage(stage,provider=provider))
    if bool(usage_context().get('forum_only')):
        # One best-effort Forum web-research call gets a smaller bounded token envelope.
        limits['max_input_tokens']=min(int(limits.get('max_input_tokens') or 3500),3500)
        limits['max_output_tokens']=min(int(limits.get('max_output_tokens') or 1800),1800)
    if limits.get('max_input_tokens'): limits['max_input_tokens']=min(CLOUD_HARD_MAX_INPUT,int(limits['max_input_tokens']))
    if limits.get('max_output_tokens'): limits['max_output_tokens']=min(CLOUD_HARD_MAX_OUTPUT,int(limits['max_output_tokens']))
    provider_cap=override.get('max_output_tokens') if 'max_output_tokens' in override else (cfg.max_output_tokens if cfg else None)
    if provider_cap:
        stage_cap=limits.get('max_output_tokens'); limits['max_output_tokens']=min(stage_cap,int(provider_cap)) if stage_cap else min(CLOUD_HARD_MAX_OUTPUT,int(provider_cap))
    expect_json=bool(re.search(r'(?i)return\s+(?:json\s+only|only\s+json)|one\s+complete\s+json\s+object',str(prompt or '')))
    prompt,truncated,estimated_input=_trim_prompt(prompt,limits.get('max_input_tokens'))
    cap_meta={'configured_max_input_tokens':limits.get('max_input_tokens'),'configured_max_output_tokens':limits.get('max_output_tokens'),'input_was_truncated':truncated,'estimated_input_tokens_after_cap':estimated_input,'web_search':True,'request_timeout_seconds':timeout}
    operation=budget_operation or usage_context().get('operation') or 'cloud_discovery'
    reservation=reserve_cloud(provider=provider,requests=1,web_searches=1,tokens_in=estimated_input,tokens_out=int(limits.get('max_output_tokens') or 0),operation=operation)
    started_at=timezone.now(); started=time.time(); _ctx=usage_context(); audit_subject=(dict(subject) if isinstance(subject,dict) else {'type':'campaign' if _ctx.get('campaign_id') else 'task','id':str(_ctx.get('campaign_id') or 'cloud-web-research'),'label':str(_ctx.get('campaign_label') or 'Cloud web research')}); audit_subject['budget_operation']=operation
    try:
        if provider=='openai':
            base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://api.openai.com/v1').rstrip('/'); payload={'model':model,'input':prompt,'tools':[{'type':'web_search'}]}
            if limits.get('max_output_tokens'): payload['max_output_tokens']=limits['max_output_tokens']
            r=requests.post(base+'/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json=payload,timeout=timeout); r.raise_for_status(); data=r.json(); text=_openai_text(data); _require_visible_output(text); usage=data.get('usage') or {}; sources=[]
            for item in data.get('output',[]):
                if item.get('type')=='web_search_call':
                    for src in (item.get('action') or {}).get('sources') or []:
                        if src.get('url'): sources.append(src['url'])
            reported_web_queries=sum(1 for item in data.get('output',[]) if item.get('type')=='web_search_call'); web_calls=max(1,reported_web_queries); reasoning=((usage.get('output_tokens_details') or {}).get('reasoning_tokens') or 0)
            _record('openai',model,stage,started,usage.get('input_tokens',0),usage.get('output_tokens',0),metadata={**cap_meta,'query':prompt[:500],'response_id':data.get('id',''),'web_sources':sources[:100],'web_queries_count':web_calls,'provider_reported_web_queries':reported_web_queries,'reasoning_tokens':reasoning})
            reconcile_cloud(reservation,actual_tokens_in=usage.get('input_tokens',0),actual_tokens_out=usage.get('output_tokens',0),reasoning_tokens=reasoning,actual_web_searches=web_calls)
            request_meta={'finish_reason':str(data.get('status') or ''),'configured_max_output_tokens':limits.get('max_output_tokens'),'response_truncated':str(data.get('status') or '').lower() in {'incomplete','truncated'}}
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'openai',model,started_at,True,subject=audit_subject,tokens_in=usage.get('input_tokens'),tokens_out=usage.get('output_tokens'),reasoning_tokens=reasoning,web_search_queries=web_calls,request_metadata={**request_meta,'provider_reported_web_queries':reported_web_queries},raw_output_text=raw_output)
            return text,{'provider':'openai','model':model,'sources':sources,'queries_count':reported_web_queries,'budget_search_units':web_calls,'raw':data,**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
        if provider=='openrouter':
            base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://openrouter.ai/api/v1').rstrip('/'); payload={'model':model,'messages':[{'role':'user','content':prompt}],'tools':[{'type':'openrouter:web_search','parameters':{'max_results':5,'max_total_results':15}},{'type':'openrouter:web_fetch','parameters':{'max_content_tokens':12000}}],'max_tool_calls':8}
            if limits.get('max_output_tokens'): payload['max_tokens']=limits['max_output_tokens']
            r=requests.post(base+'/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','X-Title':'ScoutBox'},json=payload,timeout=timeout)
            if r.status_code>=400:
                # Compatibility fallback for a model that cannot call the new server tools.
                payload.pop('tools',None); payload.pop('max_tool_calls',None); payload['plugins']=[{'id':'web','max_results':5}]
                r=requests.post(base+'/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','X-Title':'ScoutBox'},json=payload,timeout=timeout)
            r.raise_for_status(); data=r.json(); choice=(data.get('choices') or [{}])[0]; message=choice.get('message') or {}; text=str(message.get('content') or ''); _require_visible_output(text); usage=data.get('usage') or {}; reasoning=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0; reported_web_queries=int(usage.get('web_search_requests') or usage.get('web_searches') or usage.get('web_search_count') or 0); web_calls=max(1,reported_web_queries); sources=[]
            for ann in message.get('annotations') or []:
                if not isinstance(ann,dict): continue
                u=(ann.get('url_citation') or ann).get('url')
                if u: sources.append(u)
            actual_model=str(data.get('model') or model)
            _record('openrouter',actual_model,stage,started,usage.get('prompt_tokens',0),usage.get('completion_tokens',0),metadata={**cap_meta,'query':prompt[:500],'web_sources':sources[:100],'web_queries_count':web_calls,'provider_reported_web_queries':reported_web_queries,'reasoning_tokens':reasoning,'cost_usd':usage.get('cost')})
            reconcile_cloud(reservation,actual_tokens_in=usage.get('prompt_tokens',0),actual_tokens_out=usage.get('completion_tokens',0),reasoning_tokens=reasoning,actual_web_searches=web_calls,actual_cost_usd=usage.get('cost'))
            request_meta={'finish_reason':str(choice.get('finish_reason') or ''),'configured_max_output_tokens':limits.get('max_output_tokens'),'response_truncated':str(choice.get('finish_reason') or '').lower() in {'length','max_tokens'}}
            text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
            _write_ai_request_log(prompt,text,stage,'openrouter',actual_model,started_at,True,subject=audit_subject,tokens_in=usage.get('prompt_tokens'),tokens_out=usage.get('completion_tokens'),reasoning_tokens=reasoning,web_search_queries=web_calls,request_metadata={**request_meta,'provider_reported_web_queries':reported_web_queries},raw_output_text=raw_output)
            return text,{'provider':'openrouter','model':actual_model,'sources':sources,'queries_count':reported_web_queries,'budget_search_units':web_calls,'raw':data,**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
        base=(override.get('base_url') or (cfg.base_url if cfg else '') or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/'); payload={'contents':[{'parts':[{'text':prompt}]}],'tools':[{'google_search':{}}]}
        generation={}
        if limits.get('max_output_tokens'): generation['maxOutputTokens']=limits['max_output_tokens']
        thinking_extra,thinking_mode=_gemini_thinking_config(model,stage,override); generation.update(thinking_extra)
        if override.get('_manual_empty_retry_minimal') and str(model or '').lower().startswith('gemini-3'):
            generation['thinkingConfig']={'thinkingLevel':'minimal'}; thinking_mode='minimal'
        if expect_json and not override.get('_manual_disable_json_mime'):
            generation['responseMimeType']='application/json'
        if generation: payload['generationConfig']=generation
        r=requests.post(f'{base}/models/{model}:generateContent',headers={'x-goog-api-key':key,'Content-Type':'application/json'},json=payload,timeout=timeout); r.raise_for_status(); data=r.json(); chunks=[]; sources=[]; queries=[]
        candidates=data.get('candidates') or []
        for cand in candidates:
            for part in (cand.get('content') or {}).get('parts',[]):
                if part.get('text'): chunks.append(part['text'])
            gm=cand.get('groundingMetadata') or {}; queries.extend(gm.get('webSearchQueries') or [])
            for gc in gm.get('groundingChunks') or []:
                web=gc.get('web') or {}
                if web.get('uri'): sources.append(web['uri'])
        usage=data.get('usageMetadata') or {}; text='\n'.join(chunks); reasoning=usage.get('thoughtsTokenCount',0) or 0; reported_web_queries=len(queries); web_calls=max(1,reported_web_queries)
        finish_reasons=[str(c.get('finishReason') or '') for c in candidates if c.get('finishReason')]
        finish_messages=[str(c.get('finishMessage') or '')[:1000] for c in candidates if c.get('finishMessage')]
        _finish=','.join(finish_reasons)
        request_meta={
            'thinking_mode':thinking_mode,'web_queries':queries[:50],'finish_reason':_finish,
            'configured_max_output_tokens':limits.get('max_output_tokens'),
            'response_truncated':any(str(c.get('finishReason') or '').upper() in {'MAX_TOKENS','LENGTH'} for c in candidates),
            'provider_http_status':int(getattr(r,'status_code',0) or 0),
            'gemini_finish_reasons':finish_reasons[:10],
            'gemini_finish_messages':finish_messages[:10],
            'gemini_prompt_tokens':int(usage.get('promptTokenCount',0) or 0),
            'gemini_candidate_tokens':int(usage.get('candidatesTokenCount',0) or 0),
            'gemini_thought_tokens':int(reasoning or 0),
            'gemini_total_tokens':int(usage.get('totalTokenCount',0) or 0),
            'gemini_cached_content_tokens':int(usage.get('cachedContentTokenCount',0) or 0),
            'gemini_model_version':str(data.get('modelVersion') or '')[:200],
            'gemini_response_id':str(data.get('responseId') or '')[:300],
            'gemini_empty_retry':bool(override.get('_manual_empty_retry_minimal')),
            'gemini_json_mime_requested':bool(expect_json and not override.get('_manual_disable_json_mime')),
        }
        metric_meta={**cap_meta,'query':prompt[:500],'web_sources':sources[:100],'web_queries':queries[:50],'web_queries_count':web_calls,'provider_reported_web_queries':reported_web_queries,'reasoning_tokens':reasoning,'thinking_mode':thinking_mode,**request_meta}
        if not str(text or '').strip():
            # Preserve provider-reported accounting and finish diagnostics before raising.
            # Empty visible content can still consume prompt/thought/search resources.
            reconcile_cloud(reservation,actual_tokens_in=usage.get('promptTokenCount',0),actual_tokens_out=usage.get('candidatesTokenCount',0),reasoning_tokens=reasoning,actual_web_searches=web_calls)
            metric_meta.update({'warning_code':EMPTY_OUTPUT_WARNING_CODE,'warning_detail':EMPTY_OUTPUT_WARNING_DETAIL})
            _record('gemini',model,stage,started,usage.get('promptTokenCount',0),usage.get('candidatesTokenCount',0),error=False,metadata=metric_meta)
            warning=AIEmptyOutputWarning(EMPTY_OUTPUT_WARNING_DETAIL)
            warning.scoutbox_accounted=True
            warning.empty_attempts=1
            _write_ai_request_log(prompt,'',stage,'gemini',model,started_at,False,error=warning,subject=audit_subject,tokens_in=usage.get('promptTokenCount'),tokens_out=usage.get('candidatesTokenCount'),reasoning_tokens=reasoning,web_search_queries=web_calls,request_metadata={**request_meta,'provider_reported_web_queries':reported_web_queries})
            raise warning
        _record('gemini',model,stage,started,usage.get('promptTokenCount',0),usage.get('candidatesTokenCount',0),metadata=metric_meta)
        reconcile_cloud(reservation,actual_tokens_in=usage.get('promptTokenCount',0),actual_tokens_out=usage.get('candidatesTokenCount',0),reasoning_tokens=reasoning,actual_web_searches=web_calls)
        text,request_meta,raw_output=_prepare_structured_response(prompt,text,request_meta)
        _write_ai_request_log(prompt,text,stage,'gemini',model,started_at,True,subject=audit_subject,tokens_in=usage.get('promptTokenCount'),tokens_out=usage.get('candidatesTokenCount'),reasoning_tokens=reasoning,web_search_queries=web_calls,request_metadata={**request_meta,'provider_reported_web_queries':reported_web_queries},raw_output_text=raw_output)
        return text,{'provider':'gemini','model':model,'sources':sources,'queries':queries,'queries_count':reported_web_queries,'budget_search_units':web_calls,'raw':data,**{k:v for k,v in request_meta.items() if k.startswith('response_') or k.startswith('recovered_') or k.startswith('discarded_')}}
    except Exception as exc:
        if getattr(exc,'scoutbox_accounted',False):
            raise
        reconcile_cloud(reservation,actual_tokens_in=0,actual_tokens_out=0,actual_web_searches=0)
        empty_output_warning=isinstance(exc,AIEmptyOutputWarning)
        metric_meta={**cap_meta,'query':prompt[:500],'limit_reached':isinstance(exc,CloudLimitReached)}
        if empty_output_warning:
            metric_meta.update({'warning_code':EMPTY_OUTPUT_WARNING_CODE,'warning_detail':EMPTY_OUTPUT_WARNING_DETAIL})
        else:
            metric_meta['error']=str(exc)[:1000]
        _record(provider,model,stage,started,error=not empty_output_warning,metadata=metric_meta)
        _write_ai_request_log(prompt,'',stage,provider,model,started_at,False,error=exc,subject=audit_subject); raise

def cloud_discovery_route(lane='primary', stage='url_scrape'):
    """Return one explicit per-stage Cloud Web Primary/Failover route."""
    stage=stage if stage in _cloud_web_pipeline_stages() else 'url_scrape'
    routes=configured_cloud_web_routes(stage)
    if not routes:
        raise RuntimeError(f'Cloud Web Discovery needs an enabled Cloud provider and configured Primary model for {stage}.')
    lane=str(lane or 'primary').lower()
    chosen=next((r for r in routes if r[2]==lane),None) or routes[0]
    saved=dict(cloud_web_stage_routes().get(stage) or {})
    defaults=dict(CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general']))
    result={'provider':chosen[0],'model':chosen[1],'execution_mode':'cloud','automatic':False,'lane':chosen[2],
            'max_input_tokens':_safe_int(saved.get('max_input_tokens'),defaults['max_input_tokens']),
            'max_output_tokens':_safe_int(saved.get('max_output_tokens'),defaults['max_output_tokens'])}
    fallback=next((r for r in routes if r[2]!=chosen[2]),None)
    if fallback and fallback[0]==chosen[0]:
        result.update({'fallback_provider':fallback[0],'fallback_model':fallback[1],'fallback_execution_mode':'cloud'})
    return result


def _cloud_web_response_truncated(meta):
    """Return True when the provider explicitly stopped because output was capped."""
    meta=dict(meta or {})
    provider=str(meta.get('provider') or '').strip().lower()
    raw=meta.get('raw') if isinstance(meta.get('raw'),dict) else {}
    try:
        if provider=='gemini':
            return any(str(c.get('finishReason') or '').upper() in {'MAX_TOKENS','LENGTH'} for c in (raw.get('candidates') or []) if isinstance(c,dict))
        if provider=='openrouter':
            return any(str(c.get('finish_reason') or '').lower() in {'length','max_tokens'} for c in (raw.get('choices') or []) if isinstance(c,dict))
        if provider=='openai':
            return str(raw.get('status') or '').lower() in {'incomplete','truncated'}
    except Exception:
        return False
    return False


def _cloud_web_json_complete(text):
    """Compatibility wrapper for Cloud Discovery structured-output checks."""
    return _structured_json_complete(text)


def _cloud_web_structured_issue(prompt,text,meta):
    meta=dict(meta or {})
    if meta.get('response_recovered') and _cloud_web_json_complete(text):
        return ''
    if _cloud_web_response_truncated(meta):
        return 'provider response hit its output-token limit'
    if _expects_structured_json(prompt) and not _cloud_web_json_complete(text):
        return 'provider returned incomplete or malformed JSON'
    return ''


def cloud_web_search(prompt, timeout=180, route_lane=None, stage='url_scrape'):
    """Run web-grounded Cloud work with structured-output recovery and failover.

    A provider-native truncation or malformed JSON response is not a successful Discovery
    result. Retry the same model once with more output room, then move to the configured
    same-provider failover model. This prevents a green request log entry from silently
    turning into an empty Opportunity/Lead set.
    """
    lane=str(route_lane or usage_context().get('cloud_route_lane') or 'primary').lower()
    stage=str(stage or usage_context().get('bundle_anchor') or 'url_scrape')
    if stage not in _cloud_web_pipeline_stages():
        stage='url_scrape'
    routes=configured_cloud_web_routes(stage)
    if not routes:
        raise RuntimeError(f'Cloud Web Discovery has no configured route for {stage}.')
    ordered=[]
    preferred=next((r for r in routes if r[2]==lane),None)
    if preferred: ordered.append(preferred)
    ordered += [r for r in routes if r not in ordered]
    forum_only=bool(usage_context().get('forum_only'))
    if forum_only:
        # Forum is best-effort in Cloud mode: one route attempt only. Primary discovery
        # keeps retry/failover capacity, rate-limit budget, and the longer timeout.
        ordered=ordered[:1]
    last_error=None
    rate_state={'waited':0}
    for provider,model,_lane in ordered:
        base_limits=dict(token_limits_for_stage(stage,provider=provider))
        try:
            def _initial_web_call():
                return web_search_with(provider,model,prompt,stage,timeout,limits_override=base_limits)
            try:
                text,meta=_cloud_campaign_call_with_backoff(_initial_web_call,provider,model,stage,rate_state)
            except AIEmptyOutputWarning:
                # Normal primary Cloud discovery gets one targeted Gemini empty-output
                # recovery before route failover. Forum passes deliberately skip this retry
                # so supplementary acquisition cannot consume primary discovery throughput.
                if forum_only or provider!='gemini':
                    raise
                def _gemini_empty_output_retry_call():
                    return web_search_with(
                        provider,model,prompt,stage,timeout,limits_override=base_limits,
                        config_override={'_manual_empty_retry_minimal':True,'_manual_disable_json_mime':True},
                    )
                text,meta=_cloud_campaign_call_with_backoff(_gemini_empty_output_retry_call,provider,model,stage,rate_state)
                meta=dict(meta or {})
                meta['empty_output_retry']=True
                meta['empty_output_retry_mode']='minimal_thinking_no_json_mime'
            issue=_cloud_web_structured_issue(prompt,text,meta)
            if issue and not forum_only:
                current=max(64,int(base_limits.get('max_output_tokens') or CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general'])['max_output_tokens']))
                expanded=min(CLOUD_HARD_MAX_OUTPUT,max(current+1800,int(current*1.75)))
                if expanded>current:
                    retry_limits=dict(base_limits); retry_limits['max_output_tokens']=expanded
                    def _structured_web_retry_call():
                        return web_search_with(provider,model,prompt,stage,timeout,limits_override=retry_limits)
                    text,meta=_cloud_campaign_call_with_backoff(_structured_web_retry_call,provider,model,stage,rate_state)
                    meta=dict(meta or {}); meta['structured_retry']=True; meta['structured_retry_output_cap']=expanded
                    issue=_cloud_web_structured_issue(prompt,text,meta)
            if issue:
                suffix=' without retry (Forum throughput isolation)' if forum_only else ' after structured-output retry'
                raise RuntimeError(f'{provider} {model}: {issue}{suffix}')
            meta=dict(meta or {}); meta['route_lane']=_lane; meta['route_stage']=stage
            return text,meta
        except Exception as exc:
            last_error=exc
            if forum_only:
                break
    if last_error: raise last_error
    raise RuntimeError('No configured Cloud Web model could execute the request.')

def test_provider(provider, prompt=None):
    cfg=AIProviderConfig.objects.get(provider=provider)
    started=timezone.now(); web_ok=None; web_message=''
    try:
        if provider == 'ollama':
            d=ollama.diagnostics(); ok=d['ok']; msg=d['message']
            caps=dict(cfg.capabilities or {}); caps.update({'model':cfg.default_model or '', 'generation':bool(ok), 'web_search':False})
        else:
            test_prompt=(prompt or 'Reply with exactly: OK').strip()[:2000]
            model=configured_cloud_model(cfg)
            if not model:
                raise RuntimeError('No cloud model has been selected or resolved yet. Use Test configuration to resolve Automatic, or choose a default model.')
            try:
                text=generate_with(provider,model,test_prompt,stage='provider_test',timeout=30)
            except AIEmptyOutputWarning:
                if provider!='gemini':
                    raise
                text=generate_with(provider,model,test_prompt,stage='provider_test',timeout=30,config_override={'_manual_empty_retry_minimal':True,'_manual_disable_json_mime':True})
            ok=bool(text.strip()); msg=f'Provider responded: {text[:300]}'
            caps=dict(cfg.capabilities or {}); caps.update({'model':model, 'generation':bool(ok)})
            if ok and provider in CLOUD_PROVIDERS:
                try:
                    try:
                        web_text,_meta=web_search_with(provider,model,'Capability test: find the official Python programming language website and reply with its name and URL.',stage='provider_test',timeout=45,limits_override={'max_input_tokens':700,'max_output_tokens':160},budget_operation='provider_test')
                    except AIEmptyOutputWarning:
                        if provider!='gemini':
                            raise
                        web_text,_meta=web_search_with(provider,model,'Capability test: find the official Python programming language website and reply with its name and URL.',stage='provider_test',timeout=45,limits_override={'max_input_tokens':700,'max_output_tokens':160},budget_operation='provider_test',config_override={'_manual_empty_retry_minimal':True,'_manual_disable_json_mime':True})
                    web_ok=bool(str(web_text or '').strip()); caps['web_search']=web_ok
                    web_message=' · Web research available' if web_ok else ' · Web research returned no content'
                except CloudLimitReached:
                    caps.pop('web_search',None); web_message=' · Web capability not tested because a Cloud AI safety limit was reached'
                except Exception as web_exc:
                    web_ok=False; caps['web_search']=False; caps['web_search_error']=str(web_exc)[:500]
                    web_message=' · Generation works; web research is unavailable for this model'
            msg+=web_message
    except CloudLimitReached as exc:
        return {'ok':None,'state':'limit_reached','message':str(exc),'provider':provider,'at':started,'limit_name':exc.limit_name,'used':exc.used,'limit':exc.limit}
    except Exception as exc:
        ok=False; msg=str(exc); caps=dict(cfg.capabilities or {}); caps.update({'model':configured_cloud_model(cfg), 'generation':False})
    cfg.last_test_ok=ok; cfg.last_test_message=msg; cfg.last_test_at=timezone.now(); cfg.capabilities=caps; cfg.save()
    return {'ok':ok,'state':'ok' if ok else 'failed','message':msg,'provider':provider,'at':started,'capabilities':caps}
