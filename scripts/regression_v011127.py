from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.127'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.127'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.127'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.127'
assert (root/'docs/RELEASE_NOTES_0.11.127.md').exists()

views=read('portal/views.py')
assert 'def re_evaluation_results_export(request, kind, pk):' in views
assert "'opportunity':('filter_opportunities','opportunity','Opportunity','opportunity-reevaluation')" in views
assert "'hidden-lead':('filter_hidden_leads','lead','Hidden Lead','hidden-lead-reevaluation')" in views
assert "'address-book':('filter_contacts','contact','Address Book contact','address-book-reevaluation')" in views
assert "['Entry','Item Date','Decision','Fit','Reason']" in views
assert 'manual_filter_meaningful_items(job.result' in views
assert "return _xlsx(f'{filename_prefix}-{job.pk}.xlsx'" in views

urls=read('portal/urls.py')
assert "path('re-evaluation/results/<str:kind>/<int:pk>/export/'" in urls

checks=(
    ('templates/portal/opportunities.html',"'opportunity'",'Opportunity'),
    ('templates/portal/cold_contact.html',"'hidden-lead'",'Hidden Lead'),
    ('templates/portal/contacts.html',"'address-book'",'Address Book'),
)
for rel,kind,label in checks:
    text=read(rel)
    assert '<th>Refreshed</th>' not in text
    assert '<th>Entry</th><th>Item Date</th><th>Decision</th><th>Fit</th><th>Reason</th>' in text
    assert "re_evaluation_results_export" in text
    assert kind in text
    assert '.csv' not in text
    assert 'Export all '+label+' re-evaluation results as XLSX' in text
    assert 'data-page-size="50"' in text

css=read('portal/static/portal/app.css')
assert '.manual-filter-history-search{width:25%;min-width:180px;max-width:300px}' in css
assert '.manual-filter-history-table table[data-list-table]{width:100%;min-width:0;table-layout:fixed}' in css
assert 'th:nth-child(5),.manual-filter-history-table td:nth-child(5){width:46%;overflow-wrap:anywhere}' in css

mig=read('portal/migrations/0199_v011127_reevaluation_xlsx_layout.py')
assert "version='0.11.127'" in mig
assert "dependencies = [('portal', '0198_v011126_reevaluation_result_listview')]" in mig

print('ScoutBox 0.11.127 targeted regression checks passed')
