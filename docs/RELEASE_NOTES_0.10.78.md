# ScoutBox 0.10.78

ScoutBox 0.10.78 is a focused reliability and usability release on top of 0.10.77. It addresses the telemetry/header alignment and Address Book navigation requests, adds a one-hour diagnostic export, and reduces the persistent "stalled at Reddit/search" failure mode.

## Fixed and changed

- **Telemetry export alignment:** Token Usage and Discovery Performance now use the same heading right padding and zero trailing icon margin, so their heading export icons share the same right edge. The Token Usage scope label (`All tokens` or the selected model) remains immediately to the left of its export action.
- **Address Book company homepage link:** when a contact has a distinct company line and a valid stored email, the company line is now a link to `https://<email-domain>/`. It no longer uses the contact/source URL for this shortcut. Hovering shows the email domain in the native tooltip, and hover/focus underlines the company name. Existing contact editing, source-link, country, summary, and health logic is unchanged.
- **Diagnostic export — Last 1 hour:** Maintenance > Export Diagnostic Data now offers `Last 1 hour`; the backend accepts `1h`, `1hr`, and `1hrs` and applies a one-hour cutoff to time-filtered diagnostic/record sections.

## Discovery stall mitigation

Field behavior showed that many apparent stalls were not a dead worker: the campaign heartbeat stayed alive while a source adapter performed several **sequential blocking network requests**. Reddit was the clearest case: up to ten search variants could each wait for the generic 20-second request timeout, so a degraded Reddit endpoint could occupy one campaign stage for several minutes. Normal search providers could likewise keep consuming their per-provider stage window after repeated request errors.

0.10.78 adds bounded fail-fast behavior without reducing healthy-provider query allowance:

- Reddit defaults to at most 6 query variants per pass, a 75-second pass budget, a 10-second request timeout, and an early stop after 2 consecutive request errors. Remaining variants rotate into later runs. Failed OAuth acquisition is negative-cached for five minutes so multiple campaigns do not repeatedly pay the same auth timeout before falling back to Reddit's public JSON endpoint.
- Normal campaign search providers stop the current provider after 2 consecutive request errors instead of repeatedly waiting until the full provider-stage budget expires. The same guard now covers direct-source search fallback and exact-employer resolution. A successful request resets the error streak.
- Hidden Leads scanning applies the same consecutive-error cutoff per search provider, so an unavailable engine does not consume all six query slots before the scan moves on.
- These limits are configurable with `SCOUTBOX_REDDIT_MAX_QUERIES_PER_PASS`, `SCOUTBOX_REDDIT_PASS_MAX_SECONDS`, `SCOUTBOX_REDDIT_REQUEST_TIMEOUT_SECONDS`, `SCOUTBOX_REDDIT_MAX_CONSECUTIVE_ERRORS`, and `SCOUTBOX_SEARCH_PROVIDER_MAX_CONSECUTIVE_ERRORS`.

This does not hide provider errors: the bounded-exit reason is retained in discovery error diagnostics/Search Activity context so a repeatedly unhealthy provider remains visible.

## Maintenance: Recover Stalled Operations

Maintenance now includes the amber **Recover Stalled Operations** action. It is intentionally a last-resort operation and requires typing `RECOVER`.

The recovery action:

- identifies current queued/running/stopping CampaignRun rows and queued/running BackgroundJob rows;
- revokes their Celery task IDs with termination requested and retires their persistent rows so they cannot continue blocking scheduling after a container restart;
- reconstructs and preserves partial discovery counts for interrupted campaign runs where possible;
- clears only ScoutBox-owned Redis coordination namespaces used for local-AI lanes and search-provider pacing (`scoutbox:local-ai:lane:*` and `scoutbox:search-provider:last:*`), leaving Celery broker data and user records untouched;
- queues one replacement for each affected enabled, non-recycled campaign pass, preserving normal versus Forum-only pass type;
- restarts an interrupted Hidden Leads scan;
- releases other one-off background jobs without automatically replaying them, because blindly replaying email/draft/import/application tasks could duplicate external side effects;
- writes one `maintenance_recovery` Audit Trail entry summarizing the recovery.

The operation does **not** delete Opportunities, Hidden Leads, Address Book contacts, Applications, campaign definitions, profiles, or credentials.

## Regression coverage

`portal/tests/test_v01078.py` adds runtime coverage for the email-domain company link, one-hour diagnostics period, Reddit consecutive-error cutoff, and persistent-state recovery/requeue behavior. `scripts/regression_v01078.py` adds release-level source assertions for the UI alignment, stall guards, Maintenance wiring, and safe Redis key scope.

All v0.10.77 regressions remain in the package, including the request-level `/opportunities/` HTTP 200 regression and Address Book promotion-audit cleanup coverage.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application files with the 0.10.78 full package, then run the normal restart/upgrade flow:

```bash
./restart_scout_box.sh
```

No new database migration is required by 0.10.78. The existing 0.10.77 migration remains part of the full package and continues to apply automatically on systems that have not yet run it.
