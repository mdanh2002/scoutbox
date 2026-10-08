from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.125'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.125'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.125'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.125'
assert (root/'docs/RELEASE_NOTES_0.11.125.md').exists()

extras=read('portal/templatetags/portal_extras.py')
assert 'def manual_filter_is_recycled' in extras
assert "return manual_filter_decision_label(row) == 'Recycle'" in extras
assert "'recycle'" in extras and "'rejected'" in extras
assert "return 'Recycle'" in extras
assert "return 'red' if label=='Failed' else ('amber' if label=='Recycle' else 'green')" in extras

views=read('portal/views.py')
assert "def _manual_filter_history_label(history, subject='Re-evaluation')" in views
assert "return f'Showing {count} {subject} re-evaluation result{suffix}'" in views
assert "_manual_filter_history_label(opportunity_filter_history,'Opportunity')" in views
assert "_manual_filter_history_label(hidden_lead_filter_history,'Hidden Lead')" in views
assert "_manual_filter_history_label(contact_filter_history,'Address Book')" in views

opp=read('templates/portal/opportunities.html')
lead=read('templates/portal/cold_contact.html')
contacts=read('templates/portal/contacts.html')
for text in (opp,lead,contacts):
    assert 'manual_filter_is_recycled' in text
    assert "item.decision == 'recycled' and item.id" not in text
    assert 'manual-filter-count-checked' not in text
    assert '>checked</span>' not in text
assert "item.id and not item|manual_filter_is_recycled" in opp
assert "item.id and not item|manual_filter_is_recycled" in lead
assert "restoreInlineItem('opportunity'" in opp
assert "restoreInlineItem('lead'" in lead
assert "restoreInlineItem('contact'" in contacts

# Address Book does not have an active detail-link route in re-evaluation history,
# but normalized recycle decisions must still expose Restore.
assert "item|manual_filter_is_recycled and item.id" in contacts

# Existing result colors and evaluation mechanics remain unchanged.
css=read('portal/static/portal/app.css')
assert '.manual-filter-count-kept{color:#72e49b' in css
assert '.manual-filter-count-recycled{color:#ffd072' in css
assert '.manual-filter-count-failed{color:#ff9da4' in css

tasks=read('portal/tasks.py')
assert "elif decision=='convert_to_hidden_lead':" in tasks
assert "elif decision=='convert_to_opportunity':" in tasks
assert "if decision=='recycle' and protected:" in tasks

mig=read('portal/migrations/0197_v011125_reevaluation_history_restore_fix.py')
assert "version='0.11.125'" in mig
assert "dependencies = [('portal', '0196_v011124_reevaluation_result_clarity')]" in mig

print('ScoutBox 0.11.125 targeted regression checks passed')
