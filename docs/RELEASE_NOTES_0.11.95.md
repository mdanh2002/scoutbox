# ScoutBox 0.11.95

## Startup migration hotfix

0.11.95 fixes the restart failure introduced by migration `0166_v01194_telemetry_ui_followups` in 0.11.94. The migration incorrectly queried and wrote a non-existent `AuditLog.detail` field. The historical `AuditLog` state at this point contains `summary`, `metadata`, and `version`, so 0166 now uses those fields and the established `version_upgraded` action used by surrounding releases.

The failed 0.11.94 migration did not complete, so upgrading to 0.11.95 safely retries the corrected 0166 migration and then applies 0167 to record the 0.11.95 upgrade. No application records or resource samples are rewritten by this hotfix.

## Release numbering

The next release is 0.11.96, followed by 0.11.97 and 0.11.98, including minor follow-up releases.
