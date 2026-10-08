import json
import re
from collections import Counter

from portal.models import CampaignTemplate, Profile
from .ai import generate
from .queryplanner import build_search_profile, ROLE_FAMILIES, SKILL_GRAPH, PROFILE_CONCEPT_LIMIT, PROFILE_ROLE_LIMIT

DEFAULT_PROMPT=(
    'Create one focused campaign template for each likely role. Use only technologies and specialist '
    'concepts evidenced by my configured Candidate Profile or active Resumes that are directly relevant '
    'to that role. Keep role templates distinct; do not copy the same technology list into every template.'
)


def _tokens(text):
    return {x for x in re.findall(r'[a-z0-9+#]+',str(text or '').lower()) if len(x)>2 and x not in {'engineer','engineering','specialist','software','technical'}}


def _role_terms(role, search_profile, limit=12):
    rows=[dict(x) for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    if not rows: return []
    role_low=' '.join(str(role or '').lower().split()); role_tokens=_tokens(role_low)
    best_role=''; best_score=0.0
    for known in ROLE_FAMILIES:
        kt=_tokens(known)
        if role_low==known: best_role=known; best_score=999; break
        overlap=len(role_tokens & kt); score=(2*overlap/max(1,len(role_tokens|kt))) if overlap else 0
        if known in role_low or role_low in known: score+=1.5
        if score>best_score: best_role,best_score=known,score
    triggers=list(ROLE_FAMILIES.get(best_role,[])) if best_score>=0.45 else []
    trigger_lows={x.lower() for x in triggers}
    target_categories={SKILL_GRAPH[x].get('category') for x in triggers if x in SKILL_GRAPH}
    category_hints={
        'embedded':{'embedded','embedded-niche','systems'},'firmware':{'embedded','embedded-niche','systems'},
        'driver':{'systems','embedded'},'kernel':{'systems'},'reverse':{'reverse','protocol-niche'},
        'security':{'security','reverse'},'emulation':{'retro','retro-niche','virtualization'},
        'emulator':{'retro','retro-niche','virtualization'},'virtualization':{'virtualization','systems'},
        'legacy':{'retro','retro-niche'},'retro':{'retro','retro-niche'},'systems':{'systems','virtualization'},
        'writer':{'writing'},'writing':{'writing'},'trainer':{'writing'},'training':{'writing'},
        'documentation':{'writing'},'protocol':{'reverse','protocol-niche','systems'},'gpu':{'systems','embedded'},
        'ai':{'systems','embedded'},'linux':{'systems','embedded'},
    }
    for token,cats in category_hints.items():
        if token in role_low: target_categories.update(cats)
    cv_focus={}
    for cv in search_profile.get('cv_focus') or []:
        label=str(cv.get('label') or '').lower(); label_match=bool(role_tokens & _tokens(label))
        for item in cv.get('terms') or []:
            term=str(item.get('term') or '').lower()
            if term: cv_focus[term]=max(cv_focus.get(term,0),22 if label_match else 8)
    ranked=[]
    for row in rows:
        term=str(row.get('term') or '').strip(); low=term.lower(); cat=str(row.get('category') or '')
        score=float(row.get('score') or 0); sources=row.get('sources') or {}
        # Evidence source is important: prefer active Resume and explicit Candidate Profile concepts.
        if sources.get('cv'): score+=18
        if sources.get('profile_override'): score+=16
        if sources.get('high_preference'): score+=10
        elif sources.get('medium_preference'): score+=4
        if low in trigger_lows: score+=95
        if cat in target_categories: score+=32
        score+=20*len(role_tokens & _tokens(term+' '+' '.join(row.get('aliases') or [])))
        score+=cv_focus.get(low,0)
        relevant=low in trigger_lows or cat in target_categories or bool(role_tokens & _tokens(term+' '+' '.join(row.get('aliases') or [])))
        ranked.append((score,term,relevant))
    ranked.sort(key=lambda x:(-x[0],x[1].lower()))
    pool=[x for x in ranked if x[2]] or ranked
    out=[]; seen=set()
    for _score,term,_rel in pool:
        if term.lower() in seen: continue
        seen.add(term.lower()); out.append(term)
        if len(out)>=limit: break
    if len(out)<4:
        for _score,term,_rel in ranked:
            if term.lower() in seen: continue
            seen.add(term.lower()); out.append(term)
            if len(out)>=min(limit,6): break
    return out


def role_term_map(roles, search_profile, prompt=''):
    roles=[str(r or '').strip() for r in roles if str(r or '').strip()]
    available=[str(x.get('term') or '').strip() for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    allowed={x.lower():x for x in available}; ai_map={}
    if roles and allowed:
        try:
            raw=generate(
                'Choose role-specific search technologies/skills from ALLOWED TERMS only. Return JSON only: '
                'an object whose keys exactly match ROLES and whose values are arrays of 3-6 exact allowed terms. '
                'Candidate Profile and active Resume evidence have already constrained the allowed vocabulary. '
                'Make each role meaningfully different. Do not copy a common technology stack into every role. '
                'A term may repeat only when it is central to both roles. Writing/training roles should prioritize '
                'writing, documentation, education, or subject-matter evidence rather than unrelated firmware/emulation terms. '
                f'User guidance: {prompt or DEFAULT_PROMPT}\nROLES: {json.dumps(roles)}\nALLOWED TERMS: {json.dumps(available)}',
                stage='first_filter',timeout=90,
            ).strip()
            raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S).strip(); parsed=json.loads(raw)
            if isinstance(parsed,dict):
                for role in roles:
                    vals=parsed.get(role) or []; clean=[]
                    for v in vals if isinstance(vals,list) else []:
                        canonical=allowed.get(str(v or '').strip().lower())
                        if canonical and canonical.lower() not in {x.lower() for x in clean}: clean.append(canonical)
                    ai_map[role]=clean[:6]
        except Exception:
            ai_map={}
    usage=Counter(); out={}
    for role in roles:
        direct=_role_terms(role,search_profile,12); candidates=[]
        for term in (ai_map.get(role) or [])+direct:
            canonical=allowed.get(str(term).lower())
            if canonical and canonical.lower() not in {x.lower() for x in candidates}: candidates.append(canonical)
        role_low=role.lower(); central=set()
        for known,triggers in ROLE_FAMILIES.items():
            if known==role_low or known in role_low or role_low in known:
                central={x.lower() for x in triggers}; break
        scored=[]
        for idx,term in enumerate(candidates):
            score=120-idx*5 + (60 if term.lower() in central else 0) - usage[term.lower()]*38
            scored.append((score,term))
        scored.sort(key=lambda x:(-x[0],x[1].lower())); selected=[]
        for _score,term in scored:
            if usage[term.lower()]>=2 and term.lower() not in central: continue
            selected.append(term); usage[term.lower()]+=1
            if len(selected)>=5: break
        for term in direct:
            if len(selected)>=4: break
            if term.lower() in {x.lower() for x in selected}: continue
            selected.append(term); usage[term.lower()]+=1
        out[role]=selected[:6]
    return out


def generate_profile_campaign_templates(prompt=''):
    profile=Profile.objects.get_or_create(pk=1)[0]
    prompt=' '.join(str(prompt or DEFAULT_PROMPT).split())[:1800]
    scope=dict(profile.scope_json or {}); scope['campaign_template_prompt']=prompt; profile.scope_json=scope
    profile.save(update_fields=['scope_json','updated_at'])
    search_profile=build_search_profile()
    roles=[str(x.get('role') or '').strip() for x in (search_profile.get('role_families') or []) if str(x.get('role') or '').strip()]
    if not roles: roles=[str(x).strip() for x in (scope.get('likely_roles') or []) if str(x).strip()]
    roles=list(dict.fromkeys(roles))[:24]
    if not roles: raise RuntimeError('No likely roles are available. Add likely roles or rebuild profile defaults first.')
    marker='[Generated from Candidate Profile]'
    # Preserve all existing templates; generation is additive in 0.8.76.
    mapping=role_term_map(roles,search_profile,prompt); created=[]
    all_terms=[]; seen_terms=set()
    for row in search_profile.get('skills') or []:
        term=str(row.get('term') or '').strip() if isinstance(row,dict) else str(row or '').strip()
        if term and term.lower() not in seen_terms:
            seen_terms.add(term.lower()); all_terms.append(term)
    for role in roles:
        focused=mapping.get(role) or _role_terms(role,search_profile,5)
        # Campaign templates retain role-focused terms first, but include the complete
        # technical vocabulary extracted from Candidate Profile / active Resumes so
        # query rotation can explore the full evidence set rather than an arbitrary six.
        terms=[]; local=set()
        for term in list(focused)+all_terms:
            if term and term.lower() not in local:
                local.add(term.lower()); terms.append(term)
        base_name=f'Profile — {role}'[:190]
        name=base_name; suffix=2
        while CampaignTemplate.objects.filter(name=name).exists():
            tail=f' ({suffix})'; name=(base_name[:200-len(tail)]+tail); suffix+=1
        row=CampaignTemplate.objects.create(
            name=name,
            description=f'{marker} Role-focused discovery template generated from Candidate Profile and active Resume evidence for {role}.',
            built_in=False,locations=list(profile.operating_locations or ([profile.operating_location] if profile.operating_location else [])),
            role_families=[role],technologies=terms,engagement_types=['Full-time','Part-time','Contract','Agency / consulting','One-time project','Collaboration'],
            company_sizes=[],languages=[],negative_constraints='',extra_text=prompt,recency_days=30,source_names=[],queries_per_rotation=None,
        )
        created.append({'id':row.pk,'role':role,'technologies':terms})
    return {'created':len(created),'templates':created}


def generate_resume_campaign_template(asset_id, resume_concepts=None, likely_roles=None, prompt=''):
    """Create or regenerate the single Campaign Template linked to a Resume.

    Templates and Campaigns are deliberately independent. Regeneration updates only the
    linked template and never touches Campaign rows that may have been created from it.
    """
    from django.utils import timezone
    from portal.models import DocumentAsset
    from .queryplanner import _read_asset_text

    asset=DocumentAsset.objects.filter(pk=asset_id,kind='cv',active=True).first()
    if not asset:
        raise RuntimeError('The selected Resume is no longer available.')
    text=_read_asset_text(asset)
    if not text:
        raise RuntimeError('ScoutBox could not extract readable text from the selected Resume.')
    concepts=list(dict.fromkeys(' '.join(str(x or '').split()).lower() for x in (resume_concepts or []) if str(x or '').strip()))[:PROFILE_CONCEPT_LIMIT]
    roles=list(dict.fromkeys(' '.join(str(x or '').split()).lower() for x in (likely_roles or []) if str(x or '').strip()))[:PROFILE_ROLE_LIMIT]
    guidance=' '.join(str(prompt or '').split())[:1800]
    profile=Profile.objects.get_or_create(pk=1)[0]
    allowed_locations=list(profile.operating_locations or ([profile.operating_location] if profile.operating_location else []))
    instruction=(
        'Create exactly one focused ScoutBox campaign template using ONLY evidence in the SELECTED RESUME. '
        'The user-supplied concepts, likely roles and additional prompt are preferences, not permission to invent experience. '
        'Return JSON only with keys name, role_families, technologies, extra_text. role_families and technologies are arrays. '
        'Use a concise campaign name. Technologies should be specific search terms evidenced in the resume.\n'
        f'RESUME LABEL: {asset.label}\nRESUME CONCEPTS: {json.dumps(concepts)}\nLIKELY ROLES: {json.dumps(roles)}\n'
        f'ADDITIONAL PROMPT: {guidance}\nSELECTED RESUME TEXT:\n{text[:24000]}'
    )
    parsed={}
    try:
        raw=generate(instruction,stage='first_filter',timeout=90,subject={'type':'document','id':asset.pk,'label':asset.label}).strip()
        raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S).strip()
        value=json.loads(raw)
        if isinstance(value,dict): parsed=value
    except Exception:
        parsed={}
    out_roles=[]
    for value in (parsed.get('role_families') or roles):
        value=' '.join(str(value or '').split())[:120]
        if value and value.lower() not in {x.lower() for x in out_roles}: out_roles.append(value)
        if len(out_roles)>=8: break
    if not out_roles:
        out_roles=[asset.label[:120]]
    out_terms=[]
    requested={x.lower() for x in concepts}
    for value in (parsed.get('technologies') or concepts):
        value=' '.join(str(value or '').split())[:120]
        # Parsed AI terms must be grounded in selected Resume text; explicit user concepts are
        # also retained only when they occur in that Resume.
        if value and value.lower() in text.lower() and value.lower() not in {x.lower() for x in out_terms}:
            out_terms.append(value)
        if len(out_terms)>=30: break
    if not out_terms:
        # Reuse the content-driven search-profile extractor, but keep only terms present in this Resume.
        search_profile=build_search_profile()
        for row in search_profile.get('skills') or []:
            term=str((row or {}).get('term') or '').strip()
            if term and term.lower() in text.lower() and term.lower() not in {x.lower() for x in out_terms}:
                out_terms.append(term)
            if len(out_terms)>=20: break
    base=' '.join(str(parsed.get('name') or '').split())[:150] or f'Resume — {out_roles[0]}'
    existing=CampaignTemplate.objects.filter(source_resume=asset).order_by('-updated_at').first()
    name=base[:200]; n=2
    name_qs=CampaignTemplate.objects.exclude(pk=existing.pk if existing else None)
    while name_qs.filter(name=name).exists():
        suffix=f' ({n})'; name=(base[:200-len(suffix)]+suffix); n+=1
    extra=' '.join(str(parsed.get('extra_text') or guidance or f'Focus discovery on evidence from Resume: {asset.label}').split())[:4000]
    row=existing or CampaignTemplate(source_resume=asset)
    row.name=name
    row.description=f'[Generated from Resume #{asset.pk}] Focused campaign template generated from selected Resume “{asset.label}”.'[:500]
    row.built_in=False; row.locations=allowed_locations; row.role_families=out_roles; row.technologies=out_terms
    row.engagement_types=['Full-time','Part-time','Contract','Agency / consulting','One-time project','Collaboration']
    row.company_sizes=[]; row.languages=[]; row.negative_constraints=''; row.extra_text=extra; row.recency_days=30
    row.source_names=[]; row.queries_per_rotation=None; row.source_resume=asset
    row.save()
    generated_at=timezone.now()
    asset.campaign_template_generated_at=generated_at
    asset.save(update_fields=['campaign_template_generated_at'])
    return {'created':0 if existing else 1,'regenerated':1 if existing else 0,'template_id':row.pk,'name':row.name,'resume_id':asset.pk,'roles':out_roles,'technologies':out_terms,'generated_at':generated_at.isoformat()}


def generate_all_resume_campaign_templates(prompt=''):
    """Generate/regenerate one template for every active Resume; never create Campaigns."""
    from portal.models import DocumentAsset
    results=[]; errors=[]
    for asset in DocumentAsset.objects.filter(kind='cv',active=True).order_by('created_at'):
        try:
            results.append(generate_resume_campaign_template(asset.pk,[],[],prompt))
        except Exception as exc:
            errors.append({'resume_id':asset.pk,'label':asset.label,'error':str(exc)[:500]})
    return {'processed':len(results)+len(errors),'succeeded':len(results),'failed':len(errors),'results':results,'errors':errors}
