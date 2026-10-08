# ScoutBox 0.8.10 release notes

ScoutBox 0.8.10 is a reliability and UI refinement release based on the verified 0.8.9 package.

## Read/unread and blacklist reliability

- Opportunity and Market Studies row interactions now persist read state through the dedicated read-state endpoint using keepalive requests.
- Bulk Mark as Read and Mark as Unread actions remain available; explicit Mark as Unread is the final override.
- Blacklist editing now uses one unambiguous `blocked` checkbox value, so clearing Blocked persists as Disabled for built-in and custom rows.
- Search providers that are configured and healthy but have not been requested today use a blue informational `i`, distinct from warning/no-result states.

## Tracking Links

- Test & Generate remains asynchronous and its BackgroundJob is remembered, so leaving and returning to the page resumes the same progress/result instead of appearing stuck.
- Per-article suffix reserves are persisted in `TrackingSuffixReserve` (migration 0009).
- A reserve refill generates up to 240 article-related suffix candidates in one routed-model call, then falls back to deterministic article-keyword combinations if needed.
- Subsequent allocations consume the saved reserve first and only refill once the reserve is empty.

## Application drafts

- The email-editor save icon now commits ScoutBox application changes and creates/updates the IMAP Drafts copy in one action.
- The redundant separate Save/Update IMAP Draft control was removed.
- The save action is right-aligned in the email-editor heading and has a tooltip.
- ATS answer provider and model controls share one row; model override is a provider-driven dropdown with Automatic as the default.
- Completed background jobs are no longer repeatedly returned to the editor, eliminating the recurring page reload loop.
- Application Drafts now link the email subject/role directly to the draft editor and no longer have a redundant Action column.

## Resource Usage and Statistics

- CPU, Memory and GPU are rendered as thin line series without point markers.
- NVIDIA GPU telemetry uses NVML when available and falls back to `nvidia-smi`; unavailable GPU data is labelled explicitly rather than shown as zero.
- Request count is plotted as a dashed comparison series on a right-side axis and is included in chart hover details.
- Input Tokens exposes a hover breakdown of input-token percentages by processing purpose.
- Search Provider Performance remains sorted provider A-Z.
- Statistics Last updated now lives in the top filter/export toolbar.
- Pages scraped, Tokens consumed and Data downloaded moved into the top metric strip; the redundant Performance Summary card was removed.

## Discovery and dashboard refinements

- Test Discovery always exposes Stage diagnostics and Raw diagnostic result, including fallback diagnostic content for older/incomplete runs with no structured stage trace.
- Post-age list/detail icons now use face-style age indicators: smiling/new, neutral/medium, sad/old, and question-mark/unknown, with distinct age colors.
- Dashboard section headings link directly to Current opportunities, Recent campaigns, Recent errors and Audit Log; redundant View all links remain removed.
- The Search Provider health summary tag remains hidden from Dashboard while elevated-error and no-result conditions continue to surface in Recent errors.
- Diagnostic refresh remains on the right of the Diagnostics heading with improved spacing.
- AI-runtime readiness detail alignment was adjusted.

## Refresh-loop fixes

- Application editor and Applied Role Import now query only queued/running background jobs. Completed jobs can no longer trigger an endless reload cycle.
