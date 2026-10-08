# ScoutBox 0.8.2 release notes

0.8.2 is a site-wide usability, asynchronous-workflow, content-quality and telemetry release designed to upgrade in place from 0.8.1 while preserving `.env`, credentials and Docker volumes.

## Highlights

- Fixed tab switching across shared tabbed pages and preserved sidebar scroll position while moving through left-navigation items.
- Rebalanced major pages around full-width sections, compact list toolbars, search-as-you-type, sortable columns, pagination and items-per-page controls.
- Moved Quick Start and Diagnostics into Dashboard; added live work status, actionable counters, discovery chart and Added timestamps.
- Cleaned Opportunity list/detail presentation, normalized literal placeholder values, added a strict actionable-role gate, sanitized rich job/lead rendering, top actions, Post Age evidence, Company Info and translation support.
- Added non-role/documentation filtering so manuals, product pages and generic technical pages are not promoted as ordinary Opportunities merely because query terms match.
- Reworked Cold Contact / Hidden Market to search all enabled providers for signals of relevant technical work, not only explicit recruiting text; scans and outreach generation run asynchronously.
- Added adaptive automatic discovery rotations inside each configured search window with error-aware backoff.
- Improved Search Sources provider configuration/test flows and public-fallback visibility.
- Made major AI/network/document workflows background jobs, including Performance Lab and opportunity preparation/enrichment paths.
- Unified Email History around Incoming IMAP and Outgoing SMTP records with full body retrieval/rendering, delivery state, warnings, search/paging and XLSX export.
- Added CPU, memory and GPU resource sampling to Usage & Telemetry with historical charts and request/error drill-downs.
- Improved address-book inference/filtering and source linking; generic sales/no-reply addresses are suppressed.
- Fixed ToughDev tracking suffix generation so an article slug is not repeated as its own suffix.
- Refined campaign criteria inputs, query rotation layout, scope compensation preferences and shared country token controls.
- Reduced low-value explanatory copy and kept configuration links/status close to the controls they describe.

## Upgrade

Keep the existing `.env` and Docker volumes, replace application files, then run:

```bash
./restart_scout_box.sh
```

Do not run `initial_setup_macos.sh` for an existing installation.

Migration `0004_v082_ui_mail_resources` is additive and also cleans legacy literal placeholder values such as `blank` without deleting opportunities.
