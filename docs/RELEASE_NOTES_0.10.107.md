# ScoutBox 0.10.107

Released: 2026-09-13

## Fixed

- Removed campaign-dominance Focus assignment. Campaigns remain discovery provenance and weak Local AI context only; they cannot directly force a Focus value.
- Removed the weak peer-similarity fallback that could push unrelated records into the dominant campaign label when Local AI was unavailable.
- Added Focus assignment provenance in existing JSON metadata for future repair/debugging.
- Added a one-time upgrade repair that detects suspiciously dominant Focus labels and clears only rows whose own content does not support that label, across Opportunities, Hidden Leads and Address Book.
- Stopped old queued/running Focus rebuild/backfill jobs during upgrade so stale workers cannot keep applying the obsolete behavior.
- Merged blank and explicit `Unclassified` values into one Focus dropdown option.
- Moved the Discovery Activity loading spinner beside the `Discovery Activity` heading text; date-range buttons no longer shift during 14-day/30-day loads.

## Validation

- Static release verification.
- Python syntax/AST validation.
- Targeted 0.10.107 regression checks.
- Compose YAML and shell syntax checks where local tooling is available.
