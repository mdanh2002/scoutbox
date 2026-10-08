from __future__ import annotations

import time
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from portal.models import AIProviderConfig, BackgroundJob, PortalSettings
from .crypto import decrypt
from .resources import gpu_telemetry, host_resource_totals
from . import ollama

CLOUD_PROVIDERS = ('openai', 'gemini', 'openrouter')
AUTO_ACCELERATOR_PROBE_LABEL = 'Local accelerator auto-detection'
_CACHE = {'at': 0.0, 'value': None}


def local_accelerator_state():
    gpu, gpu_mem, label = gpu_telemetry()
    totals = host_resource_totals()
    os_label = str(totals.get('os_label') or '').strip()
    platform_label = str(totals.get('platform') or '').strip()
    identity = f'{os_label} {platform_label}'.lower()

    # Apple Silicon uses unified memory and does not expose NVIDIA-style VRAM. When
    # ScoutBox is in Docker, the host telemetry bridge identifies the Mac as Darwin
    # arm64 even if macOS does not expose a utilization counter to the unprivileged
    # process. That host identity is sufficient accelerator evidence: every Apple
    # Silicon Mac has an integrated Apple GPU. Do not infer this from arm64 alone,
    # because Linux/ARM machines may be CPU-only.
    apple_host = ('darwin' in identity or 'macos' in identity)
    apple_arm = ('arm64' in identity or 'aarch64' in identity or 'apple silicon' in identity)
    apple_silicon = bool(apple_host and apple_arm)
    detected = bool(label or gpu is not None or apple_silicon)
    display_label = label or ('Apple Silicon GPU' if apple_silicon else '')
    return {
        'detected': detected,
        'gpu_percent': gpu,
        'gpu_memory_percent': gpu_mem,
        'label': display_label,
        'system': identity,
        'apple_silicon': apple_silicon,
        'host_os_label': os_label,
        'host_platform': platform_label,
    }


def _local_probe_record():
    """Return recent automatic accelerator-probe evidence stored on Ollama config."""
    try:
        cfg = AIProviderConfig.objects.filter(provider='ollama').first()
        data = dict((cfg.capabilities or {}).get('local_accelerator_probe') or {}) if cfg else {}
        raw_at = str(data.get('at') or '')
        at = parse_datetime(raw_at) if raw_at else None
        if at and timezone.is_naive(at):
            at = timezone.make_aware(at, timezone.get_current_timezone())
        data['_at'] = at
        return data
    except Exception:
        return {}


def _probe_is_recent(data, hours=24):
    at = (data or {}).get('_at')
    return bool(at and at >= timezone.now() - timedelta(hours=hours))


def _ensure_local_accelerator_probe():
    """Queue one lightweight local probe when accelerator identity is still unknown.

    This is intentionally automatic: Test Selection is a diagnostic convenience, not
    a prerequisite for ScoutBox to discover whether Local AI can run on a GPU.
    """
    try:
        cfg = AIProviderConfig.objects.filter(provider='ollama', enabled=True).first()
        if not cfg:
            return
        # Avoid duplicate/probe storms across web + beat + workers.
        if BackgroundJob.objects.filter(
            kind='diagnostic', label=AUTO_ACCELERATOR_PROBE_LABEL,
            status__in=['queued', 'running']
        ).exists():
            return
        recent = BackgroundJob.objects.filter(
            kind='diagnostic', label=AUTO_ACCELERATOR_PROBE_LABEL,
            created_at__gte=timezone.now() - timedelta(minutes=10)
        ).exists()
        if recent:
            return
        job = BackgroundJob.objects.create(
            kind='diagnostic', label=AUTO_ACCELERATOR_PROBE_LABEL,
            message='Identifying local accelerator…', result={'automatic': True}
        )
        try:
            from celery import current_app
            result = current_app.send_task('portal.tasks.local_accelerator_probe_job', args=[job.pk])
            job.celery_task_id = getattr(result, 'id', '') or ''
            job.save(update_fields=['celery_task_id'])
        except Exception as exc:
            job.status = 'failed'; job.finished_at = timezone.now()
            job.message = 'Automatic accelerator probe could not be queued'
            job.error = str(exc)[:1000]
            job.save(update_fields=['status','finished_at','message','error'])
    except Exception:
        return


def _installed_ollama_models(diag):
    names = []
    for item in (diag or {}).get('installed') or []:
        name = str((item or {}).get('model') or (item or {}).get('name') or '').strip()
        if name and name not in names:
            names.append(name)
    return names


def _latest_pipeline_validation_result():
    """Return the latest successful validation result for the currently saved routes."""
    try:
        # Imported lazily to avoid coupling module import order to the routing service.
        from .ai import pipeline_route_signature

        ps = PortalSettings.objects.get_or_create(pk=1)[0]
        job = (
            BackgroundJob.objects.filter(
                kind='diagnostic', label='Pipeline model validation', status='completed'
            )
            .order_by('-created_at')
            .first()
        )
        if not job:
            return {}
        result = job.result or {}
        if result.get('test_schema') != 3:
            return {}
        if result.get('route_signature') != pipeline_route_signature(ps.discovery_mode):
            return {}
        return result
    except Exception:
        return {}


def _current_pipeline_validations():
    """Return successful provider/model attempts for the current saved route signature."""
    result = _latest_pipeline_validation_result()
    validated = set()
    for row in result.get('stages') or []:
        for attempt in row.get('attempts') or []:
            if attempt.get('role') not in ('primary', 'fallback') or attempt.get('ok') is not True:
                continue
            provider = str(attempt.get('provider') or '').strip().lower()
            model = str(attempt.get('model') or '').strip()
            if provider:
                validated.add((provider, model))
    return validated


def _validated_local_accelerator():
    """Return recent direct evidence that Ollama used a local accelerator.

    Route signatures may become stale after a harmless routing edit, but accelerator
    evidence remains useful for a short period.  Prefer the current Test Selection, then
    recent completed selection/model tests.  This avoids false Dashboard warnings when
    Docker host telemetry briefly disappears while still refusing indefinite CPU-only use.
    """
    results=[]
    current=_latest_pipeline_validation_result()
    if current: results.append(current)
    cutoff=timezone.now()-timedelta(hours=24)
    try:
        jobs=(BackgroundJob.objects.filter(kind='diagnostic',label='Pipeline model validation',status='completed',finished_at__gte=cutoff).order_by('-finished_at')[:8])
        results.extend([j.result or {} for j in jobs])
    except Exception:
        pass
    seen=set()
    for result in results:
        marker=id(result)
        if marker in seen: continue
        seen.add(marker)
        for row in result.get('stages') or []:
            for attempt in row.get('attempts') or []:
                if (str(attempt.get('provider') or '').lower()=='ollama' and attempt.get('ok') is True and attempt.get('accelerator_validated') is True):
                    return True
    try:
        jobs=(BackgroundJob.objects.filter(label='Ollama model test',status='completed',finished_at__gte=cutoff).order_by('-finished_at')[:5])
        for job in jobs:
            if (job.result or {}).get('accelerator_validated') is True:
                return True
    except Exception:
        pass
    return False


def provider_state(provider, validated_routes=None):
    provider = str(provider or '').lower()
    cfg = AIProviderConfig.objects.filter(provider=provider).first()
    if not cfg or not cfg.enabled:
        return {'provider': provider, 'ready': False, 'reason': 'Provider disabled or not configured.'}

    validated_routes = validated_routes if validated_routes is not None else _current_pipeline_validations()

    if provider == 'ollama':
        accel = local_accelerator_state()
        try:
            diag = ollama.diagnostics() or {}
        except Exception as exc:
            diag = {'ok': False, 'message': str(exc), 'installed': []}
        installed = _installed_ollama_models(diag)

        # Host GPU telemetry is best-effort. Test Selection records direct Ollama
        # VRAM/GPU evidence at model-execution time, so a stale/missing telemetry bridge
        # must not turn a proven local GPU route into a false global warning.
        validated_accelerator = _validated_local_accelerator()
        running_vram = any(float((item or {}).get('size_vram') or 0) > 0 for item in (diag.get('running') or []))
        auto_probe = _local_probe_record()
        auto_probe_recent = _probe_is_recent(auto_probe)
        auto_probe_ready = bool(auto_probe_recent and auto_probe.get('ok') is True)
        auto_probe_negative = bool(auto_probe_recent and auto_probe.get('conclusive') is True and auto_probe.get('ok') is False)
        accelerator_ready = bool(accel['detected'] or running_vram or validated_accelerator or auto_probe_ready)
        identifying = bool(diag.get('ok') and installed and not accelerator_ready and not auto_probe_negative)
        ready = bool(diag.get('ok') and installed and accelerator_ready)
        if not diag.get('ok'):
            reason = diag.get('message') or 'Ollama is unavailable.'
        elif not installed:
            reason = 'No local Ollama model is installed.'
        elif identifying:
            reason = 'Identifying local accelerator…'
        elif not accelerator_ready:
            reason = 'Local accelerator was not detected.'
        else:
            reason = 'Local AI is ready.'
        default_model = (cfg.default_model or '').strip()
        return {
            'provider': provider,
            'ready': ready,
            'reason': reason,
            'model': default_model,
            'installed_models': installed,
            'default_model_available': bool(default_model and default_model in installed),
            'validated_route': any(p == 'ollama' for p, _ in validated_routes),
            'validated_accelerator': validated_accelerator,
            'accelerator': accel,
            'provider_test_ok': bool(cfg.last_test_ok),
            'diagnostics_ok': bool(diag.get('ok')),
            'running_vram': running_vram,
            'identifying': identifying,
            'auto_probe': {k:v for k,v in auto_probe.items() if k != '_at'},
        }

    key = ''
    try:
        key = decrypt(cfg.api_key_enc)
    except Exception:
        pass
    if not key:
        return {
            'provider': provider,
            'ready': False,
            'reason': 'Cloud credentials are missing.',
            'model': cfg.default_model or '',
        }
    caps=dict(cfg.capabilities or {})
    model = (cfg.default_model or caps.get('model') or '').strip()
    route_validated = any(p == provider for p, _ in validated_routes)
    if not model and not route_validated:
        return {
            'provider': provider,
            'ready': False,
            'reason': 'No default cloud model is configured.',
            'model': '',
        }

    # Either a direct provider/model test or a current Test Selection route validation
    # establishes cloud readiness.  This keeps the system provider-neutral and avoids
    # requiring a particular cloud vendor or a provider-level default-model test when
    # the actual saved route has already passed.
    if not cfg.last_test_ok and not route_validated:
        return {
            'provider': provider,
            'ready': False,
            'reason': cfg.last_test_message or 'Provider/model has not passed validation.',
            'model': model,
        }
    return {
        'provider': provider,
        'ready': True,
        'reason': 'Validated cloud AI is ready.',
        'model': model,
        'last_test_at': cfg.last_test_at,
        'validated_route': route_validated,
        'provider_test_ok': bool(cfg.last_test_ok),
    }


def ai_compute_readiness(force=False):
    now = time.monotonic()
    if not force and _CACHE.get('value') is not None and now - float(_CACHE.get('at') or 0) < 10:
        return _CACHE['value']

    validated_routes = _current_pipeline_validations()
    states = [provider_state('ollama', validated_routes)] + [
        provider_state(p, validated_routes) for p in CLOUD_PROVIDERS
    ]
    ready = [x for x in states if x.get('ready')]
    if ready:
        # Prefer the configured local runtime when it is usable; otherwise accept any
        # validated cloud provider.  No cloud vendor is assumed or required.
        preferred = ready[0]
        value = {
            'ready': True,
            'reason': preferred.get('reason', 'AI compute ready.'),
            'provider': preferred['provider'],
            'states': states,
        }
    else:
        identifying = any(bool(x.get('identifying')) for x in states)
        if identifying:
            _ensure_local_accelerator_probe()
        value = {
            'ready': False,
            'identifying': identifying,
            # Unknown accelerator state is not the same as negative evidence.
            'reason': 'Identifying local accelerator…' if identifying else 'No usable AI route.',
            'states': states,
        }
    _CACHE.update(at=now, value=value)
    return value


def route_ready(provider):
    return provider_state(provider).get('ready', False)
