from django.db import migrations
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from collections import Counter, defaultdict
import math
import re

FOCUS_UNCLASSIFIED='Unclassified'
STOP={
    'a','an','and','or','the','to','of','for','in','on','with','from','at','as','by','is','are','be','this','that','their','our','your','you','we','it',
    'role','job','jobs','team','company','companies','senior','staff','lead','principal','junior','developer','specialist','remote','full','time','work','working','position','opportunity',
    'develop','developing','build','building','built','create','creating','deliver','delivering','provide','providing','key','responsibility','responsibilities','include','includes','including','required','requires','require','requirements','experience','experienced','knowledge','benefit','benefits','flexible','shift','shifts','remote-first','hybrid','onsite','on-site','office','offices','location','locations','salary','annual','hourly','usd','cad','eur','aud','gbp','dallas','houston','austin','boston','chicago','vancouver','toronto','london','spain','egypt','india','singapore','united','states','usa','us','uk','tx','ca','co','ct','fl','ny','pa','wa','bc','on','am',
    'ago','day','days','week','weeks','month','months','year','years','posted','posting','applicants','applicant','apply','applied','linkedin','user','users','agree','agreement','privacy','policy','terms','condition','conditions','click','clicking','continue','join','before','deciding','whether','good','fit','fits','more','exclusive','cover','letter','assistant','compensation','details','process','among','first','see','who','login','log','sign','signup','register','registration','share','save','view','original','easy',
    'profile','candidate','hiring','careers','career','about','new','opening','open','vacancy','vacancies','apply','needed','need','looking','seek','seeks','seeking',
}
GENERIC={
    'engineer','engineering','developer','development','manager','management','specialist','consultant','analyst','architect','administrator','admin',
    'senior','staff','lead','principal','expert','role','job','jobs','software','systems','system','platform','platforms','technical','technology','application','applications',
    'service','services','solution','solutions','product','products','project','program','business','operations','operation','support','customer','customers','team',
}
GENERIC_LABELS={
    'software','software engineer','software engineering','engineering','technology','cloud technology','application engineer','applications engineer',
    'application engineering','developer','engineer','systems engineer','platform engineer','technical specialist','jobs','job','remote','general',
    'misc','miscellaneous','other','others','professional','business','technical','unknown','unclassified',
}
NS={'Opportunity':'opportunities','CompanyLead':'hidden_leads','Contact':'address_book'}
CAMPAIGN_PREFIX_RE=re.compile(r'(?i)^\s*(?:profile|campaign|template|search|source)\s*[-—:]+\s*')


def normalize_token(token):
    t=str(token or '').casefold().strip("._-–—,:;()[]{}'\"")
    aliases={'.net':'dotnet','net':'dotnet','c++':'cplusplus','cpp':'cplusplus','cplusplus':'cplusplus','c#':'csharp','csharp':'csharp','node.js':'nodejs','nodejs':'nodejs'}
    return aliases.get(t,t)


def ordered_tokens(text, keep_generic=False):
    raw=re.findall(r'[a-z0-9+#.][a-z0-9+#.\-]{1,30}',str(text or '').casefold())
    out=[]
    for w in raw:
        t=normalize_token(w)
        if len(t)<2 or t in STOP or re.fullmatch(r'\d+\+?', t):
            continue
        if not keep_generic and t in GENERIC:
            continue
        out.append(t)
    return out


def title_token(t):
    special={'iot':'IoT','ai':'AI','ml':'ML','api':'API','apis':'APIs','ui':'UI','ux':'UX','qa':'QA','sre':'SRE','devops':'DevOps','aws':'AWS','gcp':'GCP','azure':'Azure','linux':'Linux','unix':'Unix','rtos':'RTOS','qemu':'QEMU','bios':'BIOS','uefi':'UEFI','sdk':'SDK','ios':'iOS','macos':'macOS','gpu':'GPU','fpga':'FPGA','rf':'RF','sdio':'SDIO','usb':'USB','ble':'BLE','nfc':'NFC','crm':'CRM','erp':'ERP','soc':'SOC','siem':'SIEM','edr':'EDR','xdr':'XDR','dotnet':'.NET','cplusplus':'C++','csharp':'C#','nodejs':'Node.js'}
    return special.get(t,t[:1].upper()+t[1:])


def label_from_tokens(tokens):
    cleaned=[]
    for t in tokens:
        t=normalize_token(t)
        if not t or t in STOP:
            continue
        cleaned.append(t)
    dedup=[]
    for t in cleaned:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    cleaned=dedup
    if cleaned[:2] in (['reverse','engineering'], ['reverse','engineer']):
        return 'Reverse Engineering'
    while cleaned and cleaned[-1] in GENERIC:
        cleaned.pop()
    while cleaned and cleaned[0] in GENERIC:
        cleaned.pop(0)
    if not cleaned:
        return ''
    return ' '.join(title_token(t) for t in cleaned[:4])


def distinctive(label):
    return {t for t in ordered_tokens(label,True) if t not in GENERIC and len(t)>=3}


def is_generic_label(value):
    label=' '.join(str(value or '').replace('/',' and ').replace('\\',' and ').replace('|',' and ').split())
    folded=label.casefold().strip()
    if not folded or folded in GENERIC_LABELS:
        return True
    toks=ordered_tokens(label,True)
    dist=[t for t in toks if t not in GENERIC and t not in STOP]
    if not dist:
        return True
    if len(dist)==1 and any(t in GENERIC for t in toks) and dist[0] in {'firmware','cloud','application','software','platform','system','systems','technology','technical'}:
        return True
    if len(toks)<=2 and all(t in GENERIC or t in {'cloud','application','software','platform','technology'} for t in toks):
        return True
    return False


def sanitize(value):
    text=' '.join(str(value or '').replace('/',' and ').replace('\\',' and ').replace('|',' and ').split())
    text=re.sub(r'(?i)\s+&\s+',' and ',text)
    text=CAMPAIGN_PREFIX_RE.sub('',text)
    text=re.sub(r'^[\-–—:;,\.\s]+|[\-–—:;,\.\s]+$','',text)
    words=text.split()
    if len(words)>5:
        text=' '.join(words[:5])
    if not text or len(text)>72 or is_generic_label(text):
        return ''
    return text


def clean_json(value):
    safe_keys={
        'role_title','title','summary','highlight','description','skills','skill','technologies','technology','keywords','keyword','categories','category',
        'technical_areas','technical_area','job_categories','job_category','requirements','responsibilities','industry','industries','product','products',
        'service_line','business_area','domain','domains','ai_job_summary','local_pre_persistence_review',
    }
    noisy=('html','source_text','raw','page_text','scraped','reason','fit_reason','remote','location','country','provenance','focus','url','date','posted','fetch','error')
    def collect(obj,key_hint=''):
        key_l=str(key_hint or '').casefold()
        if any(x in key_l for x in noisy): return []
        if isinstance(obj,(str,int,float)):
            return [str(obj)] if (not key_l or key_l in safe_keys or any(k in key_l for k in safe_keys)) else []
        if isinstance(obj,list):
            parts=[]
            for item in obj[:24]: parts.extend(collect(item,key_hint))
            return parts
        if isinstance(obj,dict):
            parts=[]
            for k,v in obj.items():
                k_l=str(k or '').casefold()
                if k_l in safe_keys or any(sk in k_l for sk in safe_keys):
                    parts.extend(collect(v,k_l))
                elif isinstance(v,dict) and k_l in {'ai_job_summary','local_pre_persistence_review'}:
                    parts.extend(collect(v,k_l))
            return parts
        return []
    if not isinstance(value,dict): return ''
    return ' '.join(collect(value))


def row_text(row):
    cls=row.__class__.__name__
    if cls=='Opportunity':
        vals=[row.title,row.list_highlight,clean_json(row.extracted_facts)]
    elif cls=='CompanyLead':
        vals=[row.summary,row.match_summary,row.evidence,clean_json(row.company_intel)]
    elif cls=='Contact':
        vals=[row.title,row.company_summary,row.notes,clean_json(row.company_intel)]
    else:
        vals=[]
    return ' '.join(str(x or '') for x in vals)[:8000]


def campaign_hint(row):
    try:
        c=getattr(row,'origin_campaign',None)
        if not c: return ''
        parts=[]
        for field in ('name','template','role_families','technologies'):
            val=str(getattr(c,field,'') or '').strip()
            if val: parts.append(val)
        return ' · '.join(parts)[:700]
    except Exception:
        return ''


def candidate_phrases(row, include_existing=False):
    body=row_text(row); cls=row.__class__.__name__
    if cls=='Opportunity':
        title=str(row.title or '')
    elif cls=='CompanyLead':
        title=str(row.summary or '')
    elif cls=='Contact':
        title=' '.join([str(row.title or ''),str(row.company_summary or '')])
    else:
        title=body[:500]
    row_tokens=set(ordered_tokens(body,True)); cands=[]
    def add(label,score,source):
        clean=sanitize(label)
        if clean:
            cands.append((clean,float(score),source))
    if include_existing:
        add(getattr(row,'focus','') or '',1.0,'existing')
    hint=campaign_hint(row)
    segments=[seg.strip() for seg in re.split(r'[·;,]+', CAMPAIGN_PREFIX_RE.sub('',hint)) if seg.strip()]
    for seg in segments[:18]:
        seg=CAMPAIGN_PREFIX_RE.sub('',seg)
        ht=ordered_tokens(seg,True); hd=[t for t in ht if t not in GENERIC and t not in STOP]
        if hd and row_tokens.intersection(hd):
            add(label_from_tokens(ht),3.5,'campaign_supported')
            meaningful=[t for t in ordered_tokens(title+' '+body,False) if t not in hd][:8]
            if len(hd)==1 and meaningful:
                for extra in meaningful[:4]:
                    if extra!=hd[0]:
                        add(label_from_tokens([extra,hd[0]]),3.2,'campaign_refined')
                        add(label_from_tokens([hd[0],extra]),3.0,'campaign_refined')

    tt=ordered_tokens(title,True)
    add(label_from_tokens(tt),3.0,'title')
    tm=[t for t in tt if t not in GENERIC]
    if len(tm)>=2:
        for n in (3,2):
            for i in range(0,max(0,len(tm)-n+1)):
                add(label_from_tokens(tm[i:i+n]),2.7,'title_ngram')
    bt=ordered_tokens(body,False); made=0
    for n,base in ((3,1.9),(2,1.7)):
        for i in range(0,max(0,len(bt)-n+1)):
            window=bt[i:i+n]
            if len(set(window))<len(window):
                continue
            add(label_from_tokens(window),base,'content_ngram'); made+=1
            if made>=80:
                break
        if made>=80:
            break
    for t in bt[:80]:
        if len(t)>=5 and t not in {'firmware','cloud','software','system','systems','platform','application','technology'}:
            add(label_from_tokens([t]),0.7,'content_token')
    best={}
    for label,score,source in cands:
        key=label.casefold()
        if key not in best or score>best[key][1]:
            best[key]=(label,score,source)
    return sorted(best.values(),key=lambda x:(-x[1],x[0].casefold()))[:24]


def min_group(total):
    if total<20: return 1
    if total<100: return 2
    return 3


def max_group(total,target):
    total=max(1,int(total or 1)); target=max(5,min(30,int(target or 15)))
    return max(min_group(total)*2, min(int(math.ceil(total*0.32)), int(math.ceil((total/max(1,target))*2.5))))


def label_similarity(a,b):
    ta=distinctive(a); tb=distinctive(b)
    if not ta or not tb: return 0.0
    return len(ta&tb)/max(1.0,math.sqrt(len(ta)*len(tb)))


def select_labels(records,target):
    total=len(records); minsz=min_group(total); target=max(3,int(math.ceil(max(5,min(30,target))*1.2)))
    counts=Counter(); weighted=Counter(); sources=defaultdict(Counter)
    for r in records:
        seen=set()
        for label,score,source in candidate_phrases(r,include_existing=False):
            if label.casefold() not in seen:
                counts[label]+=1; seen.add(label.casefold())
            weighted[label]+=score; sources[label][source]+=1
    candidates=[]
    for label,n in counts.items():
        if n<minsz or is_generic_label(label):
            continue
        bonus=0
        if sources[label].get('campaign_supported'): bonus+=2
        if sources[label].get('campaign_refined'): bonus+=1.5
        if sources[label].get('title') or sources[label].get('title_ngram'): bonus+=1
        candidates.append((label,n,float(n)*3+float(weighted[label])*0.35+bonus+min(.8,.2*len(distinctive(label)))))
    candidates.sort(key=lambda x:(-x[2],-x[1],x[0].casefold()))
    selected=[]
    for label,n,score in candidates:
        too_close=False
        for existing in selected:
            if label_similarity(label,existing)>=0.92:
                too_close=True; break
        if too_close: continue
        selected.append(label)
        if len(selected)>=target: break
    return selected


def assign_records(records,labels,target):
    if not records or not labels: return {}
    total=len(records); minsz=min_group(total); cap=max_group(total,target); selected={l.casefold():l for l in labels}
    choices=[]
    for r in records:
        row_tokens=set(ordered_tokens(row_text(r),True)); row_choices=[]
        for label,score,source in candidate_phrases(r,include_existing=False):
            canon=selected.get(label.casefold())
            if not canon: continue
            if not (distinctive(canon)&row_tokens): continue
            row_choices.append((canon,score,source))
        row_choices.sort(key=lambda x:(-x[1],x[0].casefold()))
        choices.append((r,row_choices))
    choices.sort(key=lambda item: (-(item[1][0][1] if item[1] else 0), int(item[0].pk)))
    mapping={}; counts=Counter()
    for r,row_choices in choices:
        chosen=''
        for label,score,source in row_choices:
            if counts[label]<cap:
                chosen=label; break
        if not chosen and row_choices:
            chosen=row_choices[0][0]
        if chosen:
            mapping[int(r.pk)]=chosen; counts[chosen]+=1
    if minsz>1:
        small={label for label,n in counts.items() if n<minsz}
        stable=[label for label,n in counts.items() if n>=minsz]
        for pk,label in list(mapping.items()):
            if label not in small: continue
            best=''; bs=0
            for dest in stable:
                sim=label_similarity(label,dest)
                if sim>bs: best=dest; bs=sim
            if best and bs>=0.34:
                mapping[pk]=best
            else:
                mapping.pop(pk,None)
    return mapping


def active_qs(model):
    fields={f.name for f in model._meta.fields}
    qs=model.objects.all()
    if 'user_deleted' in fields: qs=qs.filter(user_deleted=False)
    if 'suppressed' in fields: qs=qs.filter(suppressed=False)
    if 'deleted_at' in fields: qs=qs.filter(deleted_at__isnull=True)
    return qs


def json_field(model):
    if model.__name__=='Opportunity': return 'extracted_facts'
    if model.__name__ in {'CompanyLead','Contact'}: return 'company_intel'
    return ''


def quality_bad(model,target):
    qs=active_qs(model); total=qs.count()
    if total<20: return False
    rows=list(qs.exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).values('focus').annotate(n=Count('pk')).order_by('-n','focus'))
    if not rows: return True
    top=int(rows[0].get('n') or 0)
    singletons=sum(1 for r in rows if int(r.get('n') or 0)==1)
    generic=any(is_generic_label(str(r.get('focus') or '')) for r in rows)
    classified=sum(int(r.get('n') or 0) for r in rows)
    return top>max_group(total,target) or singletons>max(2,len(rows)//4) or generic or (total-classified>max(10,total//2) and total>=40)


def repair_model(model,target,now):
    qs=active_qs(model).order_by('pk')
    total=qs.count(); classified=qs.exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).count()
    if total<3:
        return {'namespace':NS.get(model.__name__,model.__name__),'total':int(total),'changed':0,'reason':'too-small'}
    if not quality_bad(model,target):
        return {'namespace':NS.get(model.__name__,model.__name__),'total':int(total),'classified':int(classified),'changed':0,'reason':'quality-ok'}
    records=list(qs)
    labels=select_labels(records,target)
    mapping=assign_records(records,labels,target)
    jf=json_field(model); changed=[]
    for row in records:
        new=mapping.get(int(row.pk),'')
        old=str(getattr(row,'focus','') or '')
        if old==new: continue
        row.focus=new
        if jf:
            payload=getattr(row,jf,None)
            payload=dict(payload) if isinstance(payload,dict) else {}
            payload['focus_assignment']={
                'namespace':NS.get(model.__name__,model.__name__),
                'source':'v010108_balanced_taxonomy_repair',
                'previous_focus':old[:80],
                'confidence':74 if new else 0,
                'reason':'Balanced same-list Focus repair using record content and campaign-supported naming hints.',
                'assigned_at':now.isoformat(),
                'release':'0.10.108',
            }
            setattr(row,jf,payload)
        changed.append(row)
    if changed:
        fields=['focus'] + ([jf] if jf else [])
        model.objects.bulk_update(changed,fields,batch_size=500)
    return {'namespace':NS.get(model.__name__,model.__name__),'total':int(total),'classified_before':int(classified),'changed':len(changed),'assigned':sum(1 for x in mapping.values() if x),'groups':len(set(mapping.values())),'labels':labels[:30],'reason':'balanced-repair'}


def repair_v010108_state(apps, schema_editor):
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    PortalSettings=apps.get_model('portal','PortalSettings')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    now=timezone.now()
    BackgroundJob.objects.filter(status__in=['queued','running']).filter(label__in=['Refresh Focus taxonomy','Backfill blank Focus labels']).update(
        status='stopped',message='Superseded by ScoutBox 0.10.109 balanced Focus taxonomy repair',finished_at=now
    )
    BackgroundJob.objects.filter(status='running',label__icontains='Focus',created_at__lt=now-timedelta(minutes=15)).update(
        status='stopped',message='Stale Focus job superseded by ScoutBox 0.10.109 balanced repair',finished_at=now
    )
    ps=PortalSettings.objects.first()
    target=int(getattr(ps,'max_focus_groups',15) or 15) if ps else 15
    results={
        'opportunities':repair_model(Opportunity,target,now),
        'hidden_leads':repair_model(CompanyLead,target,now),
        'address_book':repair_model(Contact,target,now),
    }
    for row in PortalSettings.objects.all():
        state=dict(getattr(row,'focus_taxonomy_state',{}) or {})
        state['automatic_full_rebuild_disabled']=True
        state['campaign_dominance_assignment_disabled']=True
        state['balanced_focus_taxonomy_enabled']=True
        state['focus_namespaces']=['opportunities','hidden_leads','address_book']
        state['v010108_repair_at']=now.isoformat()
        state['v010108_balanced_repair']=results
        row.focus_taxonomy_state=state
        row.focus_taxonomy_version='0.10.109'
        row.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version'])


class Migration(migrations.Migration):
    dependencies=[('portal','0127_v010107_focus_repair')]
    operations=[migrations.RunPython(repair_v010108_state, migrations.RunPython.noop)]
