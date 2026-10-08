# ScoutBox 0.10.54 release notes

ScoutBox 0.10.54 is a focused display/data-repair release over 0.10.53.

## Fixed
- Raw JSON-LD/applicantLocationRequirements blobs no longer appear in Opportunity role/location rows.
- Existing JSON-shaped `Opportunity.role_location` values are cleaned by migration `0099_v01054_role_location_json_cleanup.py`.
- Template rendering now uses a safe role-location display filter wherever list/detail views show role location.
- Future extraction avoids saving large multi-country eligibility lists as role location text.

Routine future releases increment the patch component.
