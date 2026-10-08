from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.123'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.123'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.123'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.123'
assert (root/'docs/RELEASE_NOTES_0.11.123.md').exists()

views=read('portal/views.py')
assert "internet_search=bool(row['is_cloud'])" in views
assert "internet_search=bool(request.POST.get('internet_search')) and bool(row['is_cloud'])" not in views

opp=read('templates/portal/opportunities.html')
lead=read('templates/portal/cold_contact.html')
contacts=read('templates/portal/contacts.html')
css=read('portal/static/portal/app.css')
for text in (opp,lead,contacts):
    assert 'Enable Internet Search' not in text
assert 'Internet Search verifies the contact/company and refreshes company data when public evidence is available.' not in contacts
assert 'Fit is recalculated. Clearly irrelevant contacts may be recycled. ~1 AI request/item.' not in contacts
for text,prefix in ((opp,'opportunity'),(lead,'hidden-lead')):
    assert 'Cloud re-evaluation instructions' in text
    assert 'cols="92"' in text
    assert f'id="{prefix}-filter-cloud-prompt"' in text
    assert "if(cloud)body.set('internet_search','1')" in text
assert '.manual-filter-cloud-modal-card{width:min(820px,calc(100vw - 32px))}' in css
assert '.manual-filter-cloud-prompt-row textarea{display:block;width:100%' in css
assert "if(cloud)body.set('internet_search','1')" in contacts

# Existing .122 cloud policy behavior stays intact.
flt=read('portal/services/opportunity_filter.py')
assert 'exceptional_interest_confidence >= 95' in flt
assert "buyer_direction == 'may_buy_from_candidate'" in flt
assert "decision = 'convert_to_hidden_lead'" in flt
assert "decision = 'convert_to_opportunity'" in flt

tasks=read('portal/tasks.py')
# Recycling alone is protected; high-confidence conversion is still allowed.
assert "if decision=='recycle' and protected:" in tasks
assert "if decision in {'recycle','convert_to_hidden_lead'} and protected:" not in tasks
assert "if decision in {'recycle','convert_to_opportunity'} and protected:" not in tasks
assert tasks.count("protected=_hidden_lead_has_outreach(lead)") >= 2
assert "'converted_id':(converted.pk if decision=='convert_to_hidden_lead' else None)" in tasks
assert "'converted_id':(converted.pk if decision=='convert_to_opportunity' else None)" in tasks
# Address Book has no cross-list conversion path.
contact_parallel=tasks[tasks.index('def _parallel_contact_filter'):tasks.index('@shared_task(bind=True)\ndef opportunity_filter_job')]
assert 'convert_to_hidden_lead' not in contact_parallel
assert 'convert_to_opportunity' not in contact_parallel

mig=read('portal/migrations/0195_v011123_reevaluation_dialog_cleanup.py')
assert "version='0.11.123'" in mig
assert "dependencies = [('portal', '0194_v011122_cloud_reevaluation_prompts')]" in mig

print('ScoutBox 0.11.123 targeted regression checks passed')
