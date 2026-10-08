from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
fresh = (ROOT / 'portal' / 'services' / 'fresh_sources.py').read_text()
tasks = (ROOT / 'portal' / 'tasks.py').read_text()
views = (ROOT / 'portal' / 'views.py').read_text()
opp = (ROOT / 'templates' / 'portal' / 'opportunities.html').read_text()
leads = (ROOT / 'templates' / 'portal' / 'cold_contact.html').read_text()
contacts = (ROOT / 'templates' / 'portal' / 'contacts.html').read_text()
css = (ROOT / 'portal' / 'static' / 'portal' / 'app.css').read_text()

for thread_id in ['49522897','49156683','48747976']:
    assert thread_id in fresh, f'missing known HN thread id {thread_id}'
for surface in ['https://news.ycombinator.com/jobs','https://www.ycombinator.com/jobs','https://www.ycombinator.com/jobs/role/all','https://hnhiring.com/search','https://hnhiring.com/search?locations=remote','https://hnhiring.herokuapp.com/search']:
    assert surface in fresh, f'missing direct hiring surface {surface}'
assert '_hn_candidate_story_ids' in fresh and 'calendar.month_name' in fresh
assert 'author_whoishiring' in fresh and '_community_thread_url' in fresh and '_community_comment_url' in fresh

assert 'MANUAL_FILTER_CLOUD_PARALLELISM = 5' in tasks
assert "def _manual_filter_parallel_enabled" in tasks
assert 'return _parallel_opportunity_filter(job,ids,provider,model,internet_search,notify_email)' in tasks
assert 'return _parallel_hidden_lead_filter(job,ids,provider,model,internet_search,notify_email)' in tasks
assert 'return _parallel_contact_filter(job,ids,provider,model,internet_search,notify_email)' in tasks
assert "in {'openai','gemini','openrouter'}" in tasks

assert '_latest_meaningful_manual_filter' in views
assert 'latest_hidden_lead_filter=_latest_meaningful_manual_filter(hidden_lead_filter_history)' in views
assert 'latest_opportunity_filter=_latest_meaningful_manual_filter(opportunity_filter_history)' in views
assert 'latest_contact_filter=_latest_meaningful_manual_filter(contact_filter_history)' in views

for tpl in [opp, leads, contacts]:
    assert 'read-state-filter-button' in tpl
    assert 'mark-state-action-button' in tpl
assert 'toolbar-select-button' in css and 'toolbar-action-cluster' in css
print('0.11.12 HN/direct-source, toolbar, result-card and cloud-concurrency regression checks passed')
