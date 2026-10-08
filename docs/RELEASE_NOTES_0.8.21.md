# ScoutBox 0.8.21

## Search Sources
- Yandex, Baidu and Naver explicitly default to **Public Access** when no valid Access Type is stored.
- Migration `0018_v0821_access_defaults.py` normalizes existing blank/invalid selections without deleting credentials. Pre-access-type Naver credentials are copied into the legacy credential slot before Public Access becomes the selected default.
- Search Sources > Schedule no longer hides provider/request limits inside an Advanced limits disclosure. Every schedule/limit setting is on its own aligned row.
- Facebook configuration follows the same flat one-setting-per-row layout.
- Preferred Sources and Custom Domains explanatory copy is rendered as normal hint text beneath the controls.

## Opportunities and Market Studies
- Reverted the v0.8.20 latest-run-only list filter. Both pages now show the complete current, unsuppressed inventory again while preserving search, read-state filters, pagination and items-per-page controls.
- The latest completed scan/run remains available as a single details panel and as **Last Scan** metadata below the list. It no longer determines which records are visible.
- Market Studies no longer displays the old top-of-list `Autoscan last completed` line.

## Dashboard and About
- Recent activity and Diagnostics refresh icons were removed; a normal Dashboard reload is sufficient.
- Diagnostics is now a link to System > Configuration.
- The Errors metric card receives the same hover response as other metric cards.
- Activity state uses the same meaning in the Dashboard and top-right status icon: green for active work, amber when idle with a next run scheduled, and red when paused or when no scheduled campaign exists.
- About ScoutBox expands the What it does section and renders Useful starting points vertically.

## In-app confirmations
- Native JavaScript `alert()` / `confirm()` dialogs are removed from portal templates.
- Destructive row actions, bulk Delete Selected flows, profile/default rebuild prompts, maintenance operations, import confirmations and mail-draft actions now use ScoutBox in-app dialogs.
