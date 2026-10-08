import requests, time
from django.conf import settings
from portal.models import UsageMetric, AIProviderConfig
from .cloud_budget import metadata as usage_metadata

def base_url(base_url_override=None):
    if base_url_override:
        return str(base_url_override).rstrip('/')
    try:
        cfg=AIProviderConfig.objects.filter(provider='ollama').first()
        if cfg and cfg.base_url: return cfg.base_url.rstrip('/')
    except Exception:
        pass
    return settings.OLLAMA_BASE_URL.rstrip('/')

def list_models(base_url_override=None):
    r=requests.get(base_url(base_url_override)+'/api/tags',timeout=5); r.raise_for_status(); return r.json().get('models',[])

def running_models(base_url_override=None):
    r=requests.get(base_url(base_url_override)+'/api/ps',timeout=5); r.raise_for_status(); return r.json().get('models',[])

def _bounded_positive_int(value, default, low, high):
    try:
        value = int(value if value not in (None, '') else default)
    except Exception:
        value = int(default)
    return max(int(low), min(int(high), value))


def _stream_generate(url, payload, timeout):
    """Call Ollama with a true wall-clock deadline.

    ``requests`` read timeouts are inactivity timeouts, not total request limits. A
    stalled Ollama/proxy connection can therefore leave ScoutBox holding its local-AI
    lane while the machine is already idle. Streaming gives us progress chunks and lets
    ScoutBox close the socket once the configured per-attempt deadline is reached.
    """
    import json as _json
    deadline = time.monotonic() + max(1, int(timeout or 120))
    chunks = []
    final = {}
    # A short read timeout keeps dead sockets from pinning the worker; the deadline below
    # remains the authoritative total cap.
    read_timeout = max(5, min(20, int(timeout or 120)))
    with requests.post(url, json=payload, timeout=(5, read_timeout), stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if time.monotonic() > deadline:
                try:
                    r.close()
                finally:
                    raise TimeoutError(f'Ollama request exceeded {int(timeout or 120)} seconds')
            if not line:
                continue
            try:
                row = _json.loads(line)
            except Exception:
                continue
            if row.get('response'):
                chunks.append(str(row.get('response') or ''))
            final = row
            if row.get('done'):
                break
    if time.monotonic() > deadline:
        raise TimeoutError(f'Ollama request exceeded {int(timeout or 120)} seconds')
    final = dict(final or {})
    final.setdefault('model', payload.get('model'))
    final['response'] = ''.join(chunks)
    return final


def generate(prompt, model=None, stage='general', timeout=120, max_output_tokens=None, metadata_extra=None, base_url_override=None):
    if not str(model or '').strip():
        raise RuntimeError('Ollama model was not resolved by ScoutBox routing; refusing implicit first-installed-model selection.')
    model=str(model).strip()
    timeout=_bounded_positive_int(timeout,120,15,600)
    payload={'model':model,'prompt':prompt,'stream':True}
    if max_output_tokens:
        payload['options']={'num_predict':int(max_output_tokens)}
    started=time.time()
    data=_stream_generate(base_url(base_url_override)+'/api/generate',payload,timeout)
    UsageMetric.objects.create(
        category='lab' if stage.startswith('lab') else 'ai',provider='ollama',model=model,stage=stage,requests=1,
        tokens_in=int(data.get('prompt_eval_count') or 0),tokens_out=int(data.get('eval_count') or 0),
        latency_ms=int((time.time()-started)*1000),
        metadata=usage_metadata({**(metadata_extra or {}),'total_duration':data.get('total_duration',0),'streamed_total_timeout':timeout}),
    )
    return data.get('response',''), data

def diagnostics(base_url_override=None):
    # /api/tags is the actual availability check. /api/ps is useful accelerator
    # telemetry, but it is not required for a working Ollama installation and can
    # be unavailable on some versions/proxies even when generation works.
    try:
        installed=list_models(base_url_override)
    except Exception as e:
        return {'ok':False,'installed':[],'running':[],'message':str(e),'running_error':''}
    running=[]; running_error=''; version=''
    try:
        running=running_models(base_url_override)
    except Exception as exc:
        running_error=str(exc)
    try:
        vr=requests.get(base_url(base_url_override)+'/api/version',timeout=3)
        if vr.ok:
            version=str((vr.json() or {}).get('version') or '').strip()
    except Exception:
        version=''
    version_prefix=f'Ollama {version} · ' if version else ''
    return {
        'ok':True,'installed':installed,'running':running,'version':version,
        'message':f'{version_prefix}{len(installed)} installed',
        'running_error':running_error,
    }
