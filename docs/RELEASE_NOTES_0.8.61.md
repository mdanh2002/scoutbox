# ScoutBox 0.8.61 release notes

Released on 2026-08-23 15:30:00.

ScoutBox 0.8.61 is a focused UI-alignment release with no database migration.

## Changes

- Candidate Profile Resume and Cover Letter tables now share fixed File / Added / action column widths so the two document sections align visually regardless of filename length.
- Dashboard host diagnostics no longer render a GPU row when the detected host operating system is macOS. Linux/other hosts retain the existing GPU label/utilization or Unavailable behavior.
- No telemetry, discovery, provider-routing, scheduler, storage or data-model behavior was changed.
