from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def fail(message):
    raise SystemExit(f'FAIL: {message}')


if read('VERSION').strip() != '0.10.77':
    fail('VERSION is not 0.10.77')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.77':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.77':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.77'):
    fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.77.md').is_file():
    fail('0.10.77 release notes missing')

views = read('portal/views.py')
base = read('templates/portal/base.html')
opportunities = read('templates/portal/opportunities.html')
leads = read('templates/portal/cold_contact.html')
contacts = read('templates/portal/contacts.html')
telemetry = read('templates/portal/telemetry.html')
css = read('portal/static/portal/app.css')
mailbox = read('portal/services/mailbox.py')
migration = read('portal/migrations/0107_v01077_addressbook_audit_cleanup.py')
tests = read('portal/tests/test_v01077.py')

if "campaign_count_base.select_related(None).prefetch_related(None).only('pk','origin_campaign_id').distinct().prefetch_related('campaigns')" not in views:
    fail('Opportunity campaign facet still risks deferred-field/select_related FieldError')
if '_country_filter_total(country_options)' not in views:
    fail('country All totals are not derived from displayed options')
if views.count('_country_filter_total(country_options)') < 4:
    fail('country total invariant is not applied to all four list views')
if "annotate(n=Count('pk',distinct=True))" not in views:
    fail('facet option counts can still double-count joined rows')
if 'country_visible_ids=_hidden_lead_visible_ids(country_count_base)' not in views:
    fail('Hidden Lead country counts are not based on visible de-duplicated companies')

if 'splitTrailingOptionCount' not in base or 'searchable-select-count' not in base or 'country-option-count' not in base:
    fail('count-preserving dropdown rendering is missing')
if 'searchable-select-count' not in css or 'country-option-count' not in css:
    fail('count-preserving dropdown CSS is missing')
if 'Select filter conditions, then click Apply.' not in opportunities or 'Select filter conditions, then click Apply.' not in leads or 'Select filter conditions, then click Apply.' not in contacts:
    fail('one or more filter dialogs still have an empty default message area')

heading = telemetry.split('token-usage-heading', 1)[1].split('</div><div class="body">', 1)[0]
if heading.find('token-model-filter-status') < 0 or heading.find('token-legend-export') < 0 or heading.find('token-model-filter-status') > heading.find('token-legend-export'):
    fail('Token Usage export icon is not to the right of the token scope label')

if "if outcome not in {'created','updated'}:\n        return" not in mailbox:
    fail('Address Book promotion audit still permits noisy non-material outcomes')
if "outcome='created' if created else ('updated' if before_state != after_state else 'unchanged')" not in mailbox:
    fail('Address Book promotion does not distinguish no-op rediscovery')
if 'SCOUTBOX_VERBOSE_ADDRESSBOOK_PROMOTION_AUDIT' in mailbox:
    fail('legacy verbose promotion-audit escape hatch can still flood Audit Trail')
if "AuditLog.objects.filter(action='addressbook_promotion').delete()" not in migration:
    fail('legacy Address Book promotion audit cleanup migration missing')

if "self.client.get(reverse('opportunities'))" not in tests or "self.assertEqual(response.status_code, 200)" not in tests:
    fail('request-level Opportunities regression test missing')
if "self.assertEqual(outcome, 'unchanged')" not in tests:
    fail('Address Book no-op audit regression test missing')
if 'remove_addressbook_promotion_history(apps, None)' not in tests:
    fail('Address Book historical audit cleanup runtime regression test missing')

print('ScoutBox 0.10.77 targeted regressions passed.')
