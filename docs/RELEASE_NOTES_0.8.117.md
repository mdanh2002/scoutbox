# ScoutBox 0.8.117 Release Notes

## Chatbot reliability

- Ask ScoutBox uses a five-minute total provider-request budget per queued question.
- The primary route receives the remaining budget first; when it fails quickly, the secondary route can use almost the entire remaining window. This specifically removes the old 90-second Ollama failover ceiling.
- HTTP 429 / Too Many Requests errors are retried once in the Chatbot path only, using `Retry-After` when available (capped to a practical delay) before proceeding to secondary failover.
- No discovery, enrichment, Cloud Web, or Local AI Discovery timeout/routing behavior is changed.
- Full-screen Chatbot mode locks the outer document scrollbar and restores it when full-screen closes or the Chatbot panel is hidden.

## Configuration UI

- `Different-role score penalty` and `Unknown-date score penalty` use the same 110 px compact number width as the adjacent day-window fields.
- Incoming/Outgoing mail fields are capped to a consistent 520 px control width, including SMTP/IMAP, application identity, test mail fields, and message body, while retaining a one-column responsive layout on narrow screens.

## Campaign / Resume UI

- Source Resume filenames in Campaign Templates are clickable downloads again, with the existing Word-document icon and compact secondary styling.
- Campaign Opportunity/Lead Fit values at the very-low level render as `?` rather than the downward arrow that could be mistaken for a download action.

## Database

No new migration is required. `0069_v08111_chatbot_source.py` remains the latest migration.
