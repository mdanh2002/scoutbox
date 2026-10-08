from django.db import migrations, models
import re

_GENERIC=re.compile(r'(?i)\bgeneric[\s-]*full[\s-]*stack\b')
_EXCLUDE=re.compile(r'(?<!\S)-(?:(?:"[^"]+")|(?:\'[^\']+\')|(?:[^\s]+))')

def clean_queryish(value):
    text=str(value or '')
    text=_EXCLUDE.sub(' ',text)
    text=_GENERIC.sub(' ',text)
    return re.sub(r'\s+',' ',text).strip()

def clean_negatives(value):
    out=[]
    for raw in re.split(r'[,;\n|]+',str(value or '')):
        term=raw.strip().lstrip('-').strip(' "\'')
        if not term or _GENERIC.search(term):
            continue
        if term.lower() not in {x.lower() for x in out}: out.append(term)
    return ', '.join(out)

def clean_list(value):
    if not isinstance(value,list): return value
    out=[]
    for raw in value:
        item=clean_queryish(raw)
        if item and item not in out: out.append(item)
    return out

def clean_json(value):
    if isinstance(value,dict): return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,list): return [clean_json(v) for v in value]
    if isinstance(value,str): return clean_queryish(value)
    return value

def forwards(apps,schema_editor):
    Campaign=apps.get_model('portal','Campaign')
    Template=apps.get_model('portal','CampaignTemplate')
    Lead=apps.get_model('portal','CompanyLead')
    for row in Campaign.objects.all().iterator():
        row.negative_constraints=clean_negatives(row.negative_constraints)
        row.extra_text=clean_queryish(row.extra_text)
        row.role_families=clean_queryish(row.role_families)
        row.technologies=clean_queryish(row.technologies)
        row.save(update_fields=['negative_constraints','extra_text','role_families','technologies'])
    for row in Template.objects.all().iterator():
        row.negative_constraints=clean_negatives(row.negative_constraints)
        row.extra_text=clean_queryish(row.extra_text)
        row.role_families=clean_list(row.role_families)
        row.technologies=clean_list(row.technologies)
        row.save(update_fields=['negative_constraints','extra_text','role_families','technologies'])
    # Keep existing Market Study summaries compact after the upgrade too.
    for row in Lead.objects.exclude(summary='').iterator():
        words=str(row.summary or '').split()
        if len(words)>90:
            row.summary=' '.join(words[:90]).rstrip(' ,.;:')+'…'
            row.save(update_fields=['summary'])
    # Scrub every persisted query/cache surface used by reruns or activity history.
    Run=apps.get_model('portal','CampaignRun')
    for row in Run.objects.all().iterator():
        changed=[]
        for field in ('criteria','query_plan','result'):
            value=getattr(row,field,None)
            if value:
                new=clean_json(value)
                if new!=value: setattr(row,field,new); changed.append(field)
        if changed: row.save(update_fields=changed)
    Job=apps.get_model('portal','BackgroundJob')
    for row in Job.objects.all().iterator():
        value=getattr(row,'result',None)
        if value:
            new=clean_json(value)
            if new!=value: row.result=new; row.save(update_fields=['result'])
    Usage=apps.get_model('portal','UsageMetric')
    for row in Usage.objects.all().iterator():
        value=getattr(row,'metadata',None)
        if value:
            new=clean_json(value)
            if new!=value: row.metadata=new; row.save(update_fields=['metadata'])
    Profile=apps.get_model('portal','Profile')
    for row in Profile.objects.all().iterator():
        value=getattr(row,'scope_json',None)
        if value:
            new=clean_json(value)
            if new!=value: row.scope_json=new; row.save(update_fields=['scope_json'])
    Diagnostic=apps.get_model('portal','DiagnosticRun')
    for row in Diagnostic.objects.all().iterator():
        changed=[]
        for field in ('criteria','result'):
            value=getattr(row,field,None)
            if value:
                new=clean_json(value)
                if new!=value: setattr(row,field,new); changed.append(field)
        if changed: row.save(update_fields=changed)
    Performance=apps.get_model('portal','PerformanceRun')
    for row in Performance.objects.all().iterator():
        changed=[]
        for field in ('input_text','metadata'):
            value=getattr(row,field,None)
            if value:
                new=clean_json(value) if isinstance(value,(dict,list)) else clean_queryish(value)
                if new!=value: setattr(row,field,new); changed.append(field)
        if changed: row.save(update_fields=changed)
    SavedFilter=apps.get_model('portal','SavedFilter')
    for row in SavedFilter.objects.all().iterator():
        value=getattr(row,'query_string',None)
        if value:
            new=clean_queryish(value)
            if new!=value: row.query_string=new; row.save(update_fields=['query_string'])

class Migration(migrations.Migration):
    dependencies=[('portal','0013_v0815_attention_market_summary')]
    operations=[
        migrations.AddField(model_name='application',name='is_read',field=models.BooleanField(default=False,help_text='Whether this application draft has been reviewed in the UI.')),
        migrations.RunPython(forwards,migrations.RunPython.noop),
    ]
