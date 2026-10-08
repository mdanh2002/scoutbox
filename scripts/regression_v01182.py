from pathlib import Path


root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.82"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.82"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.82"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.82"
assert (root / "docs/RELEASE_NOTES_0.11.82.md").exists()

about = read("templates/portal/about.html")
telemetry = read("templates/portal/telemetry.html")
css = read("portal/static/portal/app.css")

assert '<p class="about-copyright"><span aria-hidden="true">©</span> 2026 ToughDev. All rights reserved.</p>' in about
assert "Copyright ToughDev 2026" not in about
assert ".about-hero .about-copyright" in css
assert "font-size:10.5px" in css

assert telemetry.index("<h4>Languages</h4>") < telemetry.index("<h4>Markets</h4>")
assert "marketCoverageCard.classList.remove('card','full')" in telemetry
assert "marketCoverageCard.classList.add('market-coverage-section')" in telemetry
assert "insertBefore(marketCoverageCard,discoveryToolbar)" in telemetry
assert ".discovery-performance-card .market-coverage-section" in css
assert ".market-coverage-legend-groups{display:block!important}" in css
assert ".market-coverage-legend{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
assert ".market-coverage-copy{max-height:none!important;overflow:visible!important" in css

print("ScoutBox 0.11.82 regression checks passed")
