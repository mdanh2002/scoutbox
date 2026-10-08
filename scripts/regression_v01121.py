#!/usr/bin/env python3
"""ScoutBox 0.11.21 regression: empty re-evaluation histories stay hidden."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
extras=(root/'portal'/'templatetags'/'portal_extras.py').read_text()
views=(root/'portal'/'views.py').read_text()
assert "not recalculated" in extras
assert "_manual_filter_has_numeric_score" in extras
assert "_manual_filter_result_has_visible_entries" in views
assert "A checked/review count by itself is not a useful result" in views
assert "manual_filter_has_meaningful_result" in extras
for py in [root/'portal'/'templatetags'/'portal_extras.py', root/'portal'/'views.py']:
    ast.parse(py.read_text())
print('0.11.21 regression checks passed')
