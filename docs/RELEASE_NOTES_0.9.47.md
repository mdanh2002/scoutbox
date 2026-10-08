# ScoutBox 0.9.47

## Resource Usage model picker

- Replaced the Select all action button with a checkbox aligned with the model checkbox list. It acts as a true select-all / clear-all toggle and shows an indeterminate state for partial selections.
- Added a centered `N of M selected` counter to the picker header.
- Added a provider shortcut dropdown on the right. It offers providers represented by the current model data in the order Gemini, Ollama, OpenAI, OpenRouter and selects only that provider's models without applying the chart change automatically.
- Model checkbox rows are sorted alphabetically by model name, with provider used only as a tie-breaker.
- Apply gains the primary/highlight treatment whenever the pending checkbox state differs from the filter currently applied to the Token Usage chart.
- Pending edits are now maintained separately from the applied chart filter, so the 15-second telemetry refresh no longer rebuilds the menu from the old applied state and re-checks boxes the user just changed.
- The existing at-least-two-model Apply guard is retained.

No token accounting, provider routing, Opportunity behavior, or database schema changes are included in this release.
