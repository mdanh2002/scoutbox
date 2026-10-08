from pathlib import Path
import ast
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from portal.services.location_values import parse_location_items, location_display_text
from portal.services.source_domains import expand_source_domains, direct_endpoint_variants

# Recruiter regions remain first-class locations rather than country expansions.
assert [x['label'] for x in parse_location_items('LATAM',source='fixture')] == ['LATAM']
assert [x['label'] for x in parse_location_items('Asia Pacific',source='fixture')] == ['APAC']
assert [x['label'] for x in parse_location_items('ASEAN',source='fixture')] == ['ASEAN']
assert [x['label'] for x in parse_location_items('Europe, Middle East and Africa',source='fixture')] == ['EMEA']
assert [x['label'] for x in parse_location_items('EU/EEA',source='fixture')] == ['EU/EEA']
assert [x['label'] for x in parse_location_items('Remote from Europe, Ukraine',source='fixture')] == ['Europe','Ukraine']
assert location_display_text('LATAM') == 'LATAM'

# Exercise extract_role_location without importing Django-only module dependencies.
content_path=Path('portal/services/content_quality.py')
content_tree=ast.parse(content_path.read_text(),filename=str(content_path))
extract_node=next(n for n in content_tree.body if isinstance(n,ast.FunctionDef) and n.name=='extract_role_location')
ns={'re':re,'json':json}
exec(compile(ast.Module(body=[extract_node],type_ignores=[]),str(content_path),'exec'),ns)
extract_role_location=ns['extract_role_location']
jobicy_text='''QA Manual Test Engineer\nRemote from\nLATAM\nThis is a remote role, but applicants must be located in Latin America.'''
structured=[{'@type':'Country','name':x} for x in ['Antigua and Barbuda','Argentina','Barbados','Bahamas','Belize']]
assert extract_role_location(jobicy_text,'') in {'LATAM','Latin America'}
assert extract_role_location(jobicy_text,structured) in {'LATAM','Latin America'}
assert extract_role_location('Remote from ANZ',[{'name':'Australia'},{'name':'New Zealand'}]) == 'ANZ'

# Location resolver must consider direct/visible recruiter wording before structured JSON-LD.
location_source=Path('portal/services/location.py').read_text()
resolver=location_source[location_source.index('def resolve_opportunity_location'):location_source.index('\ndef legacy_country_is_untrusted')]
assert resolver.index('direct_hint=') < resolver.index("items=_items_from_hint(structured_hint")
assert resolver.index("source='explicit_page_role_location'") < resolver.index("source='structured_jobposting'")

# Known worldwide domain families work from either the default domain or a variant.
assert 'sg.indeed.com' in expand_source_domains('indeed.com',limit=8)
assert expand_source_domains('https://sg.indeed.com/jobs',limit=3)[0] == 'sg.indeed.com'
assert expand_source_domains('seek.co.nz',limit=3)[:2] == ['seek.co.nz','seek.com.au']
assert 'glassdoor.com' in expand_source_domains('glassdoor.sg',limit=8)
lever=direct_endpoint_variants('lever','https://api.eu.lever.co/v0/postings',limit=2)
assert lever == ['https://api.eu.lever.co/v0/postings','https://api.lever.co/v0/postings'], lever
assert direct_endpoint_variants('jobicy','https://jobicy.com/api/v2/remote-jobs',limit=3) == ['https://jobicy.com/api/v2/remote-jobs']

# Execute the deterministic Focus topic rule in isolation: campaign text must not make
# an unrelated QA job become Embedded Firmware, and payments in the tested product must
# not override the QA function.
focus_path=Path('portal/services/focus.py')
focus_tree=ast.parse(focus_path.read_text(),filename=str(focus_path))
topic_assign=next(n for n in focus_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_TOPIC_RULES' for t in n.targets))
topic_rules=ast.literal_eval(topic_assign.value)
topic_fn=next(n for n in focus_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_topic_rule_candidates')
fns={'re':re,'_TOPIC_RULES':topic_rules}
exec(compile(ast.Module(body=[topic_fn],type_ignores=[]),str(focus_path),'exec'),fns)
qa=fns['_topic_rule_candidates'](
    'QA Manual Test Engineer',
    'Validate web applications and payments workflows. Create test plans, regression testing and actionable defect reports.',
    'Embedded Jobs',
)
labels=[row[0] for row in qa]
assert 'QA & Testing' in labels, labels
assert 'Embedded Firmware' not in labels, labels
assert 'FinTech Engineering' not in labels, labels

# Exercise the canonical age bucket function without importing Django.
fresh_path=Path('portal/services/freshness.py')
fresh_tree=ast.parse(fresh_path.read_text(),filename=str(fresh_path))
age_fn=next(n for n in fresh_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_age_range_label')
age_ns={}
exec(compile(ast.Module(body=[age_fn],type_ignores=[]),str(fresh_path),'exec'),age_ns)
for day in range(0,7): assert age_ns['_age_range_label'](day) == '~ 3 days', day
for day in range(7,14): assert age_ns['_age_range_label'](day) == '~ 1 week', day
fresh_source=fresh_path.read_text()
assert "_parse_public_date(post.get('exact_date'))" in fresh_source
assert fresh_source.index("_parse_public_date(post.get('exact_date'))") < fresh_source.index("age_days=post.get('age_days')")

# Direct-adapter CR-3 implementation is bounded and deduplicated.
direct=Path('portal/services/fresh_sources.py').read_text()
lever_block=direct[direct.index('def _lever('):direct.index('\ndef _ashby(')]
assert "direct_endpoint_variants(" in lever_block
assert "limit=2" in lever_block
assert '_merge_rows_unique(site_rows,batch)' in lever_block
assert '_merge_rows_unique(rows,site_rows)' in lever_block
# Provider IDs, not variant hostnames, are the primary direct-row dedupe key.
direct_tree=ast.parse(direct,filename='portal/services/fresh_sources.py')
dedupe_nodes=[n for n in direct_tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_direct_row_dedupe_key','_merge_rows_unique'}]
dedupe_ns={}
exec(compile(ast.Module(body=dedupe_nodes,type_ignores=[]),'portal/services/fresh_sources.py','exec'),dedupe_ns)
rows=[]
a={'url':'https://jobs.lever.co/acme/abc','_direct_adapter':'lever','_direct_item_id':'123','_ats_board':'acme'}
b={'url':'https://jobs.eu.lever.co/acme/abc','_direct_adapter':'lever','_direct_item_id':'123','_ats_board':'acme'}
dedupe_ns['_merge_rows_unique'](rows,[a,b])
assert len(rows)==1, rows

migration=Path('portal/migrations/0132_v010112_source_fidelity_focus_age.py').read_text()
assert "focus_taxonomy_version='0.10.112'" in migration
assert "country_repair_version=''" in migration
assert '_normalize_post_ages' in migration

opps=Path('templates/portal/opportunities.html').read_text()
assert 'value="lt3d"> ~ 3 days' in opps
print('0.10.112 targeted regressions passed')
