from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.113'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.113'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.113'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.113'
assert (root / 'docs/RELEASE_NOTES_0.11.113.md').exists()

views = read('portal/views.py')
base = read('templates/portal/base.html')
partial = read('templates/portal/_date_filter_fields.html')
stats = read('templates/portal/stats.html')
telemetry = read('templates/portal/telemetry.html')
css = read('portal/static/portal/app.css')

# Server-side validation is shared by Statistics, Resource Usage, and list/history views.
assert 'def _validated_custom_date_bounds(raw_from, raw_to):' in views
assert 'max_date=timezone.localdate()+timedelta(days=1)' in views
assert 'start.date()>max_date or parsed_to.date()>max_date or start>=parsed_to' in views
assert views.count("_validated_custom_date_bounds(request.GET.get('from',''),request.GET.get('to',''))") == 3
assert views.count("if not valid: period='all'") >= 3

# Browser validation requires a complete, sensible pair and caps the native picker at tomorrow.
assert "if(!state.complete){state.reason='Enter both From and To dates'" in base
assert "if(fromDate.key>=toDate.key){state.reason='From must be earlier than To'" in base
assert "state.reason='Dates cannot be later than tomorrow'" in base
assert 'picker.max=maxDate().iso' in base
assert 'apply.disabled=!state.valid' in base
assert "form.addEventListener('submit'" in base
assert "input.classList.toggle('date-range-invalid'" in base

# Buttons are initially disabled server-side if either endpoint is absent.
initial_disabled = '{% if not date_from or not date_to %} disabled aria-disabled="true"{% endif %}'
assert initial_disabled in partial
assert initial_disabled in stats
assert initial_disabled in telemetry
assert '.date-input-wrap input.date-range-invalid' in css
assert '.resource-date-form>.icon-btn:disabled' in css

# Every shared list-view date control continues to use the validated partial.
for template in ('audit.html','email_history.html','gpt_log.html','recycle_bin.html','search_log.html'):
    assert "{% include 'portal/_date_filter_fields.html' %}" in read('templates/portal/' + template)

mig = read('portal/migrations/0185_v011113_date_range_validation.py')
assert "version='0.11.113'" in mig
assert '0184_v011112_date_filter_icon_state' in mig
print('ScoutBox 0.11.113 targeted regression checks passed')
