# ScoutBox 0.9.30

## AI & Discovery test-state UI

- Restored Test Selection state icons for Local and Cloud Discovery model routes.
- Added Cloud stage-level test detail links using the same saved validation result as Local Discovery.
- Selection changes and Auto-detect invalidate stale test state immediately.
- Added compact `Last tested:` metadata below Discovery actions.
- Fixed the async status transition that could leave `Queueing test…` displayed after the queued job had already started.
- Active Cloud Test Selection jobs can resume polling after a page reload.

## Chatbot validation state

- Added a small test status icon to the right of the Primary and Secondary model dropdowns.
- Added compact Primary/Secondary last-tested timestamps below Chatbot actions.
- Chatbot test results are associated with the exact provider/model/lane and retained through AuditLog; no schema migration is needed.
- Provider/model changes and Auto-detect reset stale validation indicators to unknown until retested.

## Discovery label

- Changed the inline label to **Discovery Method:** with a smaller font while preserving the full-width selector and responsive routing layout.

No database migration is included in 0.9.30.
