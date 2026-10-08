# ScoutBox 0.10.88 Release Notes

## Blacklist safety and review dialogs

- Opportunity and Hidden Lead bulk blacklist actions now use the same checkbox review dialog.
- Dialogs show `Company domain` only when the domain looks company-owned for the selected company.
- Job boards, ATS hosts and aggregators are hidden from the dialog and are never submitted as blacklist domains.
- Examples such as `jobs.linkedin.com`, `linkedin.com/jobs`, `jobs.sitepoint.com`, `himalayas.app`, `greenhouse.io`, `lever.co`, and mild platform variations are treated as non-company domains.
- Company-specific domains such as `facebook.com` for Facebook, `careers.facebook.com` for Facebook, `pivotalhealth.com` for Pivotal Health, and similar normalized matches may be shown as review context.
- Backend submission remains authoritative: Opportunities and Hidden Leads create company-name-only blacklist rules, even if stale or edited browser data is submitted.
- Standalone Blacklist buttons were removed from Opportunity and Hidden Lead detail pages to keep blacklist behavior centralized in the list review dialogs.

## Upgrade recovery

- Migration `0113_v01088_blacklist_domain_recovery.py` retires remaining active non-built-in aggregator/job-board blacklist domains across scopes.
- Plausible company labels on those retired rows are converted into company-name-only blacklist rules.
- Opportunities suppressed only by the retired aggregator-domain rule are restored, then exact company-name rules are re-applied where conversion preserved the user's selected company.

## List-table headers

- Sortable/list headers no longer collapse into `...` in narrow columns.
- Search Activity, Discovery Source Activity, Discovery Performance and Performance Lab tables have explicit width guards for Results/Latency-style columns while preserving horizontal scrolling.

## Version

- `VERSION`: `0.10.88`
- `RELEASE_ID`: `ScoutBox v0.10.88`
