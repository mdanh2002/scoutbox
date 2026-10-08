# ScoutBox 0.8.32 release notes

ScoutBox 0.8.32 is a reliability and UI-maintenance release built on 0.8.31. It addresses the follow-up issues found in daily use, especially AI Requests readability, campaign list density, country editing, public Google search behavior, noisy multi-job aggregators, background-company-research visibility, and discovery items that reappeared after users deleted them.

## AI Requests

The AI Requests table now has explicit independent columns for **Input**, **Output**, **Input Tokens**, **Output Tokens**, and a new final **Attachments** column. The input/output preview cells remain table cells instead of using a display mode that could break column geometry, which prevents the header/body drift and the apparent merged Input/Output columns. Zero output tokens render as `0` rather than looking blank.

Related-record hints are more compact. Opportunity-linked requests use a format such as `Opportunity 368: 1,000+ Embedded Developer Jobs in United States`. Generic internal task hints such as `freshness task`, `first_filter task`, and `page_summarization task` are not shown underneath the task name.

The request-detail popup continues to show Input and Output token counts directly below their corresponding bodies.

## Campaign list

The Campaign list removes the separate **Created**, **Updated**, and **Next Run** columns. Created/Updated are combined into a single **Changed** column showing whichever timestamp is newer. **Last Run** remains separate.

For an enabled campaign that is currently scheduled, the next scheduled run is shown inside the **Status** cell. Running, queued, paused, and stopping campaigns do not waste a separate column on Next Run.

## Country editing

Country flag coverage now includes the display aliases used by ScoutBox, including Cape Verde, Democratic Republic of the Congo, Ivory Coast, Micronesia, Republic of the Congo, Turkey, and Vatican City. `Remote worldwide` uses a world marker rather than appearing as a country with a missing icon.

Country selects marked as ScoutBox country pickers are enhanced into compact searchable dropdowns. Typing filters the list, the popup height is capped to avoid an excessively tall menu, keyboard navigation is supported, and selecting a country continues to dispatch the normal change event used by autosave/detail forms.

## Email editor

The formatting toolbar is forced hidden whenever the composer is in plain-text mode. In HTML mode, Bold, Italic, Underline, List, and Link buttons now reflect the formatting state at the current cursor/selection position. Switching HTML to plain text still prompts before formatting is discarded, and spellcheck remains enabled in both modes.

## Notifications and Candidate Profile

The top-right Opportunity/Hidden Lead popup adds an age beside each item: minutes or hours for recent items, `yesterday`, a day count through seven days, and a raw date for older items.

Candidate Profile now has **Save profile** in the top-right page header. The duplicate bottom Save button is removed so a long profile can be saved without scrolling to the end; the Defaults action remains in the profile body.

## Hidden Leads list

The company/domain cell uses a normal table cell with an internal centered layout. This removes the short stray separator beneath the domain and keeps the company name plus domain vertically centered with the external-open control.

## Token categories

The `Question Answers` token category is shortened to **Q/A** in usage breakdowns.

## Google public search

The Google public-search adapter now explicitly detects the enable-JavaScript/interstitial response that can redirect to URLs such as `localhost:8989/httpservice/retry/enablejs`. Those pages are never accepted or parsed as search results.

When the first public Google request returns an interstitial or no usable web results, ScoutBox retries a small set of basic-HTML/browser-compatible Google request variants with a normal browser User-Agent. Redirect/interstitial URLs are filtered from parsed results. If all public variants fail, ScoutBox records a clean provider error rather than feeding the retry page into discovery. Google Programmable Search credentials remain the most reliable API path when configured.

## Multi-job aggregators

Collection-page detection now understands thousands separators and `+` counts. Titles such as `1,000+ Embedded Developer Jobs in United States` are classified as job collections rather than single opportunities. Flexible/remote job-list titles and pages with many repeated apply/job-role signals are also treated as collections.

Aggregator/list pages remain discovery pointers: ScoutBox expands supported pages into individual role URLs and analyzes those child roles. Collection pages that survive fetch are rejected before persistence. The upgrade migration also suppresses obvious legacy opportunities whose titles begin with a large job count followed by a jobs collection title, cleaning existing `1,000+ … Jobs` noise from normal Opportunity views.

## Permanent user-deletion tombstones

Deleting an Opportunity or Hidden Lead from the UI is now a soft deletion. The record is hidden from user-facing inventories, unread counts, campaign lists, dashboard Opportunity lists, application/statistics views, and activity links, but remains in the database as a tombstone.

Future discovery checks these tombstones before creating or updating a result. Opportunities are compared by canonical URL and by close title/company/content similarity; Hidden Leads are compared by domain and normalized company-name similarity. The normal Hidden Leads scanner and campaign-lead capture both honor deleted lead tombstones. This prevents previously removed noise from being rediscovered simply because a URL, company name, or title changed slightly.
 Deleted records are also excluded from Dashboard counters/activity charts, Statistics, Ask ScoutBox opportunity/application context, tracking-link application choices, and the daily digest so they do not leak back into user-facing activity after removal.

Migration `0027_v0832_deleted_tombstones.py` adds `user_deleted` and `deleted_at` fields to Opportunities and Company Leads and performs the legacy aggregate-title cleanup.

## Company research activity

Queued/running company-research jobs are explicitly prioritized in Dashboard/ScoutBox Activity rather than competing only for the generic background-job row limit. As a result, when Company Info reports that public company information is being collected, the corresponding pending company-research activity is visible on Dashboard.

## Search Activity and navigation

Search Activity no longer enforces a minimum table width larger than its container. Its fixed utility columns are slightly narrower and the Query column receives the remaining space, removing the small horizontal scrollbar seen at normal desktop widths.

The left sidebar container no longer scrolls as one block. The navigation section scrolls independently, while the ScoutBox logo/header stays fixed at the top and the copyright/footer stays fixed at the bottom.

## Verification

ScoutBox 0.8.32 retains the existing 0.8.28–0.8.31 targeted regression suites and adds `scripts/regression_v0832.py`. The new checks cover AI Request column geometry/attachments/hints, campaign timestamp compaction, country flag aliases and searchable dropdowns, HTML toolbar mode/state, notification ages, Candidate Profile save placement, Hidden Lead cell layout, Q/A terminology, Google interstitial retries, `1,000+ … Jobs` collection detection, deletion tombstones, company-research activity priority, Search Activity overflow, and independent sidebar scrolling.
