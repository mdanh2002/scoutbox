# ScoutBox 0.8.33 release notes

ScoutBox 0.8.33 is a focused reliability and workflow release built on 0.8.32. It addresses AI-request readability and token accounting, sortable diagnostics, HTML-to-plain-text email fidelity, credential-free Google public search, deletion/restore behavior, and the top-bar recent-item menu.

## AI Requests

The AI Requests list now uses six visible columns: **Date**, **Task / Related**, **Runtime / Model**, **Input**, **Output**, and **Attachments**. The standalone Input Tokens and Output Tokens columns have been removed. Token totals are shown compactly beneath the provider/model in Runtime / Model, while the full request popup still shows the individual input and output totals beside their bodies.

Input and Output previews are capped and visually clamped to three lines so one long prompt or response cannot expand an entire table row. The full text remains available in the request-detail popup. All six visible columns are sortable in either direction, and sort state is preserved by pagination and export links.

Some providers and local runtimes return a zero or omit usage counters even when they generated text. AI request logging now falls back to ScoutBox's provider-neutral rough token estimator whenever an exact input/output counter is absent or reports zero for non-empty text, preventing useful output-token data from appearing missing.

## Search Activity

Every Search Activity column is now sortable: **Date**, **Provider**, **Query**, **Result**, **Latency**, and **Downloaded**. Sorting is performed server-side and composes with the current text/provider/outcome filters, row count, pagination, and XLSX export.

## Email HTML-to-text conversion

Converting an HTML email to plain text now keeps meaningful line boundaries. `<br>` produces a newline; paragraphs, divisions, blockquotes, headings, preformatted blocks, and table rows produce block breaks; list items keep a simple `- ` prefix and their own line. Both the browser editor conversion and mailbox-side conversion use the same intent, so paragraph and list structure is no longer flattened when formatting is discarded.

## Google public search

Google public search no longer treats Programmable Search credentials as a prerequisite for a usable source. When API credentials are not configured, ScoutBox tries several no-JavaScript/basic-HTML variants using desktop and Android browser signatures, including `gbv=1`, `nojs=1`, `udm=14`, Firefox/Opera/Android client variants, and an alternate Google regional host.

The parser now handles additional classic/mobile result wrappers and can fall back to external result anchors when Google's wrapper classes change. Enable-JavaScript, localhost retry, unusual-traffic, and `/sorry/` interstitials are still rejected as non-results. If Google blocks every public variant for one request, the error now describes the public-page block and later retry behavior instead of instructing the user to configure Programmable Search credentials.

## Recycle Bin

System now includes **Recycle Bin**. It intentionally stays simple: **Date Deleted**, **Item Title**, **Item Type**, and **Restore**, plus an **Empty Recycle Bin** action.

Campaigns, Opportunities, Applications, and Outreach records move to the Recycle Bin instead of being immediately destroyed. Restored campaigns return paused. Restoring an Opportunity makes it visible/searchable in ScoutBox again; when its attached Application/Outreach was recycled at the same time, that paired record is restored with it. Restoring an Application/Outreach also restores a recycled parent Opportunity so the record is usable immediately.

A recycled Opportunity continues to block matching rediscovery while it remains in the Recycle Bin. Emptying the Recycle Bin physically removes recycled records. After the Opportunity record is permanently removed, a later campaign is allowed to discover the same opportunity again. This replaces the previous permanent deletion-marker behavior with a user-visible lifecycle.

Campaign schedulers, campaign lists, Ask ScoutBox campaign context, Applications & Outreach, analytics, unread counts, mailbox matching, and tracking-link application choices now ignore recycled records where appropriate.

## Hidden Leads deletion

Hidden Leads are no longer retained as permanent deleted records. Deleting a Hidden Lead physically removes it, and discovery no longer checks deleted-lead similarity records. The migration removes legacy v0.8.32 deleted Hidden Lead rows so those companies may be discovered again in a future scan.

## Recent Opportunities / Recent Leads menu

The top-right recent-item popover is now split into two explicit groups with a divider: **Recent Opportunities** first and **Recent Leads** second. Hidden Lead rows append a compact three-to-four-word evidence-derived hint so company-only rows do not look abnormally short. The helper removes the misleading phrase `other projects` and falls back to a small technical-work description when the saved evidence is too weak to produce a useful hint.

## Migration

Migration `0028_v0833_recycle_bin.py` adds `deleted_at` to Campaign and Application, adds an index to Opportunity `deleted_at`, updates deletion-field descriptions for the Recycle Bin lifecycle, and removes legacy deleted Hidden Lead rows.

## Verification

The 0.8.33 regression suite checks release identity, Python/template syntax, AI Request token placement and clamping, sortable AI/Search columns, token fallback, HTML line preservation, Google public-search variants/parsing/error copy, Recycle Bin model/view/navigation/restore/empty behavior, campaign scheduler filtering, active Application filtering, normal Hidden Lead deletion, Recycle Bin-only opportunity rediscovery suppression, and the split recent-item popover.
