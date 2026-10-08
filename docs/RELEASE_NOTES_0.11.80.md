# ScoutBox 0.11.80

## Market Coverage

- Adds a Market Coverage card immediately below Discovery Performance in Resource Usage.
- Shows executed request counts by search language on the outer ring and Discovery Market on the inner ring.
- Uses the selected Resource Usage period and refreshes with the existing 15-second telemetry update.
- Includes separate language and market legends, hover details, exact request shares, and an Excel legend export.

## Search Activity

- Removes the Date Range controls and their server-side filtering from Search Activity.
- Adds a searchable, checkbox-based Search Regions filter after Providers and before Outcomes.
- Filters on the exact recorded regional setting, including values such as `wt-wt`, `en-IN`, and `kr-kr`.
- Region counts are faceted against the active provider type, provider, outcome, and text filters.

## Local-language discovery

- Removes the local-language enable checkbox from Discovery Markets.
- Makes bounded local-language exploration always active for enabled markets and saved additional languages.
- Retains Exploration strength as the request cap: Low 1, Balanced 2, and High 4 supplemental assignments per run.
- Migrates existing installations to the always-enabled state while retaining the legacy database field for compatibility.
