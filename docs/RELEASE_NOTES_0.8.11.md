# ScoutBox 0.8.11 release notes

ScoutBox 0.8.11 is a reliability and usability update based on the verified 0.8.10 package.

## Read state and blacklist

- Opportunity and Market Studies bulk Mark as Read / Mark as Unread now resolve selected rows directly from the grid controls rather than relying on DOM nesting.
- Row interactions persist read state through the dedicated endpoint and a session-side reconciliation marker prevents browser Back/Forward cache from restoring stale bold styling after an item was viewed.
- Blacklist Edit now contains only Domain/URL, Label and Reason. There is no Blocked checkbox in the editor.
- Delete Selected removes blacklist rows; Reset to Defaults remains the way to restore built-in entries.
- Configured search providers with no requests today use a distinct blue square information indicator, separate from yellow elevated-error and no-result states.

## Application draft saving

- The email-editor save icon commits ScoutBox fields immediately through an asynchronous UI request.
- IMAP Drafts persistence is queued as a background job, so slow IMAP operations do not block the editor or force a page navigation.
- The editor reports background IMAP save progress and failure without reloading the page.

## Resource Usage and Statistics

- Today/Week/Month/All/custom range controls on Resource Usage and Statistics are sticky so the active time scope remains visible while scrolling.
- Input-token purpose analysis now has its own table and donut chart with raw token counts and percentages, plus a working purpose breakdown when hovering/focusing the Input Tokens metric.
- CPU/Memory/GPU/request benchmarking remains a thin-line chart with raw hover values.
- Statistics is kept focused on opportunity/application outcomes; Pages scraped, Tokens consumed and Data downloaded were removed from its metric strip because they belong to Resource Usage.

## Candidate Profile and ranking

- CV concepts and Likely roles are editable token lists with trimming, lower-case normalization and case-insensitive duplicate prevention.
- A Defaults action rebuilds concepts and roles from active CV/profile evidence in a background job.
- Preferred Languages was added, defaulting to English. Languages can be added/removed as free text and known languages display a representative flag.
- Detected pages in a preferred language receive a small ranking bonus; detected non-preferred languages remain visible with the existing ranking penalty.
- Engagement Preferences now preserves Candidate Profile search-signal/language fields when it saves its own settings.

## Dashboard, chat and audit

- The separate Opportunity Search & Current Work card/heading was removed. Search state, interval, CPU, memory, GPU and platform details now sit below ScoutBox activity and above the current activity rows.
- First Run Readiness entries themselves are links; redundant Open/Configure buttons were removed.
- The Pause Search control has additional right-side breathing room.
- Sidebar Logout has extra bottom clearance for browser status/overlay areas.
- Ask ScoutBox uses a cross close button and stores/displays timestamps on both questions and answers.
- Audit Log records and displays human-readable object titles where available while retaining model type/id as secondary context.
- Diagnostics keeps the ScoutBox version/build line and the Last modified value includes seconds.

## Configuration and Performance Lab

- Search Sources Schedule lays each scheduling option on its own row.
- Test Discovery no longer repeats the Recent runs heading.
- Performance Lab now presents independent Chat, Post Age Analysis and DOCX → PDF test sections with their own Run buttons; less common tests remain under Other performance tests.
