# ScoutBox 0.10.27

## Fixed

- Naver public-search parsing now rejects breadcrumb/accessibility chrome such as `새 창 열림`, `Keep에 저장`, and host/path breadcrumbs as Opportunity titles.
- When a search title is contaminated, ScoutBox prefers trustworthy destination-page title evidence, including JobPosting JSON-LD and H1/title data.
- Existing Naver Opportunities are repaired only when a replacement title can be recovered with sufficient confidence.
- Opportunity and Hidden Lead Campaign filters now use a stable origin Campaign instead of the accumulating rediscovery many-to-many relation. Later campaign encounters remain available as provenance.
- URL-health (`200`/`403`/`404` etc.) refresh is scheduler-driven rather than page-view-driven. Checks older than 24 hours are queued in controlled batches; entries older than 90 days stop receiving recurring probes and retain their last-known status.
- Health-check timestamps are written only after the actual probe finishes.
- Recycle Bin Item Info values that are complete HTTP/HTTPS URLs are rendered as safe new-tab links.
- Local AI Discovery retains repeated coverage inside the configured Search window. Cloud Web Discovery treats the Search window as a hard minimum between automatic starts; manual runs therefore also postpone the next automatic run. Jitter has been removed from the model, UI, and scheduler.
- Opportunities adds a modal Filter immediately after Re-evaluate for Apply Via, Remote classification, and Post Age. Active advanced filters are summarized above the list and can be reset without clearing unrelated toolbar filters.
- Token Categories adds **Ad hoc Actions**, grouping manual re-evaluation, manual rebuild, provider/configuration model tests and equivalent explicitly marked utility AI work so it remains attributable against overall Token Usage.

## Upgrade

Includes migration `0083_v01027_origin_campaign_naver_schedule`. It adds nullable origin-Campaign foreign keys for Opportunities and Hidden Leads, conservatively backfills historical origin attribution, performs a conservative Naver-title repair, and removes the obsolete Search Jitter field.

Routine future releases increment the patch component.
