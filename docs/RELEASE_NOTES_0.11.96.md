# ScoutBox 0.11.96

## Tracking Links

- Fixes article-native tracking suffix allocation. ScoutBox no longer HTTP-probes a candidate tracking URL before that URL exists; destination validation happens once, while database uniqueness and `IntegrityError` handling protect suffix/path allocation.
- Consolidates Tracking Link progress, scan state and errors into the top dialog status banner so a stale success message cannot remain visible beside a newer failure.
- Keeps Blog base URL on one compact line, removes the redundant DOCX section gap, and makes the add-link iframe scroll only when its content actually exceeds the available modal height.
- Gives the Clicks heading a dedicated sort-icon gutter.

## Statistics and telemetry ranges

- Removes the redundant Discovery Source table while retaining the Discovery Source Share chart and its source data/export support.
- Changes the default Statistics and Resource Usage period from 30 days to 24 hours. Longer ranges remain selectable.
- Renames visible timestamp headings to Time in Email History, AI Requests and Search Activity.

## Discovery localization

- Country-market searches now rotate deterministically through major cities, with periodic country-wide coverage. For example, Australian searches rotate through Melbourne, Sydney, Brisbane, Perth and Adelaide before the Australia-wide fallback while retaining the provider's Australian market/locale settings.

## Dashboard and campaign lists

- Replaces the narrow Apply Now / Needs Review / Information Only dashboard counters with Address Book, Facebook Pages and Applications & Outreaches. New Opportunities remains first and Errors · 24h remains last.
- Makes Campaigns and Templates use the same search width, toolbar geometry and card placement so switching tabs does not shift the list view.

## Release numbering

The next release is 0.11.97, followed by 0.11.98 and 0.11.99, including minor follow-up releases.
