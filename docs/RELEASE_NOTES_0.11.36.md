# ScoutBox 0.11.36 Release Notes

## Fixed

- Search Activity Outcomes is now searchable and Apply-first, matching the provider filters.
- AI Requests Runtime, Provider, and Status filters are now searchable Apply-first multi-select dropdowns.
- Audit Trail Actions, Blacklist Scopes, and Recycle Bin Types are now searchable Apply-first multi-select dropdowns.
- Closing these dropdowns without Apply reverts uncommitted checkbox changes, avoiding accidental list refreshes while choosing several entries.

## Added

- Statistics now includes a large offline SVG world map at the end of the page.
- The map plots Opportunities, Hidden Leads, Address Book entries, Applications, and Blacklist coverage with separate icons.
- The map includes top-right show/hide layer checkboxes and bottom-right zoom controls from 25% to 100%.
- The world map uses bundled SVG/static coordinate data only; no external map services are called.

## Validation

- `scripts/regression_v01136.py`
- `verify_release.sh`
- Python AST parse and compile
- Docker Compose YAML parse
- Shell syntax checks
