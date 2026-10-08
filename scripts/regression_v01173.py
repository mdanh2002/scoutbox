from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(name): return (root/name).read_text(encoding="utf-8")
assert read("VERSION").strip()=="0.11.73"
a=read("templates/portal/about.html")
assert "<span>External Statistics</span>" in a
assert "{% icon 'source_direct' %}" in a
assert "GET /health" in a and "POST /test" in a and "POST /sync" in a
assert "EXTERNAL_STATS_URL=http://stats_service:8787" in a
assert '"links": [' in a and '"total": 12' in a and '"human": 9' in a
assert "pageviews" not in a[a.index('<span>External Statistics</span>'):]
assert "request_logs" not in a[a.index('<span>External Statistics</span>'):]
print("ScoutBox 0.11.73 regression checks passed")
