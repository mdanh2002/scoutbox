# ScoutBox 0.8.36

Released on 2026-08-20 23:58:00.

This focused release improves the safety and diagnosability of **AI & Discovery → Discovery** and corrects campaign run-duration presentation. All 0.8.35 behavior remains unless described below.

## AI & Discovery confirmations

- Saving routing/token caps now asks for confirmation before future campaign routing is changed.
- Auto Select, Optimize for Local, and Optimize for Cloud each ask for confirmation before replacing stage routing.
- Test Model asks for confirmation before sending live model/search requests.
- Test Discovery asks for confirmation before opening the live diagnostic workflow and clearly states that it does not persist opportunities or modify campaign data.
- Discovery-mode changes retain their existing confirmation.

## Persistent Test Model diagnostics

- Pipeline validation continues to be stored in the existing `BackgroundJob` result, so no schema migration is required.
- The Discovery page restores the most recent valid completed stage results after navigation/reload.
- A **Last model test** hint shows the latest test timestamp and warns when routing changed or the latest run did not complete.
- Tested stage names become clickable links. Clicking a stage opens its stored provider/model result, request attempt details, and failure reason.
- The Test Model result area now shows a pass/failure summary and expandable per-stage details instead of immediately reloading the page and hiding the diagnostic result.
- Failed stages expand automatically; all raw stored stage records remain available from the details view.
- Changing a stage route/token cap resets that stage to the gray question mark until it is tested again.

## URL discovery validation

- In Source-Guided mode, URL discovery is validated against up to three enabled search engines because that stage is search-engine backed rather than AI-model backed.
- The stage passes when at least one tested search engine returns parsed results, so a temporary block/rate limit from one engine no longer makes the whole URL discovery stage fail.
- Every tested search provider is still reported with result count, latency/mode when available, and its individual error/failure reason.
- In Cloud Web mode, URL discovery continues to validate the actual configured cloud web-search model route.
- The persisted validation signature now includes enabled Search Source configuration, so search-provider changes invalidate stale URL-discovery checkmarks.

## Campaign duration

- Last Run Duration now measures end-to-end elapsed time from the CampaignRun being queued/created until it finishes, so worker queue delays and fast-failure timestamp edge cases are visible instead of being hidden. The underlying minute value remains full precision for sorting/export.
- Display precision is adaptive: short runs use two decimal places, longer runs use one decimal place, and sub-0.01-minute runs display as `<0.01 min` instead of the misleading `0.0 min`.
- Existing completed/failed/stopped timed-run selection behavior is otherwise unchanged.

## Compatibility

- No new database migration is required.
- Existing PostgreSQL/Redis/media volumes, `.env`, encryption keys, Recycle Bin data, campaign history, and saved model-test BackgroundJobs are preserved during an ordinary upgrade.
