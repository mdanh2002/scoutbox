# ScoutBox 0.8.106

## Company Info consistency

- Fixed the Company Info list badge in Hidden Leads and Address Book so it follows the same age/size semantics as Opportunities.
- Removed the generic building/Profile fallback from list rows. General company research remains available in detail views, but a list row with no company age, domain-registration age, or employee size now shows `?`.
- Profile-only Company Info is no longer treated as a completed Company Info lifecycle result. ScoutBox can therefore run its existing recovery path to obtain founding year, approximate size, or domain-registration age when the company itself does not expose an establishment year.
- Address Book rows now inherit richer retained Company Info from a matching Opportunity or Hidden Lead even when the contact already contains older general company facts.

## Domain-age and retained-data repair

- Company Info normalization now preserves `domain_registered_at`, `domain_age_years`, `domain_age_label`, and `domain_age_domain` rather than rebuilding the structured payload and dropping them.
- Company research now returns and caches the final post-domain-fallback payload, so downstream Hidden Leads and Address Book contacts can reuse domain-age evidence.
- Migration `0066_v08106_company_info_badge_repair` normalizes retained founding/size/domain-age data, copies the strongest matching retained Company Info payload by company/domain, and marks remaining complete-but-profile-only records for refresh. The migration makes no web or AI calls.
- Startup queues a one-time `0.8.106 Company Info backfill`. It reuses existing Opportunity/Lead research first and only researches unresolved records; in Local Discovery mode it waits/pauses while campaigns are active.

## Expected list behavior

- Founding age and/or employee size available: show the detailed maturity/size building indicator.
- Only domain-registration age available: show the domain-age globe indicator and age.
- Neither age nor size available: show `?`.
