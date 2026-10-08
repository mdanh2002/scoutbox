# ScoutBox 0.11.30

Hotfix release for ScoutBox 0.11.29.

## Fixes

- Fixed `/cold-contact/` HTTP 500 caused by the Hidden Lead history label context variable not being initialized after the 0.11.29 history popup changes.
- Added a regression guard to ensure the Hidden Lead list view assigns `hidden_lead_filter_history_label` before rendering.

## Carried forward from 0.11.29

- Hidden Lead reassessment GPU/backoff and monotonic-progress fixes.
- Meaningful-only re-evaluation history across Hidden Leads, Opportunities, and Address Book.
- Campaign/template deleted-button sizing fix.
- Searchable multi-select filters for Campaign, Country, and Focus list filters.
