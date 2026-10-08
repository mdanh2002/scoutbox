# ScoutBox 0.8.111 Release Notes

Released 26 August 2026.

ScoutBox 0.8.111 adds Chatbot-only provider/model failover, clearer Chatbot provenance, safer AI Request JSON/raw controls, IMAP Browser test-message generation, and a few Resource Usage/AI Requests presentation fixes. The existing Local AI Discovery and Cloud Web Discovery implementations are not changed by this release.

## Chatbot Primary / Secondary failover

- Chatbot routing now stores an explicit Primary provider/model and a Chatbot-only Secondary provider/model.
- Both Primary and Secondary may independently be Ollama, OpenAI, Gemini, or OpenRouter, provided the selected provider is enabled and the exact model is selected.
- The Secondary route is not added to any discovery, enrichment, application, or other AI pipeline stage.
- A queued Ask ScoutBox request first uses the saved Primary route. A provider/model exception triggers the saved Secondary route. A complete-workspace context-limit result can also be retried against the Secondary model because the secondary may have a different context capacity.
- If both routes fail, the persisted answer explicitly reports that failover was exhausted rather than silently masking the failure.
- Each persisted assistant answer stores and displays its source underneath the answer. Model answers show provider + exact model; deterministic record queries and context guardrails are labelled as ScoutBox rather than falsely attributing them to a provider.
- Chat exports preserve the same answer-source information.
- AI & Discovery provides separate `Test Primary` and `Test Secondary` actions.

### Chatbot Auto-select

- When an enabled Cloud AI configuration has a saved API key and exact saved/resolved model, Auto-select makes that Cloud route Primary and chooses the strongest suitable installed Ollama generation model as Secondary.
- If no Cloud model is configured, Auto-select chooses the two strongest distinct local generation models, with the higher/larger model as Primary and the next lower model as Secondary.
- Embedding/reranking models are excluded from local Chatbot selection.
- If the required pair cannot be found, ScoutBox reports what is missing instead of saving a partial failover configuration.

## AI Requests

- Status and Duration columns have separate minimum widths and centered headers to prevent sortable-header overlap.
- `View raw` is fully hidden when that Input or Output is not valid JSON. It is never presented as a disabled control for plain text.
- JSON parsing unwraps Markdown JSON fences and tolerates shortened trailing backtick closers after a recognized opening fence.
- Valid JSON supports the tree viewer and syntax-highlighted raw mode. Expand/Collapse is shown only for valid JSON tree mode.
- Non-JSON text still receives safe lexical highlighting for quoted strings, numbers, booleans/null and JSON-like fragments; this does not claim that the entire payload is valid JSON.
- Copy remains available for every Input and Output.

## Resource Usage

- The selected-period Cloud Usage label `Output + Reasoning Safety Usage` is shortened to `Output + Reasoning`.
- The same combined `tokens_out_reasoning` daily safety bucket and existing hard-limit enforcement remain in place; this is a label-only change.

## IMAP Browser test messages

- `Generate test emails` is available in Incoming settings for both Internal Development and External Mail profiles.
- Before generating, ScoutBox saves the current Incoming host/account/folder mapping fields, so the action tests what is currently visible in the form.
- The action uses IMAP APPEND only; it does not send mail through SMTP or Resend and does not contact an external recipient.
- One message is appended to each configured Inbox, Drafts and Sent folder. Subject and body both contain a creation timestamp, making repeated tests easy to distinguish.
- The generated rows are also recorded in Email History with test metadata.

## Database migration

`0069_v08111_chatbot_source.py` adds `source_provider` and `source_model` to persisted Chatbot messages. Existing messages remain valid with blank source fields.

## Compatibility

Existing 0.8.110 installations can retain `.env`, PostgreSQL/Redis/media volumes and all current records. Replace application files and run `./restart_scout_box.sh` so migration 0069 is applied.
