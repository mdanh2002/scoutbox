from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.124'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.124'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.124'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.124'
assert (root/'docs/RELEASE_NOTES_0.11.124.md').exists()

extras=read('portal/templatetags/portal_extras.py')
assert 'def manual_filter_display_count' in extras
assert "return 'Failed'" in extras
assert "return 'Recycle'" in extras
assert "return 'Keep'" in extras
assert "return 'red' if label=='Failed' else ('amber' if label=='Recycle' else 'green')" in extras
assert "manual_filter_count(data,'converted_to_hidden_lead')" in extras
assert "manual_filter_count(data,'converted_to_opportunity')" in extras

base=read('templates/portal/base.html')
assert 'function manualFilterDisplayCounts(result)' in base
assert "const recycled=num('recycled')||num('recycle'),failed=num('failed')+num('timed_out')" in base
assert "async function restoreInlineItem" in base

opp=read('templates/portal/opportunities.html')
lead=read('templates/portal/cold_contact.html')
contacts=read('templates/portal/contacts.html')
for text in (opp,lead,contacts):
    assert 'manual_filter_decision_class' in text
    assert 'manual_filter_decision_label' in text
    assert 'need review' not in text.lower()
    assert 'manual-filter-count-kept' in text
    assert 'manual-filter-count-recycled' in text
    assert 'manual-filter-count-failed' in text
    assert "manual_filter_display_count:'kept'" in text
    assert "manual_filter_display_count:'failed'" in text
assert "restoreInlineItem('opportunity'" in opp
assert "restoreInlineItem('lead'" in lead
assert "restoreInlineItem('contact'" in contacts
assert "item.decision == 'recycled' and item.id" in opp
assert "item.decision == 'recycled' and item.id" in lead
assert "item.decision == 'recycled' and item.id" in contacts
assert 'Converted to Hidden Lead' not in opp
assert 'Converted to Opportunity' not in lead

css=read('portal/static/portal/app.css')
assert '.manual-filter-count-kept{color:#72e49b' in css
assert '.manual-filter-count-recycled{color:#ffd072' in css
assert '.manual-filter-count-failed{color:#ff9da4' in css
assert '.manual-filter-restore-line{' in css

# Evaluation mechanics remain unchanged; this release only changes result presentation/recovery UI.
tasks=read('portal/tasks.py')
assert "elif decision=='convert_to_hidden_lead':" in tasks
assert "elif decision=='convert_to_opportunity':" in tasks
assert "if decision=='recycle' and protected:" in tasks

mig=read('portal/migrations/0196_v011124_reevaluation_result_clarity.py')
assert "version='0.11.124'" in mig
assert "dependencies = [('portal', '0195_v011123_reevaluation_dialog_cleanup')]" in mig

print('ScoutBox 0.11.124 targeted regression checks passed')
