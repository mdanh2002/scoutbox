import re
from django.db import migrations, models
import django.db.models.deletion


def _positive_int(value):
    try:
        value=int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _naver_title_contaminated(value):
    text=' '.join(str(value or '').split())
    low=text.casefold()
    if not text:
        return False
    if '새 창 열림' in text or 'keep에 저장' in low or 'keep에 바로가기' in low:
        return True
    if ' › ' in text and re.search(r'(?i)(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\s|›)', text):
        return True
    return False


_ROLE_WORDS=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|qa|support|administrator|analyst|programmer)\b')
_NOISE=re.compile(r'(?i)^(apply|jobs?|careers?|home|general|frontpage|description|responsibilities|requirements|about|posted via\b|모집분야|공고소개|주요업무)\b')


def _clean_candidate(value):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip(' -–—|·:;')
    for phrase in ('새 창 열림','Keep에 저장','Keep에 바로가기'):
        text=text.replace(phrase,' ')
    text=' '.join(text.split()).strip(' -–—|·:;')
    return text[:300]


def _repair_title_candidate(row):
    candidates=[]
    lines=[_clean_candidate(x) for x in str(row.description or '').splitlines()[:16]]
    for idx,line in enumerate(lines):
        if not line or len(line)<4 or len(line)>220:
            continue
        if _naver_title_contaminated(line) or _NOISE.search(line):
            continue
        if re.search(r'(?i)https?://|\bwww\.|\.[a-z]{2,}\s*[›/]',line):
            continue
        score=(8 if _ROLE_WORDS.search(line) else 0) + max(0,4-idx)
        if str(row.raw_search_snippet or '').casefold().find(line.casefold()) >= 0:
            score += 2
        candidates.append((score,idx,line))
    if candidates:
        candidates.sort(key=lambda x:(-x[0],x[1],len(x[2])))
        if candidates[0][0] >= 6:
            return candidates[0][2]

    # Naver public snippets usually place the human result title immediately after its
    # breadcrumb/accessibility chrome.  Use only a role-looking segment; otherwise leave
    # the historical row untouched rather than guessing.
    snippet=str(row.raw_search_snippet or '')
    cleaned=snippet
    for phrase in ('Keep에 저장','Keep에 바로가기','새 창 열림'):
        cleaned=cleaned.replace(phrase,'\n')
    for seg in cleaned.splitlines():
        seg=_clean_candidate(seg)
        if not seg or _naver_title_contaminated(seg) or len(seg)>220:
            continue
        if _ROLE_WORDS.search(seg):
            # Strip a leading date but keep punctuation inside the role title.
            seg=re.sub(r'^\d{4}\.\d{2}\.\d{2}\.\s*','',seg).strip()
            if seg and _ROLE_WORDS.search(seg):
                return seg[:300]
    return ''


def backfill_origin_and_repair_naver(apps, schema_editor):
    Campaign=apps.get_model('portal','Campaign')
    CampaignRun=apps.get_model('portal','CampaignRun')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    SearchSource=apps.get_model('portal','SearchSource')
    valid=set(Campaign.objects.values_list('pk',flat=True))

    # CampaignRun result membership is the strongest historical first-discovery evidence.
    # Oldest run wins; later M2M membership remains rediscovery provenance.
    for run in CampaignRun.objects.exclude(campaign_id__isnull=True).order_by('created_at','pk').iterator(chunk_size=250):
        if run.campaign_id not in valid or not isinstance(run.result,dict):
            continue
        opp_ids=[_positive_int(x) for x in (run.result.get('opportunity_ids') or [])]
        lead_ids=[_positive_int(x) for x in (run.result.get('lead_ids') or [])]
        opp_ids=[x for x in opp_ids if x]
        lead_ids=[x for x in lead_ids if x]
        if opp_ids:
            Opportunity.objects.filter(pk__in=opp_ids,origin_campaign__isnull=True).update(origin_campaign_id=run.campaign_id)
        if lead_ids:
            CompanyLead.objects.filter(pk__in=lead_ids,origin_campaign__isnull=True).update(origin_campaign_id=run.campaign_id)

    # Exact per-record provenance is next best. Only use IDs that still refer to a campaign.
    for lead in CompanyLead.objects.filter(origin_campaign__isnull=True).iterator(chunk_size=500):
        state=lead.ai_state if isinstance(lead.ai_state,dict) else {}
        usage=state.get('_usage') if isinstance(state.get('_usage'),dict) else {}
        cid=_positive_int(usage.get('campaign_id'))
        if cid in valid:
            CompanyLead.objects.filter(pk=lead.pk,origin_campaign__isnull=True).update(origin_campaign_id=cid)

    lead_origin=dict(CompanyLead.objects.exclude(origin_campaign__isnull=True).values_list('pk','origin_campaign_id'))
    for opp in Opportunity.objects.filter(origin_campaign__isnull=True).iterator(chunk_size=500):
        facts=opp.extracted_facts if isinstance(opp.extracted_facts,dict) else {}
        cid=_positive_int(facts.get('campaign_id'))
        if cid not in valid:
            lead_id=_positive_int(facts.get('market_study_lead_id'))
            cid=lead_origin.get(lead_id)
        if cid in valid:
            Opportunity.objects.filter(pk=opp.pk,origin_campaign__isnull=True).update(origin_campaign_id=cid)

    # A single historical M2M relation is unambiguous. Multiple relations without stronger
    # evidence stay unknown rather than assigning an arbitrary origin.
    for model in (Opportunity, CompanyLead):
        for row in model.objects.filter(origin_campaign__isnull=True).iterator(chunk_size=500):
            ids=list(row.campaigns.values_list('pk',flat=True)[:2])
            if len(ids)==1:
                model.objects.filter(pk=row.pk,origin_campaign__isnull=True).update(origin_campaign_id=ids[0])

    naver_ids=set(SearchSource.objects.filter(name__iexact='Naver').values_list('pk',flat=True))
    if naver_ids:
        for row in Opportunity.objects.filter(source_id__in=naver_ids).iterator(chunk_size=250):
            if not _naver_title_contaminated(row.title):
                continue
            candidate=_repair_title_candidate(row)
            if candidate and candidate != row.title and not _naver_title_contaminated(candidate):
                Opportunity.objects.filter(pk=row.pk).update(title=candidate[:300])


def reverse_noop(apps, schema_editor):
    # Origin attribution and repaired titles are valid provenance/data corrections.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0082_v01026_third_party_employer_repair')]
    operations=[
        migrations.AddField(
            model_name='opportunity',name='origin_campaign',
            field=models.ForeignKey(blank=True,help_text='Campaign that first discovered this opportunity. Later campaign matches remain in campaigns as rediscovery provenance.',null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='origin_opportunities',to='portal.campaign'),
        ),
        migrations.AddField(
            model_name='companylead',name='origin_campaign',
            field=models.ForeignKey(blank=True,help_text='Campaign that first discovered this Hidden Lead. Later campaign matches remain in campaigns as rediscovery provenance.',null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='origin_leads',to='portal.campaign'),
        ),
        migrations.RemoveField(model_name='portalsettings',name='search_jitter_percent'),
    ]
