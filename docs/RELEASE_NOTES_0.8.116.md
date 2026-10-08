# ScoutBox 0.8.116

## Chatbot

- Removed the normal-question deterministic record-query shortcut. Workspace questions now reach the configured Chatbot LLM, with the existing complete Opportunities/Hidden Leads compact index and Chatbot-only primary/secondary failover.
- Removed `Direct record query` as a Chatbot answer provenance path. Non-AI responses are now limited to guardrail/configuration conditions.

## Opportunity and Hidden Lead lists

- Removed the dedicated Fit column from both main list views.
- Fit is shown at the bottom-right of Summary instead.
- Opportunity salary information remains on the left side of the Summary footer when present; Fit occupies the right side.
- Reclaimed table width is returned to Summary/record content while keeping Added timestamps readable.

## Email Configuration

- `Save folder assignments` now aligns to the left edge below the IMAP folder selectors.

## Campaign Templates

- Removed the `Download original resume` link.
- A compact Word-document icon plus the actual source Resume filename (falling back to its label) is shown beneath the Campaign Template name.

## Candidate Profile

- Rebalanced the Resume table columns so File no longer crowds Added, Campaign Template Generated, or the action controls.
- Long file labels are truncated visually with an ellipsis while the original download link and title remain available.
- Action buttons have a reserved, non-overlapping column.

No database migration is required. Migration `0069_v08111_chatbot_source.py` remains the latest migration.
