# ScoutBox 0.9.56

## Manual filter Fit refresh

- Manual Opportunity and Hidden Lead filtering now recalculates the 0-100 Fit score in the same selected cloud/local model request used for the second-pass quality decision.
- The previous and new Fit scores are retained in each background-job result and in the per-record manual-filter audit state.
- Opportunity manual filtering updates `fit_score`; Hidden Lead filtering updates `score`.
- Fit recalculation does not alter remote status, freshness, salary, or other enrichment fields.

## Detailed completion email

- Manual-filter completion email still contains the aggregate counts, provider/model, and Internet Search state.
- It now lists every Fit score that changed, including the entry name, record ID, before/after score, and final filter decision.
- It separately lists every Opportunity or Hidden Lead moved to the Recycle Bin, including before/after Fit and the filter reason.
- The complete generated message remains stored in Email History through the existing notification `MailEvent` record.

## Latest filter result

- Opportunities and Hidden Leads now show a Fit before/after column in the Latest Filter Result table.
- A changed score is visually emphasized and the model's Fit reason is shown below the filter reason when available.

## Fit sorting

- The Fit icon in every Opportunity and Hidden Lead list row is now clickable.
- First click sorts the complete filtered inventory by Fit from highest to lowest; another click reverses it.
- Fit ordering is server-side, so it applies across all pages rather than only the currently visible rows.
- Existing search/filter/page-size settings are preserved while Fit sorting is active.

No database migration is required for 0.9.56.
