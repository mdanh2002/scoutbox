# ScoutBox 0.8.59 release notes

ScoutBox 0.8.59 is a no-migration Maintenance/export feedback and Email History presentation release.

## Changes

- Configure → Maintenance now says **For Destructive actions, continue only if the affected records are no longer needed.**, so the adjacent diagnostic export is not implied to be destructive.
- Diagnostic export still closes its dialog immediately and remains browser-managed. While the server prepares the ZIP, the Maintenance export action reads **Downloading Export ...** and all Maintenance action buttons are disabled. A short-lived non-sensitive response cookie re-enables them as soon as the attachment response reaches the browser; no archive data is fetched through JavaScript.
- Candidate Profile removes the redundant **Priority guidance** heading while preserving the High priority, Medium priority, and Low priority / good to have fields and their stored values.
- Email History outgoing rows display only **Sent** or **Failed**, using check/cross icons. IMAP-observed-sent details, SMTP delivery state, and failure text are retained in tooltips rather than exposed as awkward status labels. The message-detail status is normalized the same way.

No database migration, new telemetry, provider-routing change, discovery scheduling change, or other unrelated system behavior is included.
