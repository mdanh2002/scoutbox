from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding="utf-8")
assert read("VERSION").strip()=="0.11.67"
assert read("RELEASE_ID").strip()=="ScoutBox 0.11.67"
assert read("BUILD_INFO.txt").strip()=="ScoutBox v0.11.67"
assert read("README.md").splitlines()[0]=="# ScoutBox 0.11.67"
stats=read("templates/portal/stats.html")
views=read("portal/views.py")
css=read("portal/static/portal/app.css")
assert "stats-map-record-popover-id" in stats
assert "id.textContent=' (#'+recordId+')'" in stats
assert "'id':row.pk" in views
assert "item['id']=str(item.get('id') or '').strip()[:24]" in views
assert ".stats-map-record-popover-id{" in css
print("ScoutBox 0.11.67 regression checks passed")
