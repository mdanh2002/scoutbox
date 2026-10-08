# ScoutBox 0.9.37

## Campaign Run History token totals

Campaign Run History now includes separate **Local tokens** and **Cloud tokens** columns. Each value sums input, output, and reasoning tokens recorded for that campaign/day and classifies the usage by the provider that actually handled the request. Exact totals remain available in the cell tooltip, while large values are compacted for readability. The Run History Excel export includes both totals as well.

## AI Requests malformed-response icon

Malformed responses now use a simple warning-triangle/exclamation icon rather than JSON-brace/X artwork. Status behavior is unchanged.

## Country flags

`GB`, `UK`, `U.K.`, `Great Britain`, and `Britain` now map to the United Kingdom flag in country displays.

No database migration is required. Existing `.env` values and Docker volumes can be retained; replace the application files and run `./restart_scout_box.sh`.
