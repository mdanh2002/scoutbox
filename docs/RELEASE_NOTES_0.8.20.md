# ScoutBox 0.8.20

## Search provider access
- Added per-provider **Access Type** selection in Search Sources.
- Yandex: Public search, Yandex Search API with service-account API key, or Yandex Cloud / AI Studio IAM token; API modes require a Yandex Cloud folder ID.
- Baidu: Public search or Baidu Qianfan Web Search API using an API key.
- Naver: Public search, legacy NAVER Developers Center API, or NAVER API HUB.
- Existing legacy Naver credentials remain backward-compatible after upgrade.
- UI-saved credentials are encrypted and take effect on the next search without a restart. Environment variables remain supported as deployment fallbacks.

## Search result URL correctness
- Search-engine redirect/tracking URLs are unwrapped before discovery.
- Unresolved search-engine URLs are rejected before Opportunity or Market Studies persistence.
- Upgrade cleanup repairs existing Bing/Yahoo-style wrapped links where a destination can be recovered and suppresses/removes records that have no valid external target.

## Market Studies
- The results table now represents only the latest completed Market Studies scan, while retaining server-side pagination and items-per-page controls.
- A useful deterministic lead rationale is displayed immediately. AI refinement runs asynchronously and is indicated by a small clock icon with tooltip.
- AI failure no longer leaves a permanent `Summary pending` row: the preliminary rationale remains available.
- Summary generation now focuses on why the company was selected, what it builds/offers (including products when evidenced), and a practical embedded/low-level engineering outreach angle.
- Forum, support, community and documentation paths are rejected more aggressively.
- `arm.com` and `kernel.org` are built-in blacklist entries for Market Studies.

## Opportunities
- Opportunity lists now show results belonging to the latest completed campaign scan, with existing pagination/items-per-page controls retained.
- Latest scan metadata is shown below the list.

## Telemetry
- Token Categories and Search Provider Performance charts now use the same analytical-column width and X position.
- Provider legend/copy alignment is preserved with the Token Categories table column.
