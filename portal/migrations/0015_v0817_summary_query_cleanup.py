from django.db import migrations
import re

_GENERIC = re.compile(r'(?i)\bgeneric[\s-]*full[\s-]*stack\b')
_EXCLUDE = re.compile(r'(?<!\S)-(?:(?:"[^"]+")|(?:\'[^\']+\')|(?:[^\s]+))')
_WS = re.compile(r'\s+')

TOPICS = [
    ('reverse engineering', ('reverse engineering', 'reverse-engineering')),
    ('binary analysis', ('binary analysis', 'binary-analysis')),
    ('firmware', ('firmware',)),
    ('embedded systems', ('embedded system', 'embedded linux', 'embedded software')),
    ('device drivers', ('device driver', 'kernel driver')),
    ('emulation', ('emulation', 'emulator')),
    ('virtualization', ('virtualization', 'virtualisation', 'qemu')),
    ('legacy systems', ('legacy system', 'legacy software', 'retro computing')),
    ('protocols', ('protocol',)),
    ('hardware bring-up', ('hardware bring-up', 'board bring-up')),
]


def clean_queryish(value):
    text = str(value or '')
    text = _EXCLUDE.sub(' ', text)
    text = _GENERIC.sub(' ', text)
    return _WS.sub(' ', text).strip()


def clean_negatives(value):
    out = []
    for raw in re.split(r'[,;\n|]+', str(value or '')):
        term = raw.strip().lstrip('-').strip(' "\'')
        if not term or _GENERIC.search(term):
            continue
        if term.lower() not in {x.lower() for x in out}:
            out.append(term)
    return ', '.join(out)


def clean_list(value):
    if not isinstance(value, list):
        return value
    out = []
    for raw in value:
        item = clean_queryish(raw)
        if item and item not in out:
            out.append(item)
    return out


def clean_json(value):
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, str):
        return clean_queryish(value)
    return value


def compact_summary(company, text):
    clean = _WS.sub(' ', str(text or '')).strip().strip('"')
    blob = ' ' + clean.lower() + ' '
    topics = []
    for label, needles in TOPICS:
        if any(needle in blob for needle in needles):
            topics.append(label)
        if len(topics) >= 3:
            break
    if topics:
        if len(topics) == 1:
            work = topics[0]
        elif len(topics) == 2:
            work = topics[0] + ' and ' + topics[1]
        else:
            work = ', '.join(topics[:-1]) + ', and ' + topics[-1]
        result = f'{company} works on {work}.' if company else f'Organization works on {work}.'
    else:
        result = re.split(r'(?<=[.!?])\s+', clean, 1)[0].strip()
        if result and result[-1] not in '.!?':
            result += '.'
    words = result.split()
    if len(words) > 28:
        result = ' '.join(words[:28]).rstrip(' ,.;:') + '…'
    return result[:420]


def forwards(apps, schema_editor):
    Campaign = apps.get_model('portal', 'Campaign')
    Template = apps.get_model('portal', 'CampaignTemplate')
    Lead = apps.get_model('portal', 'CompanyLead')

    # Re-run the v0.8.16 cleanup because campaigns/caches created after that migration
    # may still contain engine-specific unary exclusions from older workers/containers.
    for row in Campaign.objects.all().iterator():
        changed = []
        for field in ('extra_text', 'role_families', 'technologies'):
            old = getattr(row, field, '')
            new = clean_queryish(old)
            if new != old:
                setattr(row, field, new); changed.append(field)
        old = row.negative_constraints
        new = clean_negatives(old)
        if new != old:
            row.negative_constraints = new; changed.append('negative_constraints')
        if changed:
            row.save(update_fields=changed)

    for row in Template.objects.all().iterator():
        changed = []
        for field in ('role_families', 'technologies'):
            old = getattr(row, field, None)
            new = clean_list(old)
            if new != old:
                setattr(row, field, new); changed.append(field)
        old = row.extra_text
        new = clean_queryish(old)
        if new != old:
            row.extra_text = new; changed.append('extra_text')
        old = row.negative_constraints
        new = clean_negatives(old)
        if new != old:
            row.negative_constraints = new; changed.append('negative_constraints')
        if changed:
            row.save(update_fields=changed)

    surfaces = [
        ('CampaignRun', ('criteria', 'query_plan', 'result')),
        ('BackgroundJob', ('result',)),
        ('UsageMetric', ('metadata',)),
        ('Profile', ('scope_json',)),
        ('DiagnosticRun', ('criteria', 'result')),
    ]
    for model_name, fields in surfaces:
        Model = apps.get_model('portal', model_name)
        for row in Model.objects.all().iterator():
            changed = []
            for field in fields:
                old = getattr(row, field, None)
                if not old:
                    continue
                new = clean_json(old)
                if new != old:
                    setattr(row, field, new); changed.append(field)
            if changed:
                row.save(update_fields=changed)

    Performance = apps.get_model('portal', 'PerformanceRun')
    for row in Performance.objects.all().iterator():
        changed = []
        old = row.input_text
        new = clean_queryish(old)
        if new != old:
            row.input_text = new; changed.append('input_text')
        old = row.metadata
        new = clean_json(old)
        if new != old:
            row.metadata = new; changed.append('metadata')
        if changed:
            row.save(update_fields=changed)

    SavedFilter = apps.get_model('portal', 'SavedFilter')
    for row in SavedFilter.objects.all().iterator():
        old = row.query_string
        new = clean_queryish(old)
        if new != old:
            row.query_string = new
            row.save(update_fields=['query_string'])

    # Rebuild persisted Market Studies summaries from the underlying evidence so the
    # list contains a genuine one-line description instead of a clipped old paragraph.
    for row in Lead.objects.all().iterator():
        evidence = ' '.join(x for x in (row.evidence, row.match_summary, row.summary) if x)
        summary = compact_summary(row.company, evidence)
        if summary != row.summary:
            row.summary = summary
            row.save(update_fields=['summary'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0014_v0816_reliability_read_state')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
