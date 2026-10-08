# ScoutBox 0.11.137 Release Notes

## SearchAPI configuration

- SearchAPI service checkboxes now use a responsive column grid; long labels wrap within their own column.
- The SearchAPI status badge moved beside the API-key field.
- “Save” is renamed to “Save API key”.
- Saving performs a lightweight SearchAPI credential sanity check without creating ordinary Search Activity or AI Request telemetry.
- Invalid or temporarily unverifiable keys may still be saved and are shown with an amber warning state.
- Removed the decorative horizontal divider above Test Search.
- Removed the AI-research preference hint from the dialog.

## Test Search

- SearchAPI test result cards strip HTML and show compact previews rather than full descriptions.
- Job results show concise title, company/location metadata, URL, and a short snippet when available.
- Long AI research answers are bounded in the modal.

## AI research limits

- ChatGPT Research automatic default: 100/day.
- Google AI Mode automatic default: 100/day.
- Both remain subordinate to the shared SearchAPI daily limit and existing strategic routing.

## Search Activity

- Provider and query cells are vertically centered with Results, Latency, Size and Time.
- Multi-line SearchAPI provider/locale metadata stays centered as a unit.

## Preserved behavior

SearchAPI no-key preflight, shared quota accounting, SearchAPI ChatGPT Cloud Runtime logging, Google Jobs/Web/Forums/News/AI Mode/Local support, worldwide coverage, community hiring signals, multilingual discovery, quota pressure colors and prior re-evaluation safeguards are retained.
