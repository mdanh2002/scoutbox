# ScoutBox 0.11.92

## Fixed

- Repaired Facebook Page title recovery so page identity can be resolved independently from hiring/relevance validation. Blank 0.11.91 rows are automatically re-queued with bounded retries and no manual retry button.
- Tracking Link article titles now treat legacy rule/slug labels such as `Pictts` as stale and refresh them from the live page title. Stale labels are not rendered as if they were document titles while refresh is pending.
- DOCX link scanning now returns only links under the configured Blog Base URL, removes the Trackable/Result column, keeps URL/title on one row, centers Test actions, and preserves the loading spinner.
- Long-range CPU/RAM/GPU charts no longer let usage-only timeline points crowd out retained hardware samples. Synthetic usage points do not break hardware lines; real telemetry gaps remain discontinuities.
- HTML email previews use a light canvas and no longer force dark foreground/background colors over sender HTML in Email History or the IMAP browser.
- Search Activity gives Date enough room for the full timestamp, truncates Query first, avoids the normal desktop horizontal scrollbar, and labels the filter `All Outcomes`.
- Discovery Activity reserves space for the Avg Latency sort glyph and keeps the server-rendered column order unchanged.
- Discovery Evidence display collapses redundant provider truncation dot runs without changing stored evidence.
- Blacklist Scope and Date Added columns are compacted.
- Blacklist, Tracking Links, and Facebook Pages toolbars use aligned button shells; Show Deleted is intentionally a slightly larger glyph.
- Facebook Pages moves the action toolbox to the upper right and the item count into the bottom-right pager row. All is neutral; only New/Seen is highlighted, with consistent tooltips.
- Tracking Links action order is Refresh, Delete, Show Deleted, New; Delete uses the neutral toolbar style and the item count lives in the footer.
- Email History item counts use normal weight and improved spacing from Range controls.
- Support exports now include the newest 5,000 matching ResourceSample rows in chronological order, plus exported range and total-match metadata.

## Upgrade

Migration `0164_v01192_followup_repairs` re-opens unresolved blank Facebook Page titles for the repaired automatic identity-title resolver and records the 0.11.92 upgrade audit event.

## Version sequence

The next release is 0.11.93; subsequent releases continue 0.11.94, 0.11.95, and so on, even for small fixes.
