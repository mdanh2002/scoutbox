# ScoutBox 0.11.5

Source-readonly location-field hotfix.

## Fixed

- Opportunity detail no longer renders Job Country as an editable country dropdown.
- Hidden Lead and Address Book location fields are rendered as source-derived read-only text instead of editable country controls.
- Jobicy `Remote from: Europe` is preferred over JobPosting structured country arrays that expand Europe into individual countries.
- Legacy structured country arrays are suppressed from Opportunity location display/filter helpers when they would expose bogus country lists such as Albania/Andorra/Austria/Belarus.
- Country filters no longer match malformed raw JSON role-location values while the post-health repair is pending.
- Adds post-health Dashboard Activity repair: `Rebuild source-readonly location fields for 0.11.5`.

## Startup safety

Migration 0143 is database-only. It only marks the repair pending and never fetches pages, calls Local AI, or runs bulk repairs before web health.
