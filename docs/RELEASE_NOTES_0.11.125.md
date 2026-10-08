# ScoutBox 0.11.125

## Re-evaluation restore fix

- Restore now appears for every result normalized to **Recycle**, including historical `reject`, `rejected`, and `recycle` decision spellings.
- The same fix applies to Opportunities, Hidden Leads, and Address Book.
- Restore continues to use ScoutBox's existing confirmation prompt and Recycle Bin restore path.

## Recycled-result navigation

- Recycled Opportunity and Hidden Lead results no longer link to active detail routes.
- This prevents 404 pages such as `/cold-contact/<id>/` when the underlying record has already been moved to the Recycle Bin.
- Cross-list conversions remain Keep outcomes and continue linking to the converted destination record.

## History display cleanup

- Completed re-evaluation run summaries no longer show a redundant `N checked` total.
- Re-evaluation dialog subtitles now use `Showing N Opportunity re-evaluation results`, `Showing N Hidden Lead re-evaluation results`, and `Showing N Address Book re-evaluation results`.
- Keep remains green, Recycle amber, Failed red, and Strong Fit cyan.

Migration `0197` is release-audit only; there is no schema change.
