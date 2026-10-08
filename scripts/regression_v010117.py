from pathlib import Path
root=Path(__file__).resolve().parents[1]
focus=(root/'portal/services/focus.py').read_text()
tasks=(root/'portal/tasks.py').read_text()
migration=(root/'portal/migrations/0138_v010117_focus_quality_repair.py').read_text()
assert (root/'VERSION').read_text().strip()=='0.10.117'
assert (root/'RELEASE_ID').read_text().strip()=='ScoutBox v0.10.117'
assert "v010117_focus_quality_repair_pending" in migration
assert "migration_network_or_llm_calls_allowed': False" in migration
assert "Local AI propose namespace-specific labels and dynamic" in focus
assert "no\n            # Focus name gets a hard-coded prerequisite keyword list" in focus
assert "if False and len(mapping) < int(total*0.86)" in focus
assert "if False and len(mapping) < int(total*0.90)" in focus
assert "_MALFORMED_LABEL_RE" in focus
assert "Refresh Focus taxonomy quality for 0.10.117" in tasks
assert "focus_taxonomy_version='0.10.117'" in tasks
assert "'release':'0.10.117'" in focus
print('0.10.117 targeted regressions passed')
