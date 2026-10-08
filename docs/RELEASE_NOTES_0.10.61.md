# ScoutBox 0.10.61

0.10.61 is a focused UI and diagnostics patch on top of 0.10.60.

## Changes

- Hides the explanatory Forum-source sentence from Configuration > Search Sources > Forums.
- Keeps the Forum checkbox list clean and aligned without repeated Forum/software tags.
- Renames the Preferred Sources tab to Preferred Search Engines and adds a brief Local AI initial-search hint.
- Removes unwanted top spacing/misalignment from Preferred Search Engines, Custom Domains, Schedule / Limits, and Facebook tabs.
- Fixes Search Activity provider-type filtering so selected source types do not collapse the list unexpectedly.
- Adds Select all and Deselect all controls inside the Provider types dropdown.
- Uses compact Provider types summary labels: All types, N out of 4 selected, or None selected.
- Keeps the provider selector searchable and widens provider display so DuckDuckGo is not unnecessarily truncated.
- Adds View Past Results to the re-evaluation scope chooser for Opportunities, Hidden Leads, and Address Book.
- Retains the 0.10.60 Forum source category/reporting work and keeps Reddit unchanged.

## Migration

No database migration is required for 0.10.61.

Routine future releases increment the patch component from 0.10.61.
