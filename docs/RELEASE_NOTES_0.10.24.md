# ScoutBox 0.10.24 release notes

ScoutBox 0.10.24 fixes two Opportunity-list presentation/sorting regressions.

- Remote badges no longer expose internal model enum labels such as `fully_remote`. Machine-style labels are normalized to ScoutBox's existing human-readable labels while retaining the original structured status and confidence.
- Post Age cells now expose a numeric age-in-days sort key to the existing dense-table sorter. ScoutBox prefers `extracted_facts.post_age.age_days`, falls back to the retained posted/best date, and finally maps legacy display buckets to stable numeric values.
- The visible Post Age text, confidence colours, and freshness evidence are unchanged; only ordering uses the raw/derived numeric value.

0.10.24 has no database migration or database schema change.

Routine future releases increment the patch component on the 0.10.x line unless a release is deliberately designated as major.
