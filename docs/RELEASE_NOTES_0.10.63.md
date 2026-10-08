# ScoutBox 0.10.63

0.10.63 is a focused patch on top of 0.10.62.

## Fixes

- Fixed Search Activity provider-type counts for Search Engine, Direct Search, Cloud Provider, and Forum.
- Fixed provider-type filtering so selecting Search Engine or other types no longer returns zero rows incorrectly.
- Removed the stray square above the Select/Deselect row in the provider dropdown.
- Kept Provider types and Providers dropdowns mutually exclusive: opening one closes the other, and filter refreshes keep their counts in sync.
- Kept the Provider types dropdown compact while the Providers dropdown remains searchable and multi-select.
- Cleaned Pages to Watch by removing existing Facebook page rows during the upgrade migration and strengthened validation to reject login/system/unrelated Facebook pages before new rows are saved.
- Preserved the 0.10.62 forum browsing behavior: marketplace/listing pages are inspected before broad fallback search.

Routine future releases increment the patch component from 0.10.63.
