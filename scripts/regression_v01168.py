from pathlib import Path
root=Path(__file__).resolve().parents[1]
read=lambda p:(root/p).read_text()
assert read("VERSION").strip()=="0.11.68"
assert read("RELEASE_ID").strip()=="ScoutBox 0.11.68"
assert read("BUILD_INFO.txt").strip()=="ScoutBox v0.11.68"
assert read("README.md").splitlines()[0]=="# ScoutBox 0.11.68"
stats=read("templates/portal/stats.html")
assert "id.textContent=' #'+recordId" in stats
assert "(#'+recordId+')'" not in stats
assert "(recordId?' #'+recordId:'')" in stats
print("ScoutBox 0.11.68 regression checks passed")
