from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.120'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.120'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.120'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.120'
assert (root / 'docs/RELEASE_NOTES_0.11.120.md').exists()

# Dedup logic must use destination URL identity plus richer vacancy evidence.
dedup = read('portal/services/dedup.py')
ast.parse(dedup)
for marker in (
    'def vacancy_url_key(value: str) -> str:',
    'def requisition_keys(url: str = \'\', text: str = \'\') -> set[str]:',
    'def role_family_similarity(left: str, right: str) -> float:',
    'def content_similarity(left: str, right: str) -> float:',
    'def materially_different_location(left: str, right: str) -> bool:',
    'def active_role_family_duplicate(',
    'def company_concentration_decision(',
):
    assert marker in dedup, marker

# Explicit different requisitions and clearly different locations must prevent a
# same-family merge. Responsibility/content evidence must participate in the decision.
assert 'incoming_req.isdisjoint(old_req)' in dedup
assert 'materially_different_location(incoming_loc,row_loc)' in dedup
assert 'body=content_similarity(description,old_text)' in dedup
assert 'same_req=bool(incoming_req and old_req and not incoming_req.isdisjoint(old_req))' in dedup

# Same company/title alone must not be an unconditional early duplicate anymore.
active_start = dedup.index('def active_duplicate_opportunity(')
active_end = dedup.index('\ndef active_duplicate_lead(', active_start)
active_body = dedup[active_start:active_end]
assert 'same employer + same title alone is no longer sufficient' in active_body.lower()
assert 'if ck and rck == ck and tk and rtk == tk:\n            return row' not in active_body

# Rolling concentration is graded and has the intended 4/8/12 tiers.
assert 'if count<4:' in dedup
assert 'if count<8:' in dedup
assert 'elif count<12:' in dedup
assert "max(threshold+12,90)" in dedup
assert "'materially_distinct':materially_distinct" in dedup
assert "'stronger_fit':stronger_fit" in dedup

discovery = read('portal/services/discovery.py')
ast.parse(discovery)
assert 'active_role_family_duplicate' in discovery
assert 'company_concentration_decision' in discovery
assert 'def _merge_secondary_opportunity_duplicate(' in discovery
assert 'def _store_company_concentration_overflow(' in discovery
assert "existing['alternate_vacancy_urls']" in discovery
assert "existing['cross_source_merges']" in discovery
assert "existing['company_concentration_overflow']" in discovery
assert "stage='cross_source_opportunity_merge'" in discovery
assert "stage='company_concentration_overflow'" in discovery
assert 'is_job_platform_host(old_target) and not is_job_platform_host(target_url)' in discovery

# The rich second-stage checks must occur after location resolution but before create.
loc_pos = discovery.index("role_locations=normalize_location_items(location_resolution.get('locations')")
family_pos = discovery.index('family_dup=active_role_family_duplicate(', loc_pos)
concentration_pos = discovery.index('concentration=company_concentration_decision(', family_pos)
create_pos = discovery.index('opp=Opportunity.objects.create(', concentration_pos)
assert loc_pos < family_pos < concentration_pos < create_pos

# The older title/body-only fallback must not pre-empt requisition/location checks.
assert 'Do not merge on title/body similarity here.' in discovery

mig = read('portal/migrations/0192_v011120_company_concentration_dedup.py')
assert "version='0.11.120'" in mig
assert '0191_v011119_gemini_parallel_reevaluation_retry' in mig
ast.parse(mig)
print('ScoutBox 0.11.120 targeted regression checks passed')
