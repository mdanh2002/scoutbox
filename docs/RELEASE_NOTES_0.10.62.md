# ScoutBox 0.10.62

0.10.62 is a UI, diagnostics, and forum-discovery behavior patch on top of 0.10.61.

## Fixed

- Search Activity provider-type counts now classify Search Engine, Direct Search, Cloud Provider, and Forum rows with case-insensitive provider matching and alias-safe filter values.
- Provider-type filtering no longer returns zero rows when a populated type is selected.
- Provider type and Provider filters now both use checkbox multiselect popovers with one aligned Select all / Deselect all control.
- Provider filter remains searchable and no longer uses the old single-select dropdown.
- Provider dropdown/table width is increased so DuckDuckGo and similar provider names are not prematurely truncated.
- Re-evaluation scope dialogs are wider so View Past Results, Cancel, Local AI Only, Cloud AI Only, and All Items can remain on one line on desktop.
- Clicking View Past Results closes the re-evaluation scope chooser before opening the history dialog.
- Opportunities, Hidden Leads, and Address Book all pass their history dialog to the scope chooser.
- Forum sources in Configuration > Search Sources > Forums now show health markers: OK, no-results, elevated-error, or idle.
- Career-page job-presence checks now remove common theme/CSS/JSON blobs before asking a small model to judge whether a job still exists.
- Concrete job-detail URLs with early exact role/company evidence are treated as strong presence evidence before the model is asked.

## Changed

- Forum discovery now browses known marketplace, jobs, recent, and listing areas first, then falls back to broad native forum search.
- Forum native fallback queries are intentionally broad opportunity phrases, not exact campaign technology combinations like `looking for contractor qemu`.
- Normal search-engine campaign planning excludes forum source domains so forum pages are owned by the Forum source path.

## Compatibility

No database migration is required for 0.10.62.

Routine future releases increment the patch component from 0.10.62.
