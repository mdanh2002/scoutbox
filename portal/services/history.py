import re
from difflib import SequenceMatcher
from django.utils import timezone
from portal.models import Application, PortalSettings

LEGAL_SUFFIX_RE=re.compile(r'\b(pte\.?\s*ltd\.?|private limited|limited|ltd\.?|inc\.?|incorporated|llc|l\.l\.c\.|corp\.?|corporation|gmbh|plc|company|co\.?)\b',re.I)


def normalize_company(value):
    value=LEGAL_SUFFIX_RE.sub(' ',value or '')
    return re.sub(r'[^a-z0-9]+',' ',value.lower()).strip()


def normalize_role(value):
    return re.sub(r'[^a-z0-9]+',' ',(value or '').lower()).strip()


def _company_match(a,b):
    a=normalize_company(a); b=normalize_company(b)
    if not a or not b: return False,0.0
    if a==b: return True,1.0
    if min(len(a),len(b))>=5 and (a.startswith(b+' ') or b.startswith(a+' ')):
        return True,0.95
    ta=set(a.split()); tb=set(b.split())
    overlap=len(ta & tb)/max(1,len(ta | tb))
    if overlap>=0.80 and len(ta & tb)>=2:
        return True,max(0.91,overlap)
    ratio=SequenceMatcher(None,a,b).ratio()
    return ratio>=0.90,ratio


def _role_match(a,b):
    a=normalize_role(a); b=normalize_role(b)
    if not a or not b: return False,0.0
    if a==b: return True,1.0
    ratio=SequenceMatcher(None,a,b).ratio()
    return ratio>=0.88,ratio


def evaluate_company_history(opportunity, base_score=None):
    """Suppress recently repeated employer/role matches while allowing useful rediscovery.

    The configured company cooldown is the governing window. Inside it, a same-company
    role is hidden unless it is both substantially different and unusually valuable. An
    exact same-role match is always hidden inside the window. Applications older than the
    cooldown do not block a genuinely new posting. Historical rows with no reliable date
    remain conservative because their age cannot be established.
    """
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    facts=opportunity.extracted_facts or {}
    company=(opportunity.company or '').strip()
    if not company:
        facts['application_history']={'matched':False,'reason':'Company not known yet; company-level application history cannot be evaluated.'}
        opportunity.extracted_facts=facts
        return {'matched':False,'penalty':0,'exact_role':False}

    statuses=['applied','reply','interview','rejected','accepted','closed']
    apps=Application.objects.filter(deleted_at__isnull=True,status__in=statuses).select_related('opportunity').exclude(opportunity_id=opportunity.pk)[:3000]
    same=[]
    for app in apps:
        ok,company_ratio=_company_match(company,app.opportunity.company)
        if not ok: continue
        role_ok,role_ratio=_role_match(opportunity.title,app.opportunity.title)
        same.append((app,company_ratio,role_ok,role_ratio))
    if not same:
        facts['application_history']={'matched':False,'company':company}
        opportunity.extracted_facts=facts
        return {'matched':False,'penalty':0,'exact_role':False}

    cutoff=timezone.now()-timezone.timedelta(days=cfg.company_reapply_window_days)
    exact=[x for x in same if x[2]]
    if exact:
        exact.sort(key=lambda x:(x[0].applied_at or x[0].updated_at),reverse=True)
        app,cr,_,rr=exact[0]
        # A clearly old application must not permanently blacklist an employer/role. This
        # lets a genuinely new posting reappear after the configured cooldown. Unknown
        # dates stay conservative because ScoutBox cannot prove that the cooldown elapsed.
        exact_is_recent=(app.applied_at is None or app.applied_at>=cutoff)
        if exact_is_recent:
            opportunity.suppressed=True
            opportunity.duplicate_of=app.opportunity
            opportunity.status='applied'
            opportunity.fit_score=0
            timing=(f'applied {app.applied_at:%Y-%m-%d}' if app.applied_at else 'application date unknown')
            reason=(f'Recent same-role application ({timing}) at {app.opportunity.company}: '
                    f'{app.opportunity.title}. Hidden during the {cfg.company_reapply_window_days}-day cooldown.')
            facts['application_history']={
                'matched':True,'exact_role':True,'company':app.opportunity.company,'role':app.opportunity.title,
                'applied_at':app.applied_at.isoformat() if app.applied_at else None,
                'company_similarity':round(cr,3),'role_similarity':round(rr,3),'score_penalty':100,
                'cooldown_days':cfg.company_reapply_window_days,'reason':reason,
            }
            opportunity.extracted_facts=facts
            opportunity.recommendation_reason=(reason+' '+(opportunity.recommendation_reason or ''))[:2000]
            return {'matched':True,'penalty':100,'exact_role':True,'application':app,'suppressed':True}
        facts['application_history']={
            'matched':True,'exact_role':True,'company':app.opportunity.company,'role':app.opportunity.title,
            'applied_at':app.applied_at.isoformat() if app.applied_at else None,'score_penalty':0,
            'cooldown_days':cfg.company_reapply_window_days,
            'reason':f'Previous same-role application is outside the {cfg.company_reapply_window_days}-day cooldown; new posting remains eligible.',
        }
        opportunity.extracted_facts=facts
        return {'matched':True,'penalty':0,'exact_role':True,'application':app}

    recent=[]; unknown=[]
    for app,cr,_,rr in same:
        if app.applied_at is None: unknown.append((app,cr,rr))
        elif app.applied_at>=cutoff: recent.append((app,cr,rr))
    if recent:
        recent.sort(key=lambda x:x[0].applied_at,reverse=True)
        app,cr,rr=recent[0]; penalty=int(cfg.same_company_fit_penalty)
        timing=f'applied {app.applied_at:%Y-%m-%d}'
    elif unknown:
        unknown.sort(key=lambda x:x[0].updated_at,reverse=True)
        app,cr,rr=unknown[0]; penalty=int(cfg.same_company_unknown_date_penalty)
        timing='historical application date is unknown'
    else:
        facts['application_history']={
            'matched':True,'exact_role':False,'company':same[0][0].opportunity.company,'score_penalty':0,
            'reason':f'Previous application exists at this company, but it is outside the {cfg.company_reapply_window_days}-day cooldown.'
        }
        opportunity.extracted_facts=facts
        return {'matched':True,'penalty':0,'exact_role':False}

    before=int(opportunity.fit_score if base_score is None else base_score)
    # Within the re-application window, do not keep returning another ordinary role from
    # the same employer. A recent same-company role survives only when it is BOTH clearly
    # different from the previous role and unusually valuable for this candidate. This is
    # intentionally stricter than the historical soft penalty, while still allowing a rare
    # KVM/firmware/RE role to survive after an unrelated application at the same company.
    very_different=rr < 0.58
    unusually_valuable=before >= 85
    if recent and not (very_different and unusually_valuable):
        opportunity.suppressed=True
        opportunity.duplicate_of=app.opportunity
        opportunity.status='rejected'
        opportunity.fit_score=0
        reason=(f'Recent same-company application: {timing} at {app.opportunity.company} for '
                f'{app.opportunity.title}. This new role was hidden during the {cfg.company_reapply_window_days}-day cooldown '
                f'because it was not both substantially different and high-value.')
        facts['application_history']={
            'matched':True,'exact_role':False,'company':app.opportunity.company,'previous_role':app.opportunity.title,
            'applied_at':app.applied_at.isoformat() if app.applied_at else None,'company_similarity':round(cr,3),
            'role_similarity':round(rr,3),'score_before_penalty':before,'score_penalty':before,'score_after_penalty':0,
            'cooldown_days':cfg.company_reapply_window_days,'suppressed_recent_company':True,
            'very_different':very_different,'unusually_valuable':unusually_valuable,'reason':reason,
        }
        opportunity.extracted_facts=facts
        opportunity.recommendation_reason=((opportunity.recommendation_reason or '')+' '+reason).strip()[:2000]
        opportunity.rejection_reason=reason[:2000]
        return {'matched':True,'penalty':before,'exact_role':False,'application':app,'suppressed':True}

    # Unknown historical dates remain a caution only. A high-value, very different role
    # inside the known cooldown also remains visible, with a lighter penalty.
    effective_penalty=max(1, penalty//2) if recent else penalty
    opportunity.fit_score=max(0,before-effective_penalty)
    reason=(f'Recent-company exception: {timing} at {app.opportunity.company} for a different role '
            f'({app.opportunity.title}). Kept because this role is substantially different and high-value; '
            f'Fit score reduced by {effective_penalty} points.' if recent else
            f'Company-history caution: {timing} at {app.opportunity.company} for a different role '
            f'({app.opportunity.title}). Fit score reduced by {effective_penalty} points.')
    facts['application_history']={
        'matched':True,'exact_role':False,'company':app.opportunity.company,'previous_role':app.opportunity.title,
        'applied_at':app.applied_at.isoformat() if app.applied_at else None,'company_similarity':round(cr,3),
        'role_similarity':round(rr,3),'score_before_penalty':before,'score_penalty':effective_penalty,'score_after_penalty':opportunity.fit_score,
        'cooldown_days':cfg.company_reapply_window_days,'very_different':very_different,
        'unusually_valuable':unusually_valuable,'reason':reason,
    }
    opportunity.extracted_facts=facts
    opportunity.recommendation_reason=((opportunity.recommendation_reason or '')+' '+reason).strip()[:2000]
    return {'matched':True,'penalty':effective_penalty,'exact_role':False,'application':app}
