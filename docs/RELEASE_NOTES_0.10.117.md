# ScoutBox 0.10.117

## Fixed

- Improved Focus label quality by using Local AI to propose labels and evidence dynamically during taxonomy rebuilds.
- Removed forced coverage passes that over-classified weak Hidden Leads and Address Book rows.
- Added generic malformed-label guards for verb-fragment labels such as labels beginning with “Develops”, “Offers”, “Provides”, or “Specializes”.
- Required each row to support its assigned label using the label's own distinctive terms instead of hard-coded per-group keyword prerequisites.
- Queued the 0.10.117 Focus repair as a Dashboard Activity background job after web health is up.
- Updated Focus assignment metadata to write release 0.10.117.

## Startup safety

Migrations remain database-only. The 0.10.117 migration only marks Focus repair pending and stops stale Focus jobs.
