# ScoutBox 0.8.91

Maintenance/UI correction release on top of 0.8.90.

- Fixes Configuration > Maintenance visibility for **Rebuild Missing AI Data** by passing an explicit fresh Cloud Web availability flag to the template. The action is shown only when Discovery Method is `cloud_web`; the backend continues to enforce the same rule.
- Extends **Rebuild Missing AI Data** to repair missing Company Location in addition to Company Info, Remote Status, Post Age and Fit. Existing populated values are preserved, and company research side effects are restored when the corresponding field was not a rebuild target.
- Restores the normal low/unavailable-confidence colour for the literal `?` Fit indicator.
- Cleans up About ScoutBox > Overall System Architecture: adds heading top/left spacing and divider, removes the redundant flow subtitle/description, removes the standalone Usage / AI Requests / Diagnostics / Resource Telemetry box, and tightens the SVG height.

No database migration is required.
