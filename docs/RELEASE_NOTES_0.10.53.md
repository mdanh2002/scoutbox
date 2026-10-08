# ScoutBox 0.10.53 release notes

ScoutBox 0.10.53 is a focused two-fix release over 0.10.52.

## Fixed

- Suppresses raw JSON-LD country/location blobs in Opportunity, Hidden Lead and Address Book list rows.
- Cleans structured country values at ingestion/enrichment time, accepting one explicit country only when unambiguous.
- Repairs existing JSON-shaped country/location values with migration `0098_v01053_country_telemetry_display.py`.
- Adds a right-aligned resource sample capture timestamp to the CPU/RAM/GPU/Requests/Tokens/Disk metric line on the telemetry page.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application package, run migrations, then restart ScoutBox.

Routine future releases increment the patch component of the 0.10.x line; see `RELEASE_POLICY.md`.
