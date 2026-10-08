# ScoutBox 0.10.42 release notes

ScoutBox 0.10.42 is a historical quality, filtering, diagnostics and UI-correctness release.

- Diagnostic export opens with both content groups selected while preserving the no-empty-selection guard.
- Facebook Pages to Watch receives a full historical validation path, system-slug rejection, clean-title normalization, strict Page identity/hiring evidence and explicit unavailable-validation semantics.
- Address Book re-evaluation protects manual/application-history contacts, performs a historical automatic-contact quality pass, retries missing Fit, and preserves review cases.
- Re-evaluation dialogs expose permanent **View Past Results** access.
- URL-health semantics remain job-aware only for Opportunities; Leads/Contacts use prominent page-unavailable evidence. Successful response byte counts are retained and HTTP tooltips show standard status text and useful byte size.
- HTML-to-LLM serialization suppresses giant parent duplicates, keeps logical rows/items together, bounds line length, and removes recommendation/navigation/footer boilerplate.
- Opportunity Advanced Filter adds cumulative Company Size and Company/Domain Age filters; Best Fit adds <100 employees and <5 years. Hidden Leads and Address Book add a compact company-size filter.
- Search Activity hides adapter bookkeeping rows with no useful query/URL while retaining telemetry. Campaign Run History removes only the visible Status column.
- Ask ScoutBox renders fenced Markdown/code correctly and uses Company Info in deterministic small-company opportunity selection.
- Company Info tooltips include the resolved company name. Post Age provenance is available for estimated values.

Migration `0093_v01042_quality_filters_health` stores useful response byte counts for URL-health tooltips.

Routine future releases increment the patch component of the 0.10.x line; see `RELEASE_POLICY.md`.
