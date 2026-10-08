# ScoutBox 0.9.38

## Truncated structured responses

ScoutBox can now conservatively recover a useful final object when a provider truncates a JSON list in the middle of that object's last field. Only key/value pairs that were fully decoded before the cut are retained; the unfinished field is discarded and no value is invented. At least three complete fields are required before a partial final object is accepted. The corrected payload is validated before Discovery can consume it and is logged as **Recovered response**. The original provider output remains available in `raw_output_text` for diagnostics.

This extends the existing recovery behavior for complete leading list items. Responses that cannot be converted into valid JSON without guessing remain **Malformed response** and continue through retry/failover.

## Campaign Run History

The separate **Run context** column has been removed. Its compact context note now appears as the final, smaller line inside **Execution**, keeping the table narrower without losing the information. The **Status** column now uses compact semantic icons; the exact status remains available as a tooltip and accessible label. Run History Excel export likewise folds run context into its **Execution** field.

No database migration is required for 0.9.38.
