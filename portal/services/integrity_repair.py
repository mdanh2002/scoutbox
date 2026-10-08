"""One-time retained-record integrity repair for ScoutBox 0.10.104.

This module deliberately limits network work to records whose stored provenance says a
third-party vacancy was replaced by a different employer/ATS URL. Generic job-board
search shells can be rejected from their already-retained text without refetching the
whole Opportunity table.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from django.utils import timezone

from portal.models import Opportunity, Application
from .content_quality import normalize_remote_constraints, remote_work_evidence, work_arrangement_evidence
from .discovery import (
    _aggregate_job_page,
    _direct_fetch,
    _local_action_signals,
    _replacement_role_page_valid,
    canonical,
)
from .platforms import is_plausible_company_name
from .role_gate import classify_role_page


def _norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def _suppress(row, reason):
    now=timezone.now()
    changed=Opportunity.objects.filter(pk=row.pk, user_deleted=False).update(
        status='rejected', suppressed=True, user_deleted=True, deleted_at=now, is_read=True,
        rejection_reason=str(reason or 'Retained opportunity failed the 0.10.104 integrity review.')[:2000],
        updated_at=now,
    )
    if changed:
        Application.objects.filter(opportunity_id=row.pk, deleted_at__isnull=True).update(
            deleted_at=now, is_read=True,
        )
    return bool(changed)


def _stored_hard_failure(row):
    """Return a deterministic failure reason for retained collection/shell rows."""
    title=str(row.title or '')
    text='\n'.join(x for x in (str(row.description or ''), str(row.raw_search_snippet or '')) if x)
    url=str(row.target_url or row.url or '')
    gate=classify_role_page(url, title, text, has_jobposting_schema=False, is_pdf=False)
    if gate.get('hard_reject'):
        return str(gate.get('reason') or 'Invalid opportunity source/structure.')
    if _aggregate_job_page(url, title, text):
        return 'Job-board collection/search page is not an individual vacancy.'
    # A navigation phrase accidentally captured as the employer is strong corroboration
    # only when the retained page also looks like a board/search shell. Do not remove a
    # valid vacancy merely because a small/odd employer name fails a naming heuristic.
    company=str(row.company or '').strip()
    if company and not is_plausible_company_name(company):
        low=_norm(company+' '+title+' '+text[:7000])
        shell_hits=sum(1 for marker in (
            'employers register for free','post a job','products & prices','customer service',
            'job return to search result','salary search:','see popular questions & answers about',
        ) if marker in low)
        if shell_hits >= 2:
            return 'Job-board navigation text was stored as employer/vacancy content.'
    return ''


def _role_identity_ok(expected_title, fetched_title, fetched_text):
    expected=_norm(expected_title)
    actual=_norm(fetched_title)
    if not expected:
        return True
    if actual and SequenceMatcher(None, expected, actual).ratio() >= 0.56:
        return True
    generic={'senior','junior','lead','principal','staff','engineer','developer','specialist','manager','remote','role','job'}
    tokens={x for x in re.findall(r'[a-z0-9+#.]+', expected) if len(x)>=3 and x not in generic}
    blob=_norm((fetched_title or '')+' '+(fetched_text or '')[:6000])
    if not tokens:
        return expected in blob
    need=1 if len(tokens)==1 else 2
    return sum(1 for token in tokens if token in blob) >= need


def _original_board_valid(row, original_url, fetched, facts):
    if not fetched or not fetched.get('ok'):
        return False, 'original board page could not be fetched'
    final=str(fetched.get('target_url') or original_url or '').strip()
    title=str(fetched.get('title') or row.title or '').strip()
    text=str(fetched.get('text') or '')
    if not final or _aggregate_job_page(final,title,text):
        return False, 'original board URL now resolves to a collection/search page'
    gate=classify_role_page(
        final,title,text,
        has_jobposting_schema=bool(fetched.get('has_jobposting_schema')),
        is_pdf=bool(fetched.get('is_pdf')),
    )
    if gate.get('hard_reject') or not gate.get('accepted'):
        return False, str(gate.get('reason') or 'original board page is not a concrete vacancy')
    action=_local_action_signals(final,text,has_jobposting_schema=bool(fetched.get('has_jobposting_schema')))
    if not action.get('clear'):
        return False, 'original board page no longer has concrete application/vacancy evidence'
    if not _role_identity_ok(row.title,title,text):
        return False, 'original board page no longer matches the stored role title'

    # Existing provenance from the board can preserve a role-level remote restriction.
    board_remote=((facts or {}).get('original_job_board_evidence') or {}).get('remote') or {}
    deterministic=normalize_remote_constraints(
        text+' '+str(fetched.get('jobposting_location') or ''), ''
    ) or board_remote
    explicit=remote_work_evidence(
        text+' '+str(fetched.get('jobposting_location') or ''),'',title,structured_remote=False
    )
    remote_status=str((deterministic or {}).get('status') or '').lower()
    try: remote_conf=int((deterministic or {}).get('confidence') or 0)
    except Exception: remote_conf=0
    if not (remote_status in {'remote','fully_remote'} and remote_conf >= 55) and not explicit.get('confirmed'):
        return False, 'remote-work eligibility is not confirmed on the retained/original role evidence'
    return True, ''


def _restore_original_board(row, original_url, fetched, facts):
    final=str(fetched.get('target_url') or original_url or '').strip()[:1000]
    text=str(fetched.get('text') or '')[:45000]
    newfacts=dict(facts or {})
    rejected=str(row.target_url or row.url or '')[:1000]
    newfacts['preferred_employer_rejected_url']=rejected
    newfacts['preferred_employer_rejected_reason']='0.10.104 retained-record revalidation rejected the replacement page.'
    newfacts['preferred_employer_url']=''
    newfacts['integrity_repair']={
        'release':'0.10.104','action':'restored_original_job_board','at':timezone.now().isoformat(),
        'rejected_replacement_url':rejected,'restored_url':final,
    }
    remote=normalize_remote_constraints(text+' '+str(fetched.get('jobposting_location') or ''),'')
    board_remote=((newfacts.get('original_job_board_evidence') or {}).get('remote') or {})
    remote=remote or board_remote
    remote_text=row.remote_text
    if remote and str(remote.get('status') or '').lower() in {'remote','fully_remote'}:
        remote_text=str(remote.get('label') or remote_text or 'Remote')[:220]
        newfacts['remote_classification']={
            'status':str(remote.get('status') or 'remote'),
            'label':str(remote.get('label') or 'Remote')[:60],
            'confidence':int(remote.get('confidence') or 90),
            'reason':str(remote.get('reason') or 'Original job-board evidence confirms remote work.')[:1200],
            'source':'0.10.104 original-board integrity repair',
        }
    Opportunity.objects.filter(pk=row.pk).update(
        url=final,target_url=final,canonical_url=canonical(final),description=text,
        remote_text=remote_text,extracted_facts=newfacts,target_http_status=(int(fetched.get('http_status')) if fetched.get('http_status') is not None else None),
        target_checked_at=timezone.now(),target_check_error=str(fetched.get('error') or '')[:500],
        target_response_bytes=int(fetched.get('bytes') or 0),suppressed=False,user_deleted=False,deleted_at=None,
        rejection_reason='',updated_at=timezone.now(),
    )


def repair_existing_opportunity_integrity(progress=None):
    """Repair retained invalid opportunities once after upgrading to 0.10.104.

    Returns counters suitable for the upgrade BackgroundJob result. The routine is safe
    to rerun: rows already moved to Recycle Bin are skipped, and restored substitutions
    have their ``preferred_employer_url`` cleared.
    """
    qs=Opportunity.objects.filter(user_deleted=False,suppressed=False).order_by('pk')
    total=qs.count()
    stats={'checked':0,'suppressed_invalid':0,'replacement_checked':0,'restored_original':0,'replacement_suppressed':0,'fetch_failures':0,'remote_badges_repaired':0}
    for idx,row in enumerate(qs.iterator(chunk_size=100), start=1):
        stats['checked']+=1
        failure=_stored_hard_failure(row)
        if failure:
            if _suppress(row,'0.10.104 integrity review: '+failure):
                stats['suppressed_invalid']+=1
            if progress and (idx % 10 == 0 or idx==total): progress(idx,total,stats)
            continue

        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        # Repair semantic Remote/Hybrid/On-site guesses that are not backed by actual
        # working-arrangement language. Do not use row.remote_text as evidence here: that
        # field is itself derived from the classification we are auditing.
        current_remote=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}
        current_status=str(current_remote.get('status') or '').strip().lower()
        if current_status in {'fully_remote','remote','hybrid','onsite'}:
            arrangement=work_arrangement_evidence(
                ' '.join(x for x in (row.description,row.raw_search_snippet,row.role_location) if x),'',row.title,structured_remote=False
            )
            board_remote=(facts.get('original_job_board_evidence') or {}).get('remote') if isinstance(facts.get('original_job_board_evidence'),dict) else {}
            board_status=str((board_remote or {}).get('status') or '').strip().lower()
            grounded=bool(arrangement.get('confirmed') and (
                current_status==str(arrangement.get('status') or '').lower() or
                {current_status,str(arrangement.get('status') or '').lower()}<={'fully_remote','remote'}
            ))
            if not grounded and current_status in {'fully_remote','remote'} and board_status in {'fully_remote','remote'}:
                grounded=True
            if not grounded:
                newfacts=dict(facts)
                newfacts['remote_classification']={
                    'status':'unknown','label':'Unknown','confidence':0,
                    'reason':'No explicit role-level remote/hybrid/on-site working-arrangement evidence was found during 0.10.104 integrity repair.',
                    'source':'0.10.104 remote-grounding repair','at':timezone.now().isoformat(),
                }
                Opportunity.objects.filter(pk=row.pk).update(remote_text='',extracted_facts=newfacts,updated_at=timezone.now())
                row.remote_text=''; row.extracted_facts=newfacts; facts=newfacts
                stats['remote_badges_repaired']+=1
        preferred=str(facts.get('preferred_employer_url') or '').strip()
        original=str(facts.get('original_job_board_url') or '').strip()
        current=str(row.target_url or row.url or '').strip()
        if preferred and original and current and canonical(current) != canonical(original):
            stats['replacement_checked']+=1
            # Re-evaluate the replacement against the replacement page itself. Never seed
            # the replacement title from the stored row; that is how unrelated pages inherited
            # a perfect title match during older repairs.
            current_fetched=_direct_fetch(current,row.title,row.raw_search_snippet or '',purpose='integrity_repair_replacement_role')
            if not current_fetched.get('ok'):
                current_fetched={
                    'ok':True,'target_url':current,'title':'','text':row.description or '',
                    'has_jobposting_schema':False,'is_pdf':False,
                }
            valid=_replacement_role_page_valid(row.title,row.company,current,current_fetched)
            if not valid.get('accepted'):
                fetched=_direct_fetch(original,row.title,row.raw_search_snippet or '',purpose='integrity_repair_original_role')
                if not fetched.get('ok'):
                    stats['fetch_failures']+=1
                original_ok,why=_original_board_valid(row,original,fetched,facts)
                if original_ok:
                    _restore_original_board(row,original,fetched,facts)
                    stats['restored_original']+=1
                else:
                    reason='0.10.104 integrity review: replacement URL failed independent vacancy validation'
                    if why: reason+='; '+why
                    if _suppress(row,reason):
                        stats['replacement_suppressed']+=1
        if progress and (idx % 10 == 0 or idx==total): progress(idx,total,stats)
    if progress and total==0: progress(0,0,stats)
    return stats
