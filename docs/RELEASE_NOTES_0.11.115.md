# ScoutBox 0.11.115

- Shortens Local AI **Company career pages** provider queries at the source instead of only shortening their display.
- Each company-finding query now uses one rotating role/job-title alias, at most one concise technical term, the target market/location, and one hiring intent.
- Role aliases rotate across runs and across providers, so fixed labels such as **legacy systems specialist** no longer dominate every search.
- Company-specific follow-up searches use the same concise pattern: `site:domain`, one rotating role alias, at most one technical term, and one hiring intent.
- Removes the previous seed pattern that joined two role titles with `hiring company careers "join our team"`.
- Preserves all Statistics, Tracking Links, resource-chart, date-filter, discovery filtering, and provider-localization behavior from 0.11.114.

No schema change is included; migration 0187 records the release upgrade only.

Next release: 0.11.116.
