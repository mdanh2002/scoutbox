# ScoutBox 0.11.73

## About ScoutBox — External Statistics reference

- Adds an **External Statistics** learning/reference section directly below Redis usage in About ScoutBox.
- Documents the generic sidecar contract (`/health`, `/test`, `/sync`), normalized tracking fields, and how ScoutBox communicates with an optional statistics container.
- Explains how to implement a replacement sidecar using any private database, API, or log source without exposing its schema to ScoutBox.
- Documents `EXTERNAL_STATS_URL` and Config → External Statistics as the integration points.
- Uses generic field names only; no private/internal statistics database schema is documented.
