# ScoutBox 0.11.124

## Re-evaluation result clarity

- Opportunity, Hidden Lead, and Address Book re-evaluation detail rows now show only three user-facing decisions: **Keep**, **Recycle**, and **Failed**.
- **Keep** badges are green.
- **Recycle** badges are amber.
- **Failed** badges are red.
- Historical/internal `review`, `protected`, `skipped`, and cross-list conversion outcomes are counted as Keep for the user-facing summary rather than appearing as separate decision categories.
- Timeout results are included in Failed for the user-facing summary.
- Cross-list conversion behavior itself is unchanged; converted entries continue to link to their destination record.

## Restore from re-evaluation history

- Recycled Opportunity, Hidden Lead, and Address Book results now show **Restore** on a new line beneath the reason/Fit information.
- Restore uses ScoutBox's existing confirmation prompt and Recycle Bin restore mechanism.
- Only records actually recycled by re-evaluation show Restore. Cross-list conversions do not.

## Result summary colors

- Checked remains neutral.
- Kept is green.
- Recycled is amber.
- Strong Fit is cyan.
- Failed is red.
- Latest-result banners and per-run history summaries use the same collapsed counts.

Migration `0196` is release-audit only; there is no schema change.
