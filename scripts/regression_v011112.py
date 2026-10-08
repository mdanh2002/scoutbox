from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.112'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.112'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.112'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.112'
assert (root / 'docs/RELEASE_NOTES_0.11.112.md').exists()

stats = read('templates/portal/stats.html')
telemetry = read('templates/portal/telemetry.html')
base = read('templates/portal/base.html')

# Preset period segments must not drive the filter-button highlight.
expected = "class=\"icon-btn{% if date_from or date_to %} active{% endif %}\""
assert expected in stats
assert expected in telemetry
assert "class=\"icon-btn{% if period != 'all' %} active{% endif %}\"" not in stats
assert "class=\"icon-btn{% if period != 'all' %} active{% endif %}\"" not in telemetry
assert "aria-pressed=\"{% if date_from or date_to %}true{% else %}false{% endif %}\"" in stats
assert "aria-pressed=\"{% if date_from or date_to %}true{% else %}false{% endif %}\"" in telemetry

# Live state likewise follows only the From/To inputs.
assert "const active=Boolean((from?.value||'').trim()||(to?.value||'').trim())" in base
assert "const active=Boolean(initial.from||initial.to)" in base
assert "const active=(period?.value||'all')!=='all'" not in base

mig = read('portal/migrations/0184_v011112_date_filter_icon_state.py')
assert "version='0.11.112'" in mig
assert '0183_v011111_resource_hover_tracking_search' in mig
print('ScoutBox 0.11.112 targeted regression checks passed')
