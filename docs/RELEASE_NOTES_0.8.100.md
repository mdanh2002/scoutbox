# ScoutBox 0.8.100 release notes

ScoutBox 0.8.100 improves Opportunity-summary completeness, Local GPU discovery quality, cloud Chatbot research, campaign liveness reporting, and email configuration/history.

## Opportunity Summary

- New Opportunities with usable role/JD evidence should no longer show a blank Summary simply because the narrow specialist-keyword formatter found no niche cue.
- Local GPU/Local AI enrichment asks the selected local model for a compact candidate-fit explanation and retains a source-grounded fallback when the model returns no usable wording.
- Cloud Web Discovery does not locally compose its normal Opportunity summary. The Cloud resolver is explicitly asked to author a concise fit summary from the actual role/JD and candidate profile, preferably **20–30 words** and never more than **50 words**. Weak or adjacent fit should be stated plainly rather than invented as niche relevance.
- Migration `0058_v08100_chatbot_mail_summary.py` repopulates only historical Opportunities whose `list_highlight` is empty. Existing non-empty summaries are left untouched. Saved Cloud-AI wording is preferred for past Cloud discoveries; retained role/JD evidence provides the repair path when no saved wording is available.
- Maintenance > Rebuild Missing AI Data also treats a missing Opportunity list Summary as missing AI data and, on the Cloud route, asks Cloud AI for the short fit summary.

## Local GPU language quality gate

- Local GPU Discovery now filters both Opportunities and Hidden Leads when the fetched page is predominantly non-English.
- The gate is deliberately tolerant: names, code, quotations, translated paragraphs, and a small amount of Chinese/Korean/Japanese/other-language text do not reject an otherwise English page.
- Pages dominated by Chinese, Japanese, Korean, Cyrillic, or a clearly dominant non-English Latin language are rejected from Local GPU discovery.
- Cloud Web Discovery is intentionally exempt; Cloud research may translate and ground foreign-language sources.

## Cloud Chatbot internet search

- Configuration > AI > Chatbot shows **Allow internet search** only when the chosen Chatbot provider is OpenAI, Gemini, or OpenRouter. It is hidden and disabled for local Ollama models.
- When enabled, Chatbot uses the provider's web-search/grounding API for public/current information while keeping ScoutBox's local database context read-only.
- Web-grounded answers can surface explicit source URLs alongside normal ScoutBox record links.
- **Test Chatbot** follows the same setting. With internet search enabled it performs a real provider web-grounding diagnostic instead of testing only text generation.

## Campaign liveness / Possible stall

- A running campaign now maintains a lightweight worker heartbeat every 15 seconds, including while a search provider, page fetch, or AI call is blocking.
- Dashboard **Possible stall** detection therefore tracks whether the worker is alive rather than requiring the current external call to complete inside the warning window.
- Existing progress/stage messages and the watchdog's genuine stalled-run handling remain in place.

## Email configuration and history

- Configuration > Email tab labels are now **IMAP**, **SMTP**, and **IMAP Browser**.
- The old separate SMTP Testing tab is removed. SMTP test-send controls appear below the SMTP credentials.
- SMTP test-send executes synchronously, so it no longer reports only `Queued` while waiting on a background worker.
- A successful test sends the message immediately through the saved SMTP profile. Both successful and failed test-send attempts are persisted in Email History.
- `MailEvent` now records a `server` value. Email History shows a **Server** column for Incoming, Outgoing, and Draft Activity, using the relevant `IMAP host:port` or `SMTP host:port`.
- Existing email-history rows are backfilled with the most appropriate configured server when the upgrade has enough profile information to identify it.

## Upgrade

For an existing 0.8.99 installation, keep `.env` and Docker volumes, apply the upgrade package, and run:

```bash
chmod -R +x *.sh
./restart_scout_box.sh
```

The restart applies migration `0058_v08100_chatbot_mail_summary.py` automatically.
