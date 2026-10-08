from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.121'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.121'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.121'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.121'
assert (root/'docs/RELEASE_NOTES_0.11.121.md').exists()

f=read('portal/services/opportunity_filter.py')
assert "decision = 'convert_to_hidden_lead'" in f
assert "decision = 'convert_to_opportunity'" in f
assert "conversion_confidence >= 90" in f
assert "conversion_confidence >= 92" in f
assert "conversion_exact_vacancy" in f
assert "convert_to_hidden_lead and purpose in {'company_hiring_signal','company_outreach_target'}" in f
assert "convert_to_opportunity and conversion_exact_vacancy and purpose in OPPORTUNITY_PURPOSES" in f
assert "conversion_url.startswith(('http://', 'https://'))" in f

jobs=read('portal/tasks.py')
assert 'def _manual_convert_opportunity_to_hidden_lead' in jobs
assert 'def _manual_convert_hidden_lead_to_opportunity' in jobs
assert "decision in {'recycle','convert_to_hidden_lead'} and protected" in jobs
assert "decision in {'recycle','convert_to_opportunity'} and protected" in jobs
assert "action='manual_cross_list_conversion'" in jobs
assert "Converted to Hidden Leads" in jobs and "Converted to Opportunities" in jobs
assert "target=str(review.get('conversion_url') or '').strip()[:1000]" in jobs
assert "if stats.get('converted_to_hidden_lead'):" in jobs
assert "if stats.get('converted_to_opportunity'):" in jobs
contact=jobs[jobs.index('def _parallel_contact_filter'):jobs.index('@shared_task(bind=True)\ndef opportunity_filter_job')]
assert "convert_to_hidden_lead" not in contact and "convert_to_opportunity" not in contact

cold=read('templates/portal/cold_contact.html')
assert 'Fit is recalculated. Irrelevant leads may be recycled; existing outreach is kept. ~1 AI request/item.' not in cold
assert 'Converted to Opportunity' in cold
opp=read('templates/portal/opportunities.html')
assert 'Converted to Hidden Lead' in opp

black=read('templates/portal/blacklist.html')
assert 'blacklist-field-stack' in black
assert 'Optional. Leave empty for an exact company-name-only rule.' in black
assert 'Minimum {{label_min_chars}} characters when Domain is empty.' in black
assert 'Not a useful discovery source' not in black

mig=read('portal/migrations/0193_v011121_cross_list_reevaluation.py')
assert "version='0.11.121'" in mig
print('ScoutBox 0.11.121 targeted regression checks passed')
