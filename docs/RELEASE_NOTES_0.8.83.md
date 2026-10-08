# ScoutBox 0.8.83 Release Notes

ScoutBox 0.8.83 incorporates the follow-up review changes on top of 0.8.82. It focuses on list readability, Company Info/Fit presentation, contact data quality, detail-page cleanup, error consolidation, and avoiding redundant AI work.

## Highlights

- Company Info uses maturity/size-aware compact icons, confidence colouring, compact age/size details, and a question mark when no useful information is available.
- Fit faces retain quality semantics while colour represents confidence.
- Opportunity, Hidden Lead and Applications IDs are shown inline in the first identifying cell rather than standalone ID columns.
- Hidden Leads gain a dedicated Email column; known emails are repaired/backfilled from stored record evidence where appropriate.
- Address Book automatic collection rejects generic shared mailboxes such as info@, contact@, sales@, support@ and jobs@ while still allowing real-person and explicit regional routing addresses.
- A one-time 0.8.83 migration repopulates empty Company Info and contact email data from already-stored evidence and retires generic automatically-added Address Book contacts.
- Opportunity detail reuses Cloud AI discovery summaries instead of re-summarizing the same job text, removes broken generated evidence-link clutter, removes Verified tags from Company Info, fixes stale Post Age presentation, and uses clear full-text top actions.
- Recent Errors are grouped by component with counts and consolidated repeated messages.
- List toolbar widths, tooltip line breaks, Hidden Lead Company Info width, Address Book controls, and unread-row presentation receive additional cleanup.

Existing data and volumes are preserved by the normal upgrade path. Historical migration filenames remain unchanged for Django migration compatibility.
