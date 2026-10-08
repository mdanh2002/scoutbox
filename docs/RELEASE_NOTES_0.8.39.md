# ScoutBox 0.8.39 release notes

Released on 2026-08-21 01:45:00.

## Discovery controls

- Adds a visible **Discovery method** label above the Source-Guided / Cloud Web selector.
- During Test Model or Test Discovery, the Discovery method selector, all Primary/Fallback model selectors, and all input/output token-cap fields are not only disabled but visibly grayed out, making the locked state obvious.

## Dashboard

- Corrects alignment of the Errors · 24h exclamation icon so it aligns cleanly with the error count.

## Status notification

- When a campaign is active or is the next scheduled search, the campaign context is shown as a complete linked line, for example `Campaign: Emulation (created on 21 Aug 2026)`.
- The whole campaign context line links directly to that campaign.

## Campaign detail

- **Opportunities Found** now more closely mirrors the standalone Opportunities list, including Role / Company with country beneath it, Contact/URL, Status, Added, Applied Date, Source, Remote, Post Age and Fit.
- **Leads Found** now more closely mirrors the standalone Hidden Leads list, including Company with domain/country, Summary, Added, Source and Fit.
- Campaign lead names open the specific Hidden Lead detail directly; the separate website icon still opens the public target site.

## Campaign list

- Renames the visible **Last Run Duration** heading to **Run Duration** because the row already represents the campaign's latest run.
- The underlying duration calculation remains unchanged: end-to-end elapsed seconds from CampaignRun creation/queueing through completion.

## Database

- No new database migration is required for 0.8.39.
