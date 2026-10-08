# ScoutBox 0.10.84

ScoutBox 0.10.84 is a stability and list-management release focused on keeping discovery throughput high while improving day-to-day list handling.

## Fixed

- Company Enrichment and passive company research no longer overwrite the visible progress of the originating CampaignRun or make campaigns appear stalled at `company_enrichment`.
- Company research waits only briefly for the shared local AI generation lane and then degrades safely, rather than holding up campaign discovery.
- The General settings screen now exposes `Max concurrent campaigns` with a default of 5, minimum 2 and maximum 10. Automatic campaign scheduling uses this setting instead of local-generation-lane limits.
- Opportunity, Hidden Leads and Address Book lists refresh automatically when their new/unread badge count increases while the user is already on the page. Refresh is skipped while the user is editing, has a modal open, or has selected rows.
- Sort icons are kept inside their own table header cells site-wide, fixing the Opportunity `Company Info`/`Remote` overlap.
- Opportunity table summary width is less aggressive so horizontal scrolling appears only on genuinely narrow windows.
- The Opportunity toolbar now includes a blacklist button before Delete, matching Hidden Leads.
- Blacklist entries can now be company-name-only rules with a blank Domain. Domainless rules require a normalized Company Name of at least 7 characters and match company names exactly after trim/case-folding.
- Blacklist terminology now shows `Company Name` instead of `Label` in the user interface while preserving the existing database column for compatibility.

## Upgrade notes

- No manual data cleanup is required. Existing blacklist domain rules continue to work unchanged.
- Domainless blacklist rules are intentionally exact-match only to avoid suppressing unrelated companies.
