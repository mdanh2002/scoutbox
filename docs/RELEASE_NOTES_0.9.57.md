# ScoutBox 0.9.57

## Compact toolbar actions

- Campaigns now use icon-only actions for Delete Selected and New Campaign.
- Campaign Templates now use icon-only actions for New Template and Delete Selected.
- Blacklist now uses icon-only Reset to Defaults and Delete Selected actions.
- Address Book now uses an icon-only Delete Selected action.
- Applications & Outreach now uses icon-only Delete, Sync IMAP, and Import History actions.
- Every compact action keeps a descriptive tooltip and accessible `aria-label`.
- New semantic SVGs distinguish campaign creation, template creation, reset, IMAP sync, and history import without relying on text or font glyphs.

## Fit sort direction

- The clickable Fit control in Opportunities and Hidden Leads now shows a tiny chevron immediately to the right of the Fit icon while Fit sorting is active.
- Highest-to-lowest uses a downward chevron; lowest-to-highest uses an upward chevron.
- The indicator is intentionally small so it communicates direction without turning the Fit control into a larger toolbar element.

No database migration is required for 0.9.57.
