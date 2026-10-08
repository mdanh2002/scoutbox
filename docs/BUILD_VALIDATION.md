# ScoutBox 0.10.102 build validation

The 0.10.102 release is checked before packaging and again after extracting the final ZIP.

Static validation covers release identity, Python compilation and AST parsing, targeted 0.10.102 regressions, Compose YAML where PyYAML is available, base-template JavaScript syntax where Node is available, shell syntax, migration/backfill invariants, and bytecode-cache cleanliness. Django tests are included under `portal/tests/test_v010102.py`; run them in a normal ScoutBox runtime with dependencies installed.
