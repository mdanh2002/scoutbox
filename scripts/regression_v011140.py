from pathlib import Path
import ast, re, urllib.parse

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.140'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.140'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.140'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.140'
assert (root/'docs/RELEASE_NOTES_0.11.140.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 19:44:00'" in read('opportunity_portal/settings.py')

search=read('portal/services/search.py')
assert 'ScoutBox/0.11.140' in search
assert '_FACEBOOK_POST_TITLE_RE' in search
assert "'NA':'North America'" in search
assert "_facebook_title_matches_page_id(seeded,page_id)" in search
assert "identity=facebook_page_identity_title(url,clean_seed_title,evidence_text,page_id,direct=False).get('title','')" in search
assert "identity=facebook_page_identity_title(page_url,direct_title or title,evidence,candidate,direct=False)" in search

# Execute only the dependency-light Facebook identity helpers from search.py.
tree=ast.parse(search)
keep_assign={'_FACEBOOK_WATCH_NOISE','_FACEBOOK_SYSTEM_SLUGS','_FACEBOOK_TITLE_SUFFIX_RE','_FACEBOOK_POST_TITLE_RE','_FACEBOOK_REGION_SUFFIXES'}
keep_funcs={'_clean_facebook_page_title','_facebook_identity_key','_facebook_page_id_display','_facebook_title_looks_like_post','_facebook_title_matches_page_id','_facebook_identity_from_evidence','facebook_page_identity_title'}
nodes=[]
for node in tree.body:
    if isinstance(node,(ast.Assign,ast.AnnAssign)):
        names=[]
        if isinstance(node,ast.Assign):
            for t in node.targets:
                if isinstance(t,ast.Name): names.append(t.id)
        elif isinstance(node.target,ast.Name): names.append(node.target.id)
        if any(n in keep_assign for n in names): nodes.append(node)
    elif isinstance(node,ast.FunctionDef) and node.name in keep_funcs:
        nodes.append(node)
mod=ast.Module(body=nodes,type_ignores=[]); ast.fix_missing_locations(mod)
ns={'re':re,'urllib':urllib}
exec(compile(mod,'facebook_identity_helpers','exec'),ns,ns)

page_id='BoschBuildingTechnologiesNA'
expected='Bosch Building Technologies North America'
assert ns['_facebook_page_id_display'](page_id)==expected
post='Are you looking for a career change? Bosch Building Technologies is the place to be'
assert ns['_facebook_title_looks_like_post'](post)
assert not ns['_facebook_title_matches_page_id'](post,page_id)
resolved=ns['facebook_page_identity_title'](
    'https://www.facebook.com/'+page_id,
    post,
    'Join our team! We are hiring for our ICT and KC locations.',
    page_id,
    direct=False,
)
assert resolved['title']==expected, resolved
assert resolved['source']=='page_id', resolved
resolved2=ns['facebook_page_identity_title'](
    'https://www.facebook.com/'+page_id,
    expected,
    '',page_id,direct=False,
)
assert resolved2['title']==expected and resolved2['source']=='stored', resolved2

migration=read('portal/migrations/0212_v011140_facebook_page_identity_titles.py')
assert "dependencies=[('portal','0211_v011139_company_identity_integrity')]" in migration
assert "'NA':'North America'" in migration
assert "version='0.11.140'" in migration
assert 'facebook_page_titles_repaired' in migration
assert "row.page_title=replacement" in migration
assert "row.save(update_fields=['page_title','validation_reason','updated_at'])" in migration

# Ensure evidence presentation remains independent of Page title.
facebook=read('templates/portal/facebook_pages.html')
assert '{{p.page_title}}' in facebook
assert '{{p.evidence_text|normalize_evidence_ellipsis}}' in facebook
assert 'facebook-evidence-cell' in facebook

# Prior 0.11.139 integrity/detail behavior and SearchAPI configuration remain present.
assert (root/'portal/migrations/0211_v011139_company_identity_integrity.py').exists()
assert "SEARCHAPI_ACCOUNT_ENDPOINT='https://www.searchapi.io/api/v1/me'" in search
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in read('portal/tasks.py')

print('ScoutBox 0.11.140 targeted regression checks passed')
