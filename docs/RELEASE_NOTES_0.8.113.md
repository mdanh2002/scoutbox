# ScoutBox 0.8.113 release notes

## AI Requests
- Replaced separate Expand all / Collapse all controls with one stateful Expand / Collapse button for each JSON tree.
- JSON payload detection strips recognized Markdown/provider wrappers before validation. It accepts plain JSON, fenced `json`/`js` payloads, whitespace variants, and shortened closing backtick fences.
- `View raw` remains physically hidden for non-JSON payloads. Non-JSON text continues to receive lexical highlighting for JSON-like fragments.

## Hidden Leads
- Fit remains immediately before Added.
- Fit is now a compact icon column; Added is widened for the full timestamp.

## Email Configuration / IMAP Browser
- Refresh and Detect are icon buttons beside the IMAP Browser heading and both expose descriptive tooltips.
- Added an in-place `Save folder assignments` action below the Inbox/Drafts/Sent/Browse selectors.
- Moved test-message generation below the message list and renamed the action `Generate Test Email`.
- Refresh/detect and generation continue to use background jobs and do not reload the page. The save action is also asynchronous.

## Chatbot configuration
- Removed the visual Primary/Secondary route cards and headings.
- Primary provider/model, Secondary provider/model, internet-research toggles, and Answer token cap now share one aligned form layout.
- Existing primary/secondary Chatbot routing and failover behavior is unchanged.

## Compatibility
- No new migration is required. Migration 0069 remains the latest migration.
- Discovery algorithms are not modified in this release.
