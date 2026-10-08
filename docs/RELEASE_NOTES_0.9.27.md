# ScoutBox 0.9.27

## Discovery presentation and Auto-detect feedback

- Removed the verbose Cloud Web Auto-detect success explanation after defaults are applied.
- Removed the verbose Cloud Chatbot Auto-detect success explanation after defaults are applied.
- Discovery method is now an inline header beside the selector rather than a stacked label.
- The selector fills the remaining card width and aligns to the routing table's right edge.
- Removed the horizontal divider between the Discovery method selector and stage routing, retaining whitespace for separation.
- Added a model-level concentric chart under Token Providers. The outer ring shows total tokens by provider/model; the inner rings show input, output and reasoning-token distributions.
- Restyled the Provider / Tokens / Share table to use the same standard detailed-table presentation as Search Provider Performance.
- Token-provider/model telemetry updates with the existing live Resource Usage refresh and respects the selected date/provider filters.

No Discovery routing behavior, Gemini stage progression, provider model catalogue filtering, or database schema is changed in 0.9.27. The telemetry additions are presentation/aggregation changes over existing UsageMetric data and require no migration.
