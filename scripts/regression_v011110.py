from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.110'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.110'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.110'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.110'
assert (root / 'docs/RELEASE_NOTES_0.11.110.md').exists()

tracking = read('portal/services/tracking.py')
assert "raise ValueError('Invalid link, please try a different link.')" in tracking
assert 'Enter an article URL, not the blog/site index itself.' not in tracking

# Preserve the Generate action and prior 0.11.109 modal behavior.
rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')
assert '>Generate</button>' in rules
assert "function closeTrackingAddModal(){closeModal('tracking-add-modal');const url=new URL(window.location.href);window.location.assign(url.pathname+url.search+url.hash)}" in links

mig = read('portal/migrations/0182_v011110_tracking_invalid_link_message.py')
assert "version='0.11.110'" in mig
assert '0181_v011109_tracking_close_alignment' in mig
print('ScoutBox 0.11.110 targeted regression checks passed')
