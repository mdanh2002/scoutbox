from pathlib import Path


root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.81"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.81"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.81"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.81"
assert (root / "docs/RELEASE_NOTES_0.11.81.md").exists()

views = read("portal/views.py")
search_log = read("templates/portal/search_log.html")
telemetry = read("templates/portal/telemetry.html")
base = read("templates/portal/base.html")
about = read("templates/portal/about.html")
css = read("portal/static/portal/app.css")

search_view = views[views.index("def search_log_view("):views.index("\ndef gpt_log_view(", views.index("def search_log_view("))]
for marker in ("_log_date_bounds(request)", "_apply_log_date_bounds(base,'at'", "date_period=date_period", "provider_values=providers_selected"):
    assert marker in search_view
assert "selected_region_label='All Regions'" in search_view
assert "selected_region_label=f'Regions:" in search_view
assert "search-log-total-count" in search_log
assert "search-log-footer-date" in search_log
assert "{% include 'portal/_date_filter_fields.html' %}" in search_log
assert search_log.index("provider-filter") < search_log.index("search-region-filter") < search_log.index("outcome-filter")

assert "sidebar-foot" not in base
assert "{{ PORTAL_COPYRIGHT }}" not in base
assert "Copyright ToughDev 2026" in about
assert "Niche opportunity intelligence" not in about

assert "resourceChartHeading.insertAdjacentElement('afterend',resourceCaptured)" in telemetry
assert "resourceCaptured.textContent=at?'Captured '" in telemetry
assert "box.appendChild(captured)" not in telemetry
assert "insertBefore(marketCoverageCard,discoveryToolbar)" in telemetry
assert telemetry.index("Discovery Performance") < telemetry.index("Market Coverage") < telemetry.index("Request Breakdown")

for marker in (
    ".search-log-total-count",
    ".search-log-footer-date",
    ".search-region-market{margin-left:8px",
    ".discovery-performance-card .market-coverage-card",
    ".resource-chart-captured",
    ".resource-range-bar>.range-divider,.resource-range-meta>.resource-data-days,.resource-range-meta>.resource-meta-separator{display:none!important}",
):
    assert marker in css

print("ScoutBox 0.11.81 regression checks passed")
