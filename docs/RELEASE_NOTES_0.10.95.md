# ScoutBox 0.10.95

## Corrective list-search behavior

- Removes the 0.10.94 global behavior that invented a search box for every list/sort table.
- Restores the same search-control footprint that existed before that change; no new search field is added to a list that did not already have one.
- Removes the extra Query Rotation search control introduced in 0.10.94.
- Existing client-side list searches use rendered table-cell text only and ignore hidden `data-search` payloads, record metadata and tooltip data.
- Existing server-backed Opportunity and Hidden Lead searches are restricted to fields represented by their list rows; hidden job descriptions and Company Info research cannot make an unrelated row match.

## Company Info domain tooltip and maintenance

- Keeps the existing Company Info icon and compact age/size display unchanged.
- Adds two tooltip-only lines when a defensible company-controlled domain is known: `Domain: example.com` and `Domain age: 15 years` (or `Unknown` when registration age cannot yet be resolved).
- Separates deterministic domain/RDAP maintenance from Local/Cloud AI lifecycle state. A pending domain-age refresh no longer makes an otherwise complete company profile trigger another AI research pass.
- Adds a bounded periodic domain-registration maintenance task. It reuses normalized-domain cache evidence, retries failed RDAP lookups no more than every six hours, and makes no AI calls.
- Preserves official website/domain hints during Company Info normalization and rejects ATS/job-board hosts as company domains.
- Existing 0.10.94 refresh markers are picked up automatically after upgrade.

## Resource Usage long-range repair

- Fixes the 7-day, 30-day and All Data chart failure caused by annotating an aggregate onto the existing `ResourceSample.at` model field.
- Uses a non-conflicting internal sample-time alias and then normalizes it for chart output.
- Long ranges continue to aggregate hourly first and are adaptively condensed to a bounded point count: roughly hourly at 7 days and about three-hour resolution for 30 days on a normal desktop-sized target.
- Preserves min/average/max CPU, RAM and GPU values for each display bucket so short spikes remain available to hover diagnostics.
- An aggregation failure is now logged and falls back to a bounded raw-sample representation instead of silently returning an empty chart.
- Full retained Resource Usage export remains independent from display bucketing.

## Detailed-log retention UI

- Keeps **Config → General → Keep detailed logs for** at 14–180 days, default 90.
- Removes the visible `14–180 · business records and aggregate statistics are preserved` helper sentence from the settings row.
- The safety boundary is unchanged: detailed telemetry may expire, while business records and aggregate provider statistics remain protected.

## Button interaction correction

- Removes hover-time border-color changes from button/button-like controls.
- Hover feedback is a mild background change only; controls no longer lift, translate, or add a hover shadow.
- Pressed feedback remains momentary and keyboard `:focus-visible` keeps an accessibility outline independent of mouse hover.
- Applies the correction to shared button variants and page-specific controls, including Company Info refresh/history actions and export controls.

## Daily Digest subject and mail-state compatibility

- Scheduled and manual Daily Digest messages now use the same subject form, with no `TEST` prefix and no `ScoutBox 24-hour digest` wording:
  `[13 Sep 2026] - Daily Digest [15 new opportunities, 6 new leads, 2 contacts]`
- The date is the actual local submission date and the counts are the full rolling-24-hour totals, not merely the Top 20 rows shown in the body.
- Singular/plural grammar is generated from the totals.
- Manual-test identity remains available inside ScoutBox/body metadata rather than in the Subject.
- Adds an upgrade migration that maps legacy Resend notification rows recorded as `sent` to `accepted` when Resend/provider evidence identifies them. This does not claim inbox delivery.
- Provider acceptance and actual delivery/bounce/rejection remain distinct states.

## Upgrade

Run the normal ScoutBox database migrations before starting the web and worker services. The 0.10.95 migration is local-only; it performs no network or AI calls. Domain/RDAP refresh happens later in a bounded background maintenance task.
