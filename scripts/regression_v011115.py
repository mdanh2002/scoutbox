from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.115'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.115'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.115'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.115'
assert (root / 'docs/RELEASE_NOTES_0.11.115.md').exists()

src = read('portal/services/discovery.py')
assert 'from .queryplanner import pre_score_hit, grounded_profile_relevance, build_search_profile, _role_alias_fallback' in src
assert "hiring_intents=['hiring','careers','jobs','vacancies']" in src
assert 'def compact_company_query(offset=0, *, domain=' in src
assert "role_variants[(rotation_bucket+offset)%len(role_variants)]" in src
assert "technical_terms[(rotation_bucket*3+offset)%len(technical_terms)]" in src
assert "if not alias or len(alias.split())>4:" in src
assert "if not words or len(words)>3:" in src
assert "parts.append(f'\"{role}\"')" in src
assert "parts.append(f'site:{domain}')" in src
assert "seed_query=compact_company_query(pidx-1)" in src
assert "q=compact_company_query(idx,domain=domain)" in src
assert "seed_query=f'{focus} {location} hiring company careers \"join our team\"'.strip()" not in src
assert "company_intents=['careers','jobs','hiring','\"join our team\"','opportunities','projects','consulting','collaboration']" not in src

# Confirm syntax and that the concise builder remains inside the company-career stage.
module = ast.parse(src)
company_fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == '_company_career_page_records')
nested = [node for node in company_fn.body if isinstance(node, ast.FunctionDef)]
assert any(node.name == 'compact_company_query' for node in nested)

mig = read('portal/migrations/0187_v011115_concise_search_queries.py')
assert "version='0.11.115'" in mig
assert '0186_v011114_statistics_domain_country' in mig
print('ScoutBox 0.11.115 targeted regression checks passed')
