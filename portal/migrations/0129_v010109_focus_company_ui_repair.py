from django.db import migrations
from django.db.models import Q
import re

FOCUS_UNCLASSIFIED='Unclassified'
BAD_FOCUS_VALUES={
    'embedded','firmware','writing','would useful','explore firmware','legacy','c++','cplusplus',
    'protocol reverse','security tls','embedded integration','embedded low-level','application engineer',
    'software engineer','engineer','developer','cloud technology',
}
FOCUS_REWRITES={
    'buildroot yocto':'Embedded Linux',
    'yocto buildroot':'Embedded Linux',
    'qemu':'Systems Emulation',
    'protocol reverse':'Reverse Engineering',
    'security tls':'Network Security',
    'tls security':'Network Security',
    'writing':'Technical Documentation',
    'explore firmware':'Embedded Firmware',
    'embedded integration':'Embedded Firmware',
    'embedded low-level':'Low-Level Systems',
}
FRAGMENT_WORDS={
    'our','your','their','this','that','these','those','allows','allowing','helps','helping','provides','provide','offers','offering','through','while','where',
    'with','using','building','developing','designing','scalability','experience','responsibilities','requirements','required','across','including','supporting','focusing','focused','partnering','improving','delivering','updated','verified','integrates','integrating','recommends','recommend',
}
CORP_WORDS={'inc','incorporated','llc','ltd','limited','corp','corporation','company','co','gmbh','plc','pty','group','holdings','technologies','technology','systems','labs','laboratories','studio','studios','university','institute','foundation'}
UI_MARKERS=('employers register','register for free','post a job','products & prices','products and prices','customer service','job search','search jobs','our technology','this role','this position')
PLATFORM_NAMES={'workopolis','indeed','linkedin','jobsdb','jobstreet','glassdoor','himalayas','built in','builtin','coursera','gulftalent'}

def key(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).strip()

def bad_company(value):
    raw=' '.join(str(value or '').split()).strip(' -–—|:;,')
    if not raw:
        return False
    k=key(raw); words=[w for w in k.split() if w]
    if not words:
        return True
    if k in PLATFORM_NAMES or k.replace(' ','') in {x.replace(' ','') for x in PLATFORM_NAMES}:
        return True
    if any(marker in raw.casefold() for marker in UI_MARKERS):
        return True
    if words[0] in FRAGMENT_WORDS:
        return True
    has_corp=bool(set(words)&CORP_WORDS)
    if len(words)>=4 and not has_corp and any(w in FRAGMENT_WORDS for w in words):
        return True
    if len(words)>=6 and not has_corp:
        return True
    return False

def repair_focus(apps, schema_editor):
    for model_name, meta_field in (('Opportunity','extracted_facts'),('CompanyLead','company_intel'),('Contact','company_intel')):
        Model=apps.get_model('portal',model_name)
        fields={f.name for f in Model._meta.fields}
        qs=Model.objects.all()
        if 'user_deleted' in fields: qs=qs.filter(user_deleted=False)
        if 'suppressed' in fields: qs=qs.filter(suppressed=False)
        if 'deleted_at' in fields: qs=qs.filter(deleted_at__isnull=True)
        for row in qs.only('pk','focus',meta_field).iterator(chunk_size=500):
            old=str(getattr(row,'focus','') or '').strip()
            folded=old.casefold()
            if not old:
                continue
            new=FOCUS_REWRITES.get(folded)
            if new is None and (folded in BAD_FOCUS_VALUES or folded==FOCUS_UNCLASSIFIED.casefold()):
                new=''
            if new is None:
                continue
            setattr(row,'focus',new)
            if meta_field in fields:
                payload=getattr(row,meta_field,None)
                payload=dict(payload) if isinstance(payload,dict) else {}
                payload['focus_assignment']={'source':'v010109_focus_sanity_repair','previous_focus':old,'release':'0.10.109'}
                setattr(row,meta_field,payload)
                row.save(update_fields=['focus',meta_field])
            else:
                row.save(update_fields=['focus'])

def repair_company_fragments(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    for Model, fields in ((Opportunity,('company','extracted_facts')), (CompanyLead,('company','company_intel')), (Contact,('company','company_intel'))):
        meta=fields[1]
        for row in Model.objects.all().only('pk',*fields).iterator(chunk_size=500):
            old=str(getattr(row,'company','') or '').strip()
            if not bad_company(old):
                continue
            setattr(row,'company','')
            payload=getattr(row,meta,None)
            payload=dict(payload) if isinstance(payload,dict) else {}
            payload['company_identity_repair']={'source':'v010109_sentence_fragment_cleanup','previous_company':old[:220],'release':'0.10.109'}
            setattr(row,meta,payload)
            row.save(update_fields=['company',meta])

def forwards(apps, schema_editor):
    repair_focus(apps, schema_editor)
    repair_company_fragments(apps, schema_editor)
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    state=dict(ps.focus_taxonomy_state or {})
    # Kill leftover focus jobs from older releases so they cannot repopulate the
    # taxonomy after this sanity repair.
    try:
        from django.utils import timezone
        now=timezone.now()
        BackgroundJob.objects.filter(status__in=['queued','running']).filter(label__icontains='Focus').update(
            status='stopped',message='Superseded by ScoutBox 0.10.109 Focus taxonomy repair',finished_at=now
        )
    except Exception:
        pass
    # Rebuild each namespace with the current deterministic, non-network balancer.
    # This repairs the 0.10.108 state where too many rows were left Unclassified.
    focus_results={}
    try:
        from portal.services.focus import repair_model_focus_taxonomy
        target=int(getattr(ps,'max_focus_groups',15) or 15)
        focus_results={
            'opportunities':repair_model_focus_taxonomy(Opportunity,target,rewrite=True),
            'hidden_leads':repair_model_focus_taxonomy(CompanyLead,target,rewrite=True),
            'address_book':repair_model_focus_taxonomy(Contact,target,rewrite=True),
        }
    except Exception as exc:
        focus_results={'error':str(exc)[:500]}
    state['focus_quality_release']='0.10.109'
    state['unclassified_filter_includes_blank']=True
    state['company_fragment_cleanup']='0.10.109'
    state['v010109_focus_repair']=focus_results
    ps.focus_taxonomy_state=state
    ps.focus_taxonomy_version='0.10.109'
    ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version'])

class Migration(migrations.Migration):
    dependencies=[('portal','0128_v010108_focus_balance')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
