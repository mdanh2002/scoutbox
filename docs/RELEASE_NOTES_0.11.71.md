# ScoutBox 0.11.71

- Renamed ToughDev Stats to External Statistics.
- Moved external statistics database access into the optional `stats_service` sidecar container.
- ScoutBox no longer connects directly to the external statistics database.
- Added safe dummy defaults for public distributions and kept the sidecar enabled by default on fresh installs.
- ScoutBox remains fully operational when the sidecar is unavailable; Config shows a concise non-fatal status message.
- Added a one-time upgrade handoff that writes existing connector credentials to the private `.scoutbox-runtime/external-stats.json` sidecar configuration and clears the legacy database-held credential fields after a successful handoff.
- The sidecar is internal-only and publishes no host port by default.
- Tracking Links and synchronized click history remain owned by ScoutBox.
