from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.117'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.117'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.117'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.117'
assert (root / 'docs/RELEASE_NOTES_0.11.117.md').exists()

discovery = read('portal/services/discovery.py')
assert 'configured_provider_cap=max(1,int(cfg.queries_per_provider or 1))' in discovery
assert 'provider_query_allowance(provider,configured_provider_cap)' in discovery
assert "SCOUTBOX_PROVIDER_QUERY_HARD_CAP" not in discovery
assert 'configured_provider_cap=max(1,min(int(cfg.queries_per_provider or 1),12))' not in discovery
# Preserve non-hard-cap safety controls from 0.11.116.
assert "SCOUTBOX_LOCAL_SEARCH_STAGE_MAX_SECONDS" in discovery
assert "SCOUTBOX_SEARCH_PROVIDER_STAGE_MAX_SECONDS" in discovery
assert 'provider_error_limit=_search_provider_error_limit()' in discovery

search = read('portal/services/search.py')
assert 'def provider_query_allowance(source, requested):' in search
assert 'recent=provider_recent_health(source,days=2)' in search
assert 'recent_requests>=24 and recent_unique==0 and recent_active==0' in search

ast.parse(discovery)
ast.parse(search)

mig = read('portal/migrations/0189_v011117_remove_provider_query_hard_cap.py')
assert "version='0.11.117'" in mig
assert '0188_v011116_discovery_quality_export' in mig
ast.parse(mig)
print('ScoutBox 0.11.117 targeted regression checks passed')
