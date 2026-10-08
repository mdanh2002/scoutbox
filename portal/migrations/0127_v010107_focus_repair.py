from django.db import migrations
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import json
import math
import re

FOCUS_UNCLASSIFIED='Unclassified'
STOP={
    'a','an','and','or','the','to','of','for','in','on','with','from','at','as','by','is','are','be','this','that','their','our','your','you','we','it',
    'role','job','team','company','senior','staff','lead','principal','developer','specialist','remote','full','time','work','working','position','opportunity',
}
LABEL_GENERIC={
    'engineer','engineering','developer','development','manager','management','specialist','consultant','analyst','architect','administrator',
    'senior','staff','lead','principal','expert','role','job','jobs','software','systems','system','platform','platforms','technical','technology',
}


def tokens(text):
    words=re.findall(r'[a-z0-9][a-z0-9+#.\-]{1,30}',str(text or '').casefold())
    return {w.strip('._-') for w in words if len(w.strip('._-'))>=2 and w.strip('._-') not in STOP}


def clean_json(value):
    if not isinstance(value,dict):
        return ''
    parts=[]
    for key,val in value.items():
        if str(key).casefold().startswith('focus') or str(key).casefold() in {'focus_assignment','focus_repair'}:
            continue
        if isinstance(val,(str,int,float)):
            parts.append(str(val))
        elif isinstance(val,list):
            parts.extend(str(x) for x in val[:20] if isinstance(x,(str,int,float)))
        elif isinstance(val,dict):
            for sub_key,sub_val in val.items():
                if 'focus' in str(sub_key).casefold():
                    continue
                if isinstance(sub_val,(str,int,float)):
                    parts.append(str(sub_val))
                elif isinstance(sub_val,list):
                    parts.extend(str(x) for x in sub_val[:12] if isinstance(x,(str,int,float)))
    return ' '.join(parts)


def row_text(row):
    cls=row.__class__.__name__
    if cls=='Opportunity':
        vals=[row.title,row.company,row.list_highlight,row.description,row.raw_search_snippet,row.recommendation_reason,clean_json(row.extracted_facts)]
    elif cls=='CompanyLead':
        vals=[row.company,row.summary,row.match_summary,row.evidence,row.contact_name,clean_json(row.company_intel)]
    elif cls=='Contact':
        vals=[row.company,row.title,row.company_summary,row.name,row.email,row.notes,clean_json(row.company_intel)]
    else:
        vals=[]
    return ' '.join(str(x or '') for x in vals)


def distinctive(label):
    return {t for t in tokens(label) if t not in LABEL_GENERIC and len(t)>=3}


def supports(row,label):
    d=distinctive(label)
    if not d:
        return False
    return bool(tokens(row_text(row)) & d)


def active_qs(model):
    fields={f.name for f in model._meta.fields}
    qs=model.objects.all()
    if 'user_deleted' in fields:
        qs=qs.filter(user_deleted=False)
    if 'suppressed' in fields:
        qs=qs.filter(suppressed=False)
    if 'deleted_at' in fields:
        qs=qs.filter(deleted_at__isnull=True)
    return qs


def json_field_for(model):
    name=model.__name__
    if name=='Opportunity':
        return 'extracted_facts'
    if name in {'CompanyLead','Contact'}:
        return 'company_intel'
    return ''


def mark_cleared(row,json_field,previous,now,reason):
    updates={'focus':''}
    setattr(row,'focus','')
    if json_field:
        payload=getattr(row,json_field,None)
        if isinstance(payload,dict):
            payload=dict(payload)
        else:
            payload={}
        payload['focus_assignment']={
            'source':'v010107_dominance_repair',
            'previous_focus':str(previous or '')[:80],
            'reason':reason[:300],
            'assigned_at':now.isoformat(),
            'release':'0.10.107',
        }
        setattr(row,json_field,payload)
        updates[json_field]=payload
    row.__class__.objects.filter(pk=row.pk).update(**updates)


def repair_model(model,now):
    qs=active_qs(model)
    total=qs.count()
    classified_qs=qs.exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED)
    classified=classified_qs.count()
    if total<20 or classified<20:
        return {'total':int(total),'classified':int(classified),'dominant':'','cleared':0,'kept':0,'reason':'below-threshold'}
    groups=list(classified_qs.values('focus').annotate(n=Count('pk')).order_by('-n','focus')[:8])
    if not groups:
        return {'total':int(total),'classified':int(classified),'dominant':'','cleared':0,'kept':0,'reason':'no-groups'}
    top=groups[0]
    label=str(top.get('focus') or '').strip()
    n=int(top.get('n') or 0)
    classified_ratio=n/max(1,classified)
    total_ratio=n/max(1,total)
    if not label or n<20 or (classified_ratio<0.72 and total_ratio<0.58):
        return {'total':int(total),'classified':int(classified),'dominant':label,'dominant_count':n,'cleared':0,'kept':0,'classified_ratio':classified_ratio,'total_ratio':total_ratio,'reason':'not-suspicious'}
    cleared=0; kept=0
    json_field=json_field_for(model)
    for row in classified_qs.filter(focus=label).iterator(chunk_size=400):
        if supports(row,label):
            kept+=1
            continue
        mark_cleared(row,json_field,label,now,'Dominant Focus lacked direct support in this record content; cleared for safe reclassification.')
        cleared+=1
    return {'total':int(total),'classified':int(classified),'dominant':label,'dominant_count':n,'cleared':cleared,'kept':kept,'classified_ratio':classified_ratio,'total_ratio':total_ratio,'reason':'suspicious-dominance-repaired'}


def repair_v010107_state(apps, schema_editor):
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    PortalSettings=apps.get_model('portal','PortalSettings')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    now=timezone.now()
    BackgroundJob.objects.filter(status__in=['queued','running']).filter(label__in=['Refresh Focus taxonomy','Backfill blank Focus labels']).update(
        status='stopped',message='Superseded by ScoutBox 0.10.107 content-only Focus repair',finished_at=now
    )
    BackgroundJob.objects.filter(status='running',label__icontains='Focus',created_at__lt=now-timedelta(minutes=30)).update(
        status='stopped',message='Stale Focus job superseded by ScoutBox 0.10.107',finished_at=now
    )
    results={
        'opportunities':repair_model(Opportunity,now),
        'hidden_leads':repair_model(CompanyLead,now),
        'contacts':repair_model(Contact,now),
    }
    for ps in PortalSettings.objects.all():
        state=dict(getattr(ps,'focus_taxonomy_state',{}) or {})
        state['automatic_full_rebuild_disabled']=True
        state['campaign_dominance_assignment_disabled']=True
        state['v010107_repair_at']=now.isoformat()
        state['v010107_dominance_repair']=results
        ps.focus_taxonomy_state=state
        ps.focus_taxonomy_version='0.10.107'
        ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version'])


class Migration(migrations.Migration):
    dependencies=[('portal','0126_v010106_focus_ui_cleanup')]
    operations=[migrations.RunPython(repair_v010107_state, migrations.RunPython.noop)]
