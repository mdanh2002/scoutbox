#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.3 dynamic Focus label evidence repair.

The release environment used for packaging may not have Django installed, so these
checks assert the safety-critical guardrails directly in the source file.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
focus = (root / 'portal' / 'services' / 'focus.py').read_text()
tasks = (root / 'portal' / 'tasks.py').read_text()
migration = (root / 'portal' / 'migrations' / '0142_v0113_focus_label_evidence_repair.py').read_text()

required = [
    "FOCUS_TARGET_VERSION = '0.11.3'",
    "_LABEL_WEAK_HEAD_NOUNS",
    "def _anchor_label_tokens",
    "def _token_supported_by_text",
    "anchor_tokens=_anchor_label_tokens(clean)",
    "supported_anchors={t for t in anchor_tokens",
    "records_by_id={int(r.pk):r for r in records}",
    "and _record_supports_focus_label(record,label)",
    "('Linux Systems Companies'",
    "('Systems Software Companies'",
]
for needle in required:
    assert needle in focus, f'missing focus guardrail: {needle}'

for forbidden in ("_CRITICAL_LABEL_TOKEN_ALIASES", "def _critical_label_tokens_supported"):
    assert forbidden not in focus, f'label-specific evidence gate remains: {forbidden}'

assert "'retro':" not in focus, 'retro-specific prerequisite aliases must not be hard-coded'
# Generic acronym expansion is allowed; label-specific prerequisite maps are not.

assert 'Repair Focus label evidence for 0.11.3' in tasks
assert 'v0113_focus_label_evidence_repair_pending' in migration
assert 'ollama' not in migration.casefold()
assert 'fetch' not in migration.casefold()
print('ScoutBox 0.11.3 Focus label evidence static regression checks passed.')
