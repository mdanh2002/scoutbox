from pathlib import Path


root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.87'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.87'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.87'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.87'
assert (root/'docs/RELEASE_NOTES_0.11.87.md').exists()

views=read('portal/views.py')
facebook=read('templates/portal/facebook_pages.html')
links=read('templates/portal/links.html')
telemetry=read('templates/portal/telemetry.html')
profile=read('templates/portal/profile.html')
about=read('templates/portal/about.html')
blacklist=read('templates/portal/blacklist.html')
css=read('portal/static/portal/app.css')
migration=read('portal/migrations/0159_v01187_ui_and_telemetry_repairs.py')

assert '@xframe_options_sameorigin' in views
assert '_market_name_for_region_setting' in views and "market.locale" in views and "market.ddg_region" in views
assert "'page_id_asc'" in views and "'evidence_desc'" in views
assert 'data-async-list-search="facebook-pages"' in facebook
assert 'document.querySelectorAll(\'input[name="facebook_page_ids"][form="facebook-pages-bulk"]:checked\')' in facebook
assert 'Discovery Evidence' in facebook and 'Pending page-title validation' not in facebook
assert 'pagination_window' in facebook and 'facebook-title-pending' in facebook
assert "{% icon 'refresh' %}" in links and 'likely_human_clicks' not in links
assert "_resource_chart_rows(sample_rows,qs,start,end,max_points=240)" in views
assert "line('cpu','#45d2e8',100,true)" in telemetry
assert '<h3>Discovery Activity</h3>' in telemetry
assert 'data-max-items="10"' in profile and 'profile-operating-field' in profile
assert '{% if scope.count %}' in blacklist
assert about.count('about-reference-card')>=5
assert '.search-log-total-count{font-weight:400!important}' in css
assert 'market-coverage-copy{height:100%' in css
assert "version='0.11.87'" in migration

print('ScoutBox 0.11.87 regression checks passed')
