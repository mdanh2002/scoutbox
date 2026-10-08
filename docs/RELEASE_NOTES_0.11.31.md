# ScoutBox 0.11.31

ScoutBox 0.11.31 fixes the list multi-select dropdown presentation introduced in 0.11.29/0.11.30 and cleans up re-evaluation history detail panels.

## Fixes

- Campaign, Location, and Focus multi-select filters now match the Search Activity provider dropdown layout: search box first, Select/Deselect all row, divider, then one-line checkbox/icon/name/count rows.
- The broken extra square in Campaign/Location/Focus dropdowns was removed by restoring the search field as a full text input and hiding internal mode fields.
- Country-facing list filter copy now uses Location wording so region-style values such as Africa and Other are not mislabeled.
- Re-evaluation result detail panels no longer repeat the run timestamp/progress/provider/model/internet-search metadata on the right side.
- Re-evaluation counts hide zero-value chips and show only useful non-zero values such as checked and need review.

## Carry-forward

- Retains the 0.11.30 hotfix for `/cold-contact/`.
- Retains the 0.11.29 Hidden Lead reassessment resiliency and low-priority Local AI maintenance-lane behavior.
