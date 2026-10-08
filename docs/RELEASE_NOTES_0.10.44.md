# ScoutBox 0.10.44

Repair release for regressions identified in 0.10.43.

## Fixed

- `/gpt-log/` no longer raises a server error from invalid model-field filters.
- Audit Trail search/type filtering no longer creates malformed `[object HTMLSelectElement]` URLs.
- Shared async list toolbar handling now normalizes controls back to their owning form before building request URLs.
- Hidden Leads and Address Book have compact Company filter dialogs containing both Company Size (employees) and Company / Domain Age.
- Company size and age checkboxes align consistently in grid columns across filter dialogs.
- Company Info size/age filtering does not use job boards, ATS hosts, social sites, or search platforms as the company identity.
- Stored platform-derived Company Info is cleaned by migration `0095_v01044_release_repair`; records with no real employer stay unknown.
- Korean/CJK/search-shell fragments are removed more defensively from stored Opportunity titles and company labels.
- Campaign run summaries are normalized so visible “found” counts prefer newly-created records.
- Diagnostic export now labels the records content group as “ScoutBox Data & Records”.

## Upgrade

Run the normal ScoutBox restart/migration process after replacing application files:

```bash
./restart_scout_box.sh
```
