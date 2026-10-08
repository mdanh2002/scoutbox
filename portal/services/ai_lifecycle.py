from __future__ import annotations

import hashlib
from django.utils import timezone


def _text(entity, kind):
    parts=[
        str(getattr(entity,'company','') or ''),
        str(getattr(entity,'title','') or ''),
        str(getattr(entity,'target_url','') or getattr(entity,'url','') or getattr(entity,'source_url','') or ''),
    ]
    if kind in ('summary','freshness'):
        parts.extend([str(getattr(entity,'description','') or ''),str(getattr(entity,'raw_search_snippet','') or ''),str(getattr(entity,'evidence','') or ''),str(getattr(entity,'match_summary','') or '')])
    elif kind=='company':
        parts.extend([str(getattr(entity,'country','') or ''),str(getattr(entity,'evidence','') or ''),str(getattr(entity,'description','') or '')[:6000]])
    return '\n'.join(parts)


def evidence_hash(entity, kind):
    return hashlib.sha256(_text(entity,kind).encode('utf-8','ignore')).hexdigest()


def state_for(entity, kind, *, reset_changed=True):
    state=dict(getattr(entity,'ai_state',{}) or {})
    current=dict(state.get(kind) or {})
    digest=evidence_hash(entity,kind)
    if reset_changed and current.get('evidence_hash')!=digest:
        current={
            'evidence_hash':digest,
            'generation':int(current.get('generation') or 0)+1,
            'initial':'pending',
            'recovery':'pending',
            'manual_count':0,
            'changed_at':timezone.now().isoformat(),
        }
        state[kind]=current
        entity.ai_state=state
        entity.save(update_fields=['ai_state','updated_at'])
    return current


def _save(entity, kind, current):
    state=dict(getattr(entity,'ai_state',{}) or {})
    state[kind]=current
    entity.ai_state=state
    entity.save(update_fields=['ai_state','updated_at'])
    return current


def usable_result(entity, kind):
    if kind=='summary':
        if entity.__class__.__name__.lower()=='opportunity':
            row=((getattr(entity,'extracted_facts',{}) or {}).get('ai_job_summary') or {})
            source=(getattr(entity,'description','') or getattr(entity,'raw_search_snippet','') or '').strip()
            source_hash=hashlib.sha256(source.encode('utf-8','ignore')).hexdigest() if source else ''
            return bool(str(row.get('text') or '').strip() and (not row.get('source_hash') or row.get('source_hash')==source_hash))
        state=(getattr(entity,'ai_state',{}) or {}).get('summary') or {}
        return bool(str(getattr(entity,'summary','') or '').strip() and (state.get('initial')=='success' or state.get('recovery')=='success' or state.get('last_manual')=='success'))
    if kind=='company':
        intel=getattr(entity,'company_intel',{}) or {}
        structured=intel.get('structured') if isinstance(intel,dict) and isinstance(intel.get('structured'),dict) else {}
        # Domain/RDAP refresh is deterministic maintenance owned by company_domain_refresh_tick.
        # It must not make an otherwise complete company profile trigger another AI pass.
        # A generic researched profile is not a usable list-level Company Info result.
        # Recovery should continue until we have the same age/size signal used by the
        # Opportunities list (company founding age, domain-registration age, or size).
        # Import locally to avoid coupling module import order.
        try:
            from .company_research import company_info_has_display_data
            display_data=company_info_has_display_data(intel)
        except Exception:
            display_data=False
        return bool(intel.get('facts') and intel.get('status')=='complete' and display_data)
    if kind=='freshness':
        return bool(str(getattr(entity,'freshness_label','') or '').strip() and int(getattr(entity,'freshness_confidence',0) or 0)>0)
    return False


def reserve_attempt(entity, kind, phase):
    """Reserve one lifecycle attempt. Manual attempts are unlimited by lifecycle.

    Returns (allowed, state). Automatic initial/recovery phases are each one-shot per
    evidence generation. A successful initial attempt suppresses recovery.
    """
    current=state_for(entity,kind)
    phase=str(phase or 'manual')
    if phase=='initial':
        if current.get('initial') not in ('pending',None,''):
            return False,current
        current['initial']='queued'; current['initial_queued_at']=timezone.now().isoformat()
    elif phase=='recovery':
        if usable_result(entity,kind) or current.get('initial')=='success':
            return False,current
        if current.get('recovery') not in ('pending',None,''):
            return False,current
        current['recovery']='queued'; current['recovery_queued_at']=timezone.now().isoformat()
    else:
        current['manual_count']=int(current.get('manual_count') or 0)+1
        current['last_manual']='queued'; current['last_manual_at']=timezone.now().isoformat()
    _save(entity,kind,current)
    return True,current


def complete_attempt(entity, kind, phase, status, detail=''):
    current=state_for(entity,kind)
    status=str(status or 'failed')
    phase=str(phase or 'manual')
    now=timezone.now().isoformat()
    if phase in ('initial','recovery'):
        current[phase]=status
        current[f'{phase}_finished_at']=now
        if detail: current[f'{phase}_detail']=str(detail)[:1000]
    else:
        current['last_manual']=status
        current['last_manual_finished_at']=now
        if detail: current['last_manual_detail']=str(detail)[:1000]
    _save(entity,kind,current)
    return current


def budget_operation_for_phase(phase):
    if phase=='initial': return 'passive_enrichment'
    if phase=='recovery': return 'page_recovery'
    if phase=='manual': return 'ad_hoc'
    return ''
