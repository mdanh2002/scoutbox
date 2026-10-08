# ScoutBox 0.11.114

- Replaces the Statistics **Opportunity Status** pie chart with **Opportunity by Domain**.
- Opportunity domains use the same public role-link rule as the Opportunities list: `target_url` first, then `url`, lower-case hostname, with a leading `www.` removed.
- Keeps the eight highest-volume domains visible and combines the remaining domains into **Other**, keeping the pie and legend bounded while preserving the complete represented count.
- The new domain chart follows the active Statistics period, custom From/To range, and Statistics query because it is calculated from the same filtered Opportunity queryset.
- Fixes **Leads by Country** so a stored multi-location value such as `United States, France` is represented as separate **United States** and **France** slices instead of one combined country label.
- Applies the same normalized one-location-per-slice construction to **Opportunities by Country** for consistency.
- Country/domain pie legends now render every visible slice, including **Other**, instead of drawing an unlisted extra slice; full normalized country names are no longer cut to a fixed character count.
- Preserves the 0.11.113 date-range validation and all Tracking Links/resource-chart behavior.

No schema change is included; migration 0186 records the release upgrade only.

Next release: 0.11.115.
