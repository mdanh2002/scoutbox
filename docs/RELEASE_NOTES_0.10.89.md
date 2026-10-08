# ScoutBox 0.10.89 Release Notes

## Blacklist review domain display

- The Opportunity and Hidden Lead blacklist review dialogs now choose a company-domain review value from stored company research and domain-age evidence before using the raw listing URL.
- This allows genuine company domains already visible elsewhere in the list, such as `density.io` for `Density AI`, to appear in the popup.
- Job boards, ATS hosts, aggregators, and their subdomains remain hidden and are never submitted to the blacklist action.
- The backend continues to create company-name-only blacklist rules for Opportunity and Hidden Lead bulk actions.

## Cleaner blacklist UI

- Empty domain cells in blacklist review dialogs are now simply blank.
- The Blacklist page no longer shows the `No domain` placeholder or the `Company-name-only match` hint for label-only entries.

## Hidden Lead detail

- Removed the `Open Lead` action button from the Hidden Lead detail action bar to keep lead-detail actions focused and avoid another competing action surface.

## Search Activity sizing

- The Search Activity query column now has a practical minimum width and clamps long queries to two wrapped lines.
- Results, Latency, and Size columns keep explicit compact widths while the table avoids a constant horizontal scrollbar at normal screen widths.

## Version metadata

- `VERSION`: `0.10.89`
- `RELEASE_ID`: `ScoutBox v0.10.89`
- `BUILD_INFO.txt`: `ScoutBox v0.10.89`
