from pathlib import Path


root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.85"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.85"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.85"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.85"
assert (root / "docs/RELEASE_NOTES_0.11.85.md").exists()

telemetry = read("templates/portal/telemetry.html")
stats = read("templates/portal/stats.html")
css = read("portal/static/portal/app.css")

assert "Segments count executed requests." not in telemetry
assert "node.append(document.createTextNode('.'))" not in telemetry
assert "function renderRingSummary(node,segments)" in telemetry
assert ".market-coverage-legend-groups h4{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css
assert ".market-coverage-heading-total{justify-self:start" in css

assert "<h3>Discovery Source</h3>" in stats
assert "Opportunities by Discovery Source" not in stats
assert "Rejection / Suppression Reasons" not in stats
assert 'data-table-filter="reject-table"' not in stats
assert "<h3>Acquisition Path</h3>" in stats
assert "Opportunity Quality by Acquisition Path" not in stats

print("ScoutBox 0.11.85 regression checks passed")
