# ScoutBox 0.11.83

## Resource Usage

- Restores Discovery Performance and Market Coverage as separate peer cards, matching Token Usage.
- Moves the performance table into its own **Discovery Performance Details** card after Market Coverage.
- Removes the dark background behind the Discovery Performance ring explanation.
- Places market flags after country names in the Market Coverage legend.

## Search Activity

- Rebuilds the footer as a single three-part row: rows/export on the left, date controls in the center, and pagination on the right.
- Preserves that arrangement after asynchronous filtering and pagination updates.
- Wraps long provider names inside the Provider cell so they cannot overlap the Query column.

## Diagnostic export

- Uses the compact `Preparing…` button label while the background archive job is running.
- Adds a continuously spinning status indicator to the right of the label.
- Keeps detailed preparation stages available as the button tooltip without changing its width or height.

## About ScoutBox

- Adds a new abacus-style `external_statistics` SVG and uses it only for External Statistics.
- The icon is original to this section and contains no arrow motif.

No discovery, telemetry calculation, filtering, export-content, or scheduling behavior is changed.
