from __future__ import annotations

from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime

MAX_CONTEXT_TEXT = 2000
DEFAULT_KEEP_HOURS = 48

def _aware(value):
    if not value:
        return None
    if hasattr(value, 'tzinfo'):
        dt=value
    else:
        dt=parse_datetime(str(value))
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt=timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

def make_run_context(kind, text, *, keep_until=None, origin='manual', preferred_company_countries=None, excluded_company_countries=None):
    text=str(text or '').strip()[:MAX_CONTEXT_TEXT]
    preferred=list(dict.fromkeys(str(x or '').strip() for x in (preferred_company_countries or []) if str(x or '').strip()))[:20]
    excluded=list(dict.fromkeys(str(x or '').strip() for x in (excluded_company_countries or []) if str(x or '').strip()))[:20]
    if not text and not preferred and not excluded:
        return None
    data={'kind':kind,'text':text,'origin':origin}
    if preferred: data['preferred_company_countries']=preferred
    if excluded: data['excluded_company_countries']=excluded
    until=_aware(keep_until)
    if kind=='custom_instructions' and until:
        data['keep_until']=until.isoformat()
    return data

def describe_run_context(criteria):
    ctx=((criteria or {}).get('run_context') or {}) if isinstance(criteria,dict) else {}
    kind=str(ctx.get('kind') or '')
    text=str(ctx.get('text') or '').strip()
    preferred=ctx.get('preferred_company_countries') or []
    excluded=ctx.get('excluded_company_countries') or []
    if (not text and not preferred and not excluded) or kind not in ('note','custom_instructions'):
        return {}
    label='Custom settings' if kind=='custom_instructions' else 'Note'
    until=_aware(ctx.get('keep_until'))
    suffix=''
    if until:
        suffix=f" (Until {timezone.localtime(until):%d/%m/%Y %H:%M})"
    return {
        'kind':kind,
        'label':label,
        'text':text,
        'preferred_company_countries':preferred,
        'excluded_company_countries':excluded,
        'until':until,
        'suffix':suffix,
        'display':f"{label} · {' · '.join(([text] if text else []) + (['Prefer: '+', '.join(preferred)] if preferred else []) + (['Exclude: '+', '.join(excluded)] if excluded else []))}{suffix}",
        'icon':'edit' if kind=='custom_instructions' else 'note',
        'note_only':kind=='note',
    }


def display_run_context(criteria):
    return describe_run_context(criteria).get('display','')

def active_custom_instruction(campaign, now=None):
    """Return the newest explicit retained custom instruction, if still active.

    A newer explicit custom-instruction run supersedes all older retained instructions,
    including when that newer instruction was intentionally one-run-only. Inherited
    scheduled/manual contexts are ignored while finding the owner of persistence.
    """
    now=now or timezone.now()
    runs=campaign.runs.order_by('-created_at').only('criteria','created_at')[:200]
    for run in runs:
        ctx=((run.criteria or {}).get('run_context') or {})
        if ctx.get('kind')!='custom_instructions' or ctx.get('origin','manual')!='manual':
            continue
        text=str(ctx.get('text') or '').strip()
        preferred=list(ctx.get('preferred_company_countries') or [])[:20]
        excluded=list(ctx.get('excluded_company_countries') or [])[:20]
        until=_aware(ctx.get('keep_until'))
        if (text or preferred or excluded) and until and until>now:
            return make_run_context('custom_instructions',text,keep_until=until,origin='inherited',preferred_company_countries=preferred,excluded_company_countries=excluded)
        return None
    return None

def inherited_run_context(campaign, now=None):
    return active_custom_instruction(campaign,now=now)

def default_keep_until(now=None):
    return (now or timezone.now()) + timedelta(hours=DEFAULT_KEEP_HOURS)
