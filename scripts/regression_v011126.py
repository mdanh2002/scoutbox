from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.126'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.126'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.126'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.126'
assert (root/'docs/RELEASE_NOTES_0.11.126.md').exists()

views=read('portal/views.py')
assert 'def _decorate_manual_filter_item_dates(history, item_kind):' in views
assert "values_list('pk','first_seen_by_portal')" in views
assert "values_list('pk','created_at')" in views
assert "_manual_filter_history_for_view('filter_opportunities',active_opportunity_filter),'opportunity'" in views
assert "_manual_filter_history_for_view('filter_contacts',active_contact_filter),'contact'" in views
assert "_hidden_lead_filter_history_for_view(active_hidden_lead_filter),'lead'" in views

extras=read('portal/templatetags/portal_extras.py')
assert 'def manual_filter_fit_sort_value(row):' in extras

base=read('templates/portal/base.html')
assert 'function exportListTableCsv(tableId,filename)' in base
assert "querySelector('[data-table-filter=\"'+CSS.escape(table.id)+'\"]')" in base

checks=(
    ('templates/portal/opportunities.html','opportunity-filter-result-table-','Opportunity:'),
    ('templates/portal/cold_contact.html','hidden-lead-filter-result-table-','Hidden Lead:'),
    ('templates/portal/contacts.html','contact-filter-result-table-','Address Book contact:'),
)
for rel,prefix,restore_label in checks:
    text=read(rel)
    assert 'Showing {{' not in text
    assert '<th>Item Date</th>' in text
    assert '<th>Confidence</th>' not in text
    assert 'manual-filter-fit-confidence' in text
    assert f'data-table-filter="{prefix}' in text
    assert f'data-list-table data-page-size="50"' in text
    assert f'data-page-size="{prefix}' in text
    assert f'data-pager-count="{prefix}' in text
    assert f'data-pager-page="{prefix}' in text
    assert f'data-pager-nav="{prefix}' in text
    assert 'exportListTableCsv(' in text
    assert restore_label in text

css=read('portal/static/portal/app.css')
for marker in ('.manual-filter-history-list-toolbar','.manual-filter-history-search','.manual-filter-fit-confidence','.manual-filter-history-footer'):
    assert marker in css

mig=read('portal/migrations/0198_v011126_reevaluation_result_listview.py')
assert "version='0.11.126'" in mig
assert "dependencies = [('portal', '0197_v011125_reevaluation_history_restore_fix')]" in mig

print('ScoutBox 0.11.126 targeted regression checks passed')
