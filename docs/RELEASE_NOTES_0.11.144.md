# ScoutBox 0.11.144 — Resource Telemetry Continuity

## Fixed

- macOS GPU history no longer becomes `NULL` after only 30 seconds of transient host-probe failure.
- Last-good GPU utilization can be carried for a bounded 15-minute recovery window and is explicitly marked stale.
- ResourceSample records now persist GPU sample age, GPU telemetry state, and host-bridge age.
- Added ResourceHourly, a durable hourly CPU/RAM/GPU archive used as a long-range fallback when detailed rows are absent.
- Migration 0216 backfills ResourceHourly from all ResourceSample history still present during upgrade.
- Resource Usage shows hardware/GPU coverage and current GPU telemetry state.
- Telemetry sampler logs sustained GPU degradation rather than silently writing long runs of missing values.
- Upgrade smoke tests verify that ResourceSample and ResourceHourly are actually advancing; GPU freshness is reported as a non-fatal warning if unavailable.
- Diagnostic exports now include the hourly hardware archive and the new ResourceSample quality fields.

## Data integrity

The release does not fabricate missing historical GPU values. If older ResourceSample rows were already absent before the upgrade, that period remains a genuine historical gap. The new archive prevents future detailed-row loss from silently removing long-range hardware history.

## Retained fixes

0.11.143 restart recovery, 0.11.142 Facebook Page title wrapping, and 0.11.141 source-coverage / YC fixes remain included.
