from urllib.parse import urlsplit
from django.db import migrations

NOISE_DOMAINS=('youtube.com','music.youtube.com','youtu.be','wikipedia.org','learn.microsoft.com','msdn.microsoft.com','docs.microsoft.com','developer.mozilla.org','docs.python.org','docs.oracle.com','docs.github.com','docs.aws.amazon.com','man7.org','cran.r-project.org')

def host_of(value):
    try: return (urlsplit(value or '').netloc or '').lower().removeprefix('www.')
    except Exception: return ''

def cleanup(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    for row in Opportunity.objects.all().iterator():
        host=host_of(getattr(row,'target_url','') or getattr(row,'url',''))
        if any(host==d or host.endswith('.'+d) for d in NOISE_DOMAINS):
            if not row.suppressed:
                row.suppressed=True
                row.rejection_reason='Built-in non-opportunity source blacklist'
                row.save(update_fields=['suppressed','rejection_reason'])
    CompanyLead=apps.get_model('portal','CompanyLead')
    for row in CompanyLead.objects.all().iterator():
        host=host_of(getattr(row,'target_url','') or getattr(row,'source_url',''))
        if any(host==d or host.endswith('.'+d) for d in NOISE_DOMAINS):
            row.delete()
    Contact=apps.get_model('portal','Contact')
    for row in Contact.objects.filter(name__iexact='Contact').iterator():
        if row.company:
            row.name=''
        else:
            domain=(row.email.split('@',1)[1] if '@' in row.email else '').split('.',1)[0]
            row.company=domain.replace('-',' ').replace('_',' ').title()[:200] if domain else ''
            row.name=''
        row.save(update_fields=['name','company'])

def reverse(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0005_v083_blacklist_sources_language')]
    operations=[migrations.RunPython(cleanup,reverse)]
