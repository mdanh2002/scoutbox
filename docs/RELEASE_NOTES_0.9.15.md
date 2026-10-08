# ScoutBox 0.9.15

## Short diagnostic export ranges

Maintenance → Export Diagnostic Data now includes Last 3 hours, Last 6 hours, and Last 12 hours in addition to the existing Last 24 hours and longer ranges.

The new ranges are enforced by the diagnostic export backend, so timestamped diagnostic records are filtered from the exact selected cutoff rather than the options being UI-only. Existing 24-hour, multi-day, and All available data behavior is unchanged.

No database migration is required.
