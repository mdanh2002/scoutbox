from pathlib import Path


root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.83"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.83"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.83"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.83"
assert (root / "docs/RELEASE_NOTES_0.11.83.md").exists()

telemetry = read("templates/portal/telemetry.html")
settings = read("templates/portal/settings.html")
search_log = read("templates/portal/search_log.html")
about = read("templates/portal/about.html")
extras = read("portal/templatetags/portal_extras.py")
css = read("portal/static/portal/app.css")

assert 'class="card full discovery-performance-card"' in telemetry
assert 'class="card full market-coverage-card"' in telemetry
assert "marketCoverageCard.classList.remove('card','full')" not in telemetry
assert "title.textContent='Discovery Performance Details'" in telemetry
assert "marketCoverageCard.insertAdjacentElement('afterend',tableCard)" in telemetry
assert "(row.label||'Unknown')+(row.flag?' '+row.flag:'')" in telemetry
assert ".discovery-performance-copy .help{position:static!important;background:transparent!important" in css

assert 'data-diagnostic-export-label' in settings
assert 'class="diagnostic-export-spinner"' in settings
assert "label.textContent=busy?'Preparing…':'Export Diagnostic Data'" in settings
assert "open.title=job.message" in settings
assert "open.textContent=job.message" not in settings
assert ".diagnostic-export-spinner" in css

assert "function mountFooterDate()" in search_log
assert "data-search-log-footer-date-mounted" in search_log
assert "scoutbox:list-updated" in search_log
assert ".search-log-card .history-list-footer{grid-template-columns:auto minmax(390px,1fr) auto!important" in css
assert ".search-log-provider-cell .search-log-provider-name" in css
assert "overflow-wrap:anywhere!important" in css

assert "'external_statistics':'<svg" in extras
assert "{% icon 'external_statistics' %}</span><span>External Statistics" in about
assert "{% icon 'source_direct' %}</span><span>External Statistics" not in about
icon = extras.split("'external_statistics':'", 1)[1].split("'", 1)[0]
assert "arrow" not in icon.casefold()

print("ScoutBox 0.11.83 regression checks passed")
