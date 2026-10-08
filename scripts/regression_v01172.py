from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(name): return (root/name).read_text(encoding="utf-8")
assert read("VERSION").strip()=="0.11.72"
s=read("restart_scout_box.sh")
assert "dc build web worker discovery_worker forum_worker beat" in s
assert '[[ -d "$ROOT/stats_service" && -f "$ROOT/stats_service/Dockerfile" ]]' in s
assert "dc build stats_service" in s
assert "dc up -d stats_service" in s
assert "ScoutBox will continue normally without it" in s
assert "dc build\n" not in s
print("ScoutBox 0.11.72 regression checks passed")
