# ScoutBox 0.8.42 release notes

ScoutBox 0.8.42 is a focused refinement of 0.8.41. All 0.8.41 behavior remains unchanged except for the AI & Discovery testing changes below.

## Test Selection now saves first

- **Test Selection** no longer validates a browser-only routing snapshot that could disagree with the saved configuration after navigation.
- When confirmed, ScoutBox first saves the currently displayed Primary, Fallback, input-cap and output-cap selections using the same persisted pipeline-routing structure used by campaigns.
- It then queues the selection test against that saved configuration.
- The confirmation dialog explicitly states that the current selections will be saved before testing.
- In Cloud Web mode, the managed URL-discovery route remains preserved rather than being overwritten by disabled browser controls.
- Auto Select / Optimize for Local / Optimize for Cloud still remain preview-only until either **Save** or **Test Selection** is used. Using Test Selection is therefore an intentional save-and-test action.

## Search-engine selection for Test Discovery

- Source-Guided **Test Discovery** now includes a Search engine dropdown.
- Only enabled search engines that are actually configured for API or usable public search are included; unconfigured engines are excluded.
- Every option includes a compact health marker and the provider's request/result totals for the latest seven days, for example `✓ Google (100 requests, 10 results)`.
- Status markers represent healthy recent results, warning/error-heavy activity, or no recent results.
- The default selection is the configured provider with the most recent successful result during the recent-statistics window. If none has recent results, ScoutBox falls back to the strongest available configured provider.
- Test Discovery runs only against the explicitly selected engine instead of allowing provider rotation to choose a known-bad engine.
- The selected engine is stored in the diagnostic result and shown in Discovery Summary.
- Cloud Web Discovery continues to use its cloud web-search path and does not offer ordinary Search Source selection.

## Compatibility

- No database migration is required for 0.8.42. Migration `0030_v0838_hidden_lead_company_info.py` remains the latest schema migration.
- Existing `.env`, PostgreSQL data, Redis data, media, credentials and encryption keys are preserved during a normal upgrade.
