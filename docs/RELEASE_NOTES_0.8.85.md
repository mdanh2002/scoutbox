# ScoutBox 0.8.85 Release Notes

ScoutBox 0.8.85 is a focused UI/data-quality follow-up to 0.8.84.

- Opportunity list notes now show only brief, distinctive discovery context without the templated `Discovery signal:` prefix.
- Hidden Leads use a structured Contact column: email first, then a distinct direct contact URL; contact-only notes are cleaned by migration.
- Hidden Lead URL-health badges are smaller and record IDs sit closer to the company name.
- AI Requests gives Task / Related more room and displays a failed request's error in Output when inference returned no output.
- Timestamps use the normal ScoutBox interface font with tabular numerals, avoiding the monospaced appearance while maintaining alignment.
- Obvious empty-cell dash placeholders are removed.
- Cloud quota consumption stays on the same line as its status icon.
- Recycle Bin gains Excel export beside Rows and removes the redundant Select All action.
- Resource Usage shows when the current snapshot was captured.
- The Dashboard Current Opportunities table is removed.
- List tables can be scrolled horizontally on narrow screens.
- Dashboard and top-right error badges now represent distinct error-notification components seen in the last 24 hours; they are not reset by opening Dashboard, Recent Errors, Resource Usage, Statistics, Settings, or the notification popover.
- Migration `0051_v0885_contact_note_cleanup.py` adds Hidden Lead `contact_url`, backfills contact data from legacy notes, and cleans prior generated note boilerplate.
