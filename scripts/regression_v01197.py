from pathlib import Path
import ast
import itertools
import re

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.97'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.97'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.97'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.97'
assert (root/'docs/RELEASE_NOTES_0.11.97.md').exists()
assert '0.11.98, 0.11.99, 0.11.100' in read('RELEASE_POLICY.md')

# Migration is safe against the real AuditLog schema, clears old free-form suffix
# reserves and removes existing trailing full stops from blacklist reasons.
m169=read('portal/migrations/0169_v01197_tracking_ui_translation_cleanup.py')
assert "('portal', '0168_v01196_tracking_stats_ui')" in m169
assert "action='version_upgraded', version='0.11.97'" in m169
assert "TrackingSuffixReserve.objects.all().update(suffixes=[], cursor=0)" in m169
assert ".rstrip().rstrip('.').rstrip()" in m169
assert 'detail' not in m169

# Tracking links preserve the user/native short stem and append only one/two
# letters-only article words capped at 15 characters. No canonical title/slug dump.
tracking=read('portal/services/tracking.py')
for required in (
    "tracking_stem=slug_word(entered_slug)",
    "'tracking_path':'/'+tracking_stem",
    "base_path=info['tracking_path']",
    "rule.base_path != info['tracking_path']",
    "path=base+suffix",
):
    assert required in tracking
assert 'requests.get' not in tracking[tracking.index('def allocate('):tracking.index('def allocate_for_url(')]
assert "return re.sub('[^a-z]'" in tracking

# Execute only the pure suffix helpers to validate the length/character contract.
tree=ast.parse(tracking)
selected=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STOPWORDS' for t in node.targets):
        selected.append(node)
    elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in {'suffix_word','_candidates'}:
        selected.append(node)
ns={'re':re,'itertools':itertools}
exec(compile(ast.Module(body=selected,type_ignores=[]),'tracking_helpers','exec'),ns)
assert ns['suffix_word']('XT')=='xt'
assert ns['suffix_word']('CH375 / USB adapter')=='chusbadapter'
vals=list(ns['_candidates'](['xt','emulator','hardware']))
assert vals[:3]==['xt','emulator','hardware']
assert all(v.isalpha() and 2<=len(v)<=15 for v in vals)
assert any(v=='xtemulator' for v in vals)

# Tracking editor desktop rows are compact single-line groups.
links=read('templates/portal/link_rules.html')
for cls in ('tracking-blog-base-line','tracking-blog-base-input','tracking-article-line','tracking-article-prefix','tracking-article-input','tracking-docx-file'):
    assert cls in links
css=read('portal/static/portal/app.css')
assert '.tracking-editor-line{display:flex!important' in css
assert 'flex-wrap:nowrap!important' in css
assert '.tracking-blog-base-input{flex:0 1 560px!important' in css
assert '.tracking-docx-inline .tracking-docx-file{flex:0 1 470px!important' in css
assert '.tracking-article-input{flex:0 1 260px!important' in css

# Acquisition Path spacing and dashboard cards.
stats=read('templates/portal/stats.html')
assert 'stats-acquisition-card' in stats and '.stats-acquisition-card{margin-top:11px!important}' in css
dash=read('templates/portal/dashboard.html')
assert 'New Contacts' in dash and 'stats.new_contacts' in dash and '?read=new' in dash
assert "'new_contacts'" in dash
views=read('portal/views.py')
stat_fn=views[views.index('def _dashboard_stats('):views.index('def _capture_resource_sample(')]
assert "'new_contacts':Contact.objects.filter(deleted_at__isnull=True,is_read=False)" in stat_fn
assert '.metric-strip .metric>div{display:grid!important;grid-template-rows:31px 24px!important' in css

# Worldwide is the concise market label; remote wording stays a query concept only.
markets=read('portal/services/discovery_markets.py')
assert "Market('worldwide','Worldwide','','en-US','wt-wt','remote worldwide'" in markets
assert "Market('worldwide','Worldwide Remote'" not in markets

# Translation protection must keep search operators, domains and technical literals
# outside the natural-language translation payload.
discovery=read('portal/services/discovery.py')
for token in ('_protect_query_translation_tokens','_restore_query_translation_tokens','_TRANSLATION_OPERATOR_RE','_TRANSLATION_DOMAIN_RE','_TRANSLATION_TECH_RE','_TRANSLATION_KNOWN_TECH_RE'):
    assert token in discovery
assert 'copy every one exactly and do not translate, move, split or remove it' in discovery
# Execute only the pure masking helpers/constants.
dtree=ast.parse(discovery); body=[]
keep_assign={'_TRANSLATION_OPERATOR_RE','_TRANSLATION_DOMAIN_RE','_TRANSLATION_TECH_RE','_TRANSLATION_KNOWN_TECH_RE'}
for node in dtree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in keep_assign for t in node.targets): body.append(node)
    elif isinstance(node,ast.FunctionDef) and node.name in {'_protect_query_translation_tokens','_restore_query_translation_tokens'}: body.append(node)
dns={'re':re}; exec(compile(ast.Module(body=body,type_ignores=[]),'translation_helpers','exec'),dns)
original='site:jobs.example.com C++ Bacnet modbus Linux software engineer opening'
masked,mapping=dns['_protect_query_translation_tokens'](original,['C++','BACnet','Modbus','software engineer'])
assert 'site:jobs.example.com' not in masked and 'C++' not in masked and 'Bacnet' not in masked and 'modbus' not in masked and 'Linux' not in masked
assert 'software engineer' in masked  # natural-language multiword role remains translatable
restored=dns['_restore_query_translation_tokens'](masked,mapping)
assert restored==original

# Recycle Bin info never paints into the next column.
recycle=read('templates/portal/recycle_bin.html')
assert 'class="recycle-item-info" title="{{row.item_info}}"' in recycle
assert 'class="recycle-item-info-text"' in recycle
assert 'td.recycle-item-info{display:table-cell!important' in css
assert '#recycle-bin-table .recycle-item-info-text{display:block!important' in css
assert 'text-overflow:ellipsis!important' in css

# Blacklist reasons no longer gain/retain a final full stop, for every reason.
blacklist=read('portal/services/blacklist.py')
clean_tail=blacklist[blacklist.index('def clean_blacklist_reason'):blacklist.index('def normalize_pattern')]
assert "return text.rstrip().rstrip('.').rstrip()" in clean_tail
assert "text+='.'" not in clean_tail
assert 'DEFAULT_BLACKLIST=[(domain,label,clean_blacklist_reason(reason),scope)' in blacklist
assert "or 'Manually blacklisted'" in views

# AI Requests: repair is output-list-only, only when the source looks JSON, and the
# detailed popup continues to use the original output_text.
preview=views[views.index('def _list_payload_preview'):views.index('legacy_empty_output=',views.index('def _list_payload_preview'))]
assert "repair_truncated_json_string=False" in preview
assert "clean[:1] in ('{','[')" in preview
assert "preview+='\"'" in preview
assert "_list_payload_preview(row.input_text)" in views
assert "_list_payload_preview(row.output_text,repair_truncated_json_string=True)" in views
gpt=read('templates/portal/gpt_log.html')
assert "gptPayload.output=d.error?'':(d.output_text||'')" in gpt

print('ScoutBox 0.11.97 targeted regression checks passed')
