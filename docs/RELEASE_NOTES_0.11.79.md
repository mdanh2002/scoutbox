# ScoutBox 0.11.79

## Discovery Markets

- Adds a flag before every market name and keeps Worldwide Remote last with a globe.
- Moves the local-language checkbox immediately above Save Discovery Markets.
- Removes the long multilingual guidance paragraph without adding replacement hints.
- Interleaves native-market and additional-language work so enabled-market languages are not starved.
- Reserves three of every four early market slots for Worldwide/proven markets and one for a rotating exploration probe.

## Search and activity correctness

- Excludes market-summary telemetry and blank bookkeeping rows from Search Activity.
- Removes unbounded totals from collapsed Search Activity, AI Requests, and Audit filters while retaining option counts inside dropdowns.
- Normalizes multi-site queries before Dashboard progress is published.
- Prevents long provider names from overlapping compact regional settings.
- Suppresses routine five-minute scheduler-resume audit entries while retaining scheduler-health telemetry.

## Jobicy and location integrity

- Preserves all current-listing regions, including APAC and EMEA on the same role.
- Uses JobPosting hiringOrganization as authoritative current-listing employer evidence.
- Re-applies the company blacklist immediately after authoritative identity correction.
- Rejects compiler/toolchain uses of GCC as geographic evidence and repairs the known Buildroot value.

## Diagnostic export

- Queues diagnostic preparation as a background job instead of holding a browser request open.
- Keeps progress active across collection and archive creation, survives page refresh, and downloads only when ready.
- Uses an authenticated job-specific download and expires stored archives after one day.

## Upgrade repair

- Removes existing exact five-minute scheduler audit noise.
- Repairs the reported Jobicy role's employer and two-region eligibility, then applies an existing Canonical blacklist rule if present.
