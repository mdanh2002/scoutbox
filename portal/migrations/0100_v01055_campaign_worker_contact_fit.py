from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def _clean_email(value):
    return str(value or '').strip().lower()


def _has_fit(intel):
    if not isinstance(intel, dict):
        return False
    fit = intel.get('fit_classification')
    return isinstance(fit, dict) and fit.get('score') not in (None, '')


def _company_slug(value):
    import re
    text = ' '.join(str(value or '').split()).casefold()
    text = re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co|pte)\b\.?', ' ', text)
    return re.sub(r'[^a-z0-9]+', '', text)


def _company_intel_has_display(intel):
    if not isinstance(intel, dict):
        return False
    for key in ('employee_count','employee_range','company_size_label','founded_year','domain_registered_at','domain_age_years','industry','website','country'):
        if intel.get(key) not in (None, '', [], {}):
            return True
    return False


def _related_fit(Contact, Opportunity, CompanyLead, contact):
    email = _clean_email(getattr(contact, 'email', '') or '')
    company = ' '.join(str(getattr(contact, 'company', '') or '').split()).strip()
    source_url = str(getattr(contact, 'source_url', '') or '').strip()
    q = Q()
    if email:
        q |= Q(contact_email__iexact=email)
    if source_url:
        q |= Q(url__iexact=source_url) | Q(target_url__iexact=source_url) | Q(search_url__iexact=source_url) | Q(canonical_url__iexact=source_url)
    if company and len(company) >= 3:
        q |= Q(company__iexact=company)
    if q:
        try:
            opp = Opportunity.objects.filter(q, user_deleted=False, suppressed=False).exclude(status='rejected').order_by('-fit_score','-last_seen').first()
            if opp and int(opp.fit_score or 0) > 0:
                return max(0, min(100, int(opp.fit_score or 0))), 'originating Opportunity', opp.pk
        except Exception:
            pass
    q = Q()
    if email:
        q |= Q(contact_email__iexact=email)
    if source_url:
        q |= Q(target_url__iexact=source_url) | Q(source_url__iexact=source_url) | Q(search_url__iexact=source_url)
    if company and len(company) >= 3:
        q |= Q(company__iexact=company)
    if q:
        try:
            lead = CompanyLead.objects.filter(q, user_deleted=False, deleted_at__isnull=True).order_by('-score','-updated_at').first()
            if lead and int(lead.score or 0) > 0:
                return max(0, min(100, int(lead.score or 0))), 'originating Hidden Lead', lead.pk
        except Exception:
            pass
    return None, '', None


def _heuristic_fit(contact):
    intel = contact.company_intel if isinstance(contact.company_intel, dict) else {}
    company = ' '.join(str(contact.company or '').split()).strip()
    source_url = str(contact.source_url or '').strip()
    summary = ' '.join(str(contact.company_summary or '').split()).strip()
    title = ' '.join(str(contact.title or '').split()).strip()
    notes = ' '.join(str(contact.notes or '').split()).strip()
    source = ' '.join(str(contact.source or '').split()).strip().casefold()
    manual = (source == 'manual')
    evidence_count = sum(1 for value in (company, source_url, summary, title, notes) if value)
    has_company_intel = _company_intel_has_display(intel)
    if manual and evidence_count < 2 and not has_company_intel:
        return None, 0, 'Manual Address Book contact has not been Fit-assessed yet.'
    score = 40
    if company: score += 8
    if title: score += 6
    if source_url: score += 6
    if summary: score += 8
    if has_company_intel: score += 8
    if notes: score += 4
    try:
        c = int(contact.confidence or 0)
    except Exception:
        c = 0
    if c >= 80:
        score += 5
    elif c < 50:
        score -= 5
    return max(25, min(70, score)), (35 if not manual else 25), 'Deterministic fallback from Address Book company/contact evidence; direct AI Fit assessment was unavailable or inconclusive.'


def forwards(apps, schema_editor):
    Contact = apps.get_model('portal', 'Contact')
    Opportunity = apps.get_model('portal', 'Opportunity')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    now = timezone.now().isoformat()
    for contact in Contact.objects.filter(deleted_at__isnull=True).iterator(chunk_size=100):
        intel = contact.company_intel if isinstance(contact.company_intel, dict) else {}
        if _has_fit(intel):
            continue
        score, origin, origin_id = _related_fit(Contact, Opportunity, CompanyLead, contact)
        if score is not None:
            intel['fit_classification'] = {
                'score': int(score), 'confidence': 55,
                'reason': f'Inherited from the {origin} that produced or matches this Address Book entry.',
                'source': 'Address Book inherited Fit fallback', 'origin': origin,
                'origin_id': origin_id, 'at': now,
            }
            intel['inherited_fit'] = {
                'score': int(score), 'source': origin, 'origin_id': origin_id,
                'reason': 'Temporary fallback until direct Address Book Fit assessment succeeds.', 'at': now,
            }
            contact.company_intel = intel
            contact.save(update_fields=['company_intel'])
            continue
        score, confidence, reason = _heuristic_fit(contact)
        if score is not None:
            intel['fit_classification'] = {
                'score': int(score), 'confidence': int(confidence),
                'reason': reason, 'source': 'Address Book deterministic fallback',
                'provider': 'deterministic', 'model': 'addressbook-v1', 'at': now,
            }
            contact.company_intel = intel
            contact.save(update_fields=['company_intel'])
        else:
            intel['fit_assessment_error'] = reason[:300]
            contact.company_intel = intel
            contact.save(update_fields=['company_intel'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0099_v01054_role_location_json_cleanup'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
