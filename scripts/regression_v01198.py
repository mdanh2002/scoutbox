from pathlib import Path
import ast
import re

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.98'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.98'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.98'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.98'
assert (root/'docs/RELEASE_NOTES_0.11.98.md').exists()
assert '0.11.99, 0.11.100, 0.11.101' in read('RELEASE_POLICY.md')

# Dashboard summary cards match the Resource Usage number/label presentation and no
# longer carry decorative icons.
dash=read('templates/portal/dashboard.html')
start=dash.index('<div class="metric-strip span-12 dashboard-metrics-grid">')
end=dash.index('</div>', start)
# the metric strip contains no metric-symbol markup at all; check the full block by
# slicing through the next major card rather than the first nested closing tag.
end=dash.index('<div class="card span-12"', start)
metric_block=dash[start:end]
assert 'dashboard-metric' in metric_block
assert 'metric-symbol' not in metric_block
for label in ('New opportunities','New Hidden Leads','New Contacts','Facebook Pages','Applications &amp; Outreaches','Replies today','Errors · 24h'):
    assert label in metric_block
css=read('portal/static/portal/app.css')
assert '.dashboard-metrics-grid .dashboard-metric' in css
assert 'grid-template-rows:minmax(28px,auto) minmax(20px,auto)!important' in css
assert 'justify-content:center!important' in css

# Recycle Bin uses neutral toolbox buttons and compact type/date columns.
recycle=read('templates/portal/recycle_bin.html')
actions=recycle[recycle.index('<div class="recycle-toolbar-actions">'):recycle.index('</div>',recycle.index('<div class="recycle-toolbar-actions">'))]
assert 'toolbar-icon-action recycle-action-icon' in actions
for colored in ('btn small warn recycle-action-icon','btn small success recycle-action-icon','btn small danger recycle-action-icon'):
    assert colored not in actions
assert 'recycle-title-col' in recycle and 'recycle-info-col' in recycle
assert '#recycle-bin-table col.recycle-type-col{width:88px!important}' in css
assert '#recycle-bin-table col.recycle-date-col{width:148px!important}' in css
assert '.recycle-toolbar-actions .recycle-action-icon{' in css
assert 'background:rgba(15,47,68,.92)!important' in css

# Tracking Links uses the broader relationship heading requested by the user.
links=read('templates/portal/links.html')
assert '>Application / Outreach</th>' in links
assert '>Application</th>' not in links

# Outgoing provider queries drop low-value standalone prepositions, while exact quoted
# phrases, site scopes and technical literals are preserved.
qp=read('portal/services/queryplanner.py')
assert "_SEARCH_FILLER_PREPOSITIONS = {" in qp
assert "'in','at','near','around','within','for','with','from','to','of','by','on','into','across'" in qp
qt=ast.parse(qp)
keep_assign={'_GENERIC_FULL_STACK_RE','_EXTERNAL_EXCLUSION_RE','_SEARCH_FILLER_PREPOSITIONS'}
keep_funcs={'strip_external_exclusions','_normalize_site_constraint','_append_site_constraint_once','_is_search_filler_word','sanitize_search_engine_query','sanitize_local_search_engine_query'}
body=[]
for node in qt.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in keep_assign for t in node.targets):
        body.append(node)
    elif isinstance(node,ast.FunctionDef) and node.name in keep_funcs:
        body.append(node)
ns={'re':re}
exec(compile(ast.Module(body=body,type_ignores=[]),'query_sanitizers','exec'),ns)
q='site:greenhouse.com embedded C C++ engineer "embedded systems" in Brno'
clean=ns['sanitize_local_search_engine_query'](q)
assert clean=='site:greenhouse.com embedded C C++ engineer "embedded systems" Brno', clean
q2='site:example.com "software engineer in Melbourne" C++ with BACnet in Melbourne'
clean2=ns['sanitize_local_search_engine_query'](q2)
assert 'software engineer in Melbourne' in clean2
assert ' C++ ' in (' '+clean2+' ')
assert ' BACnet ' in (' '+clean2+' ')
assert ' with ' not in (' '+clean2+' ') and (' '+clean2+' ').count(' in ')==1  # retained from the quoted phrase

# The ambiguous Retro Computing focus is retired. Existing derived assignments are
# blanked for normal regrouping and future AI labels are narrowed to Vintage Systems.
focus=read('portal/services/focus.py')
for rewrite in ("'retro computing': 'Vintage Systems'","'retro systems': 'Vintage Systems'","'vintage computing': 'Vintage Systems'"):
    assert rewrite in focus
assert 'Do not use the vague label Retro Computing or any label containing Retro.' in focus
assert "'vintage': ('retro', 'classic', 'obsolete', 'legacy')" in focus
m170=read('portal/migrations/0170_v01198_focus_search_ui.py')
assert "('portal', '0169_v01197_tracking_ui_translation_cleanup')" in m170
assert "'Retro Computing'" in m170 and "'Retro / Legacy Systems'" in m170
assert "model.objects.filter(focus__iexact=label).update(focus='')" in m170
assert "action='version_upgraded', version='0.11.98'" in m170
assert 'detail' not in m170

print('ScoutBox 0.11.98 targeted regression checks passed')
