# ScoutBox 0.8.104

## Source-first Opportunity compensation

- Salary extraction now gives retained job-description/source evidence precedence over Cloud or external estimates. If the captured role text already contains compensation, ScoutBox uses that rather than attempting to replace it with weaker research.
- Source-page wording such as `Salary estimate: $98,000 - $120,000+ (base benchmark varying by level and region)` is classified as a medium-confidence `Job-description estimate`; employer-advertised compensation remains high confidence.
- Cloud Web Discovery can still ingest compensation returned by its existing research pass, but a retained JD/source salary wins when both exist.
- Local GPU Discovery remains deterministic and network/AI-free for salary extraction. Compensation is optional enrichment and salary parsing failure cannot abort the campaign.
- Migration `0064_v08104_portal_root_salary_repair` reparses retained evidence for historical active Opportunities and replaces weaker stored salary information when a usable salary/benchmark is already present in the JD/source. The migration performs no external requests.
- `Salary not found` remains a clean terminal state when retained evidence genuinely contains no compensation; no confidence/expectation tooltip is attached to that state.

## Ask ScoutBox reliability

- Ask ScoutBox now persists the user message and queues a dedicated `chatbot` Celery job instead of keeping one long browser request open for the entire model response.
- The browser polls persisted Chatbot history and queued/running state. Navigating away, closing the panel, or a transient fetch interruption therefore does not cancel a provider call already accepted by the server.
- The existing unread-answer badge now works with the queued path: completed answers can appear after navigation and are marked seen when the user opens/scrolls to the latest response.
- Browser submission/transport failures use reconnect-oriented feedback rather than incorrectly blaming the selected provider/model. Provider failures are persisted separately with sanitized diagnostic detail.
- Test Chatbot calls the same Chatbot reasoning/provider function used by queued Ask ScoutBox jobs, including the Cloud `Allow internet search` setting.
- Chatbot BackgroundJob metadata records the selected provider, model and internet-search state so diagnostics can distinguish queue/transport/provider failures without exposing credentials.

## Portal Root URL and digest navigation

- Configuration > General now has a `Portal Root URL` setting used for absolute ScoutBox record addresses in scheduled/test digest emails.
- New/empty installations default the setting to `http://localhost:8989`.
- Auto-detect proposes `window.location.origin` and asks for confirmation before filling the field. The prompt warns that a local/internal browser address may not be reachable from the device/network where digest email is opened.
- Values are normalized to an `http://` or `https://` origin with no path/query/fragment and no trailing slash.
- `Send Test Digest Email` persists the currently entered Portal Root URL before generating the test, so the test reflects unsaved form changes.
- Digest record navigation is shown as explicit visible text (`ScoutBox: https://.../record/...`) rather than a hidden `Open in ScoutBox` hyperlink label. Mail clients may still auto-link the visible URL naturally.

## Email configuration polish

- `Refresh Folders` and `Detect folders` use matching button dimensions in the Incoming IMAP Browser.
- Switching the External Outgoing transport between SMTP and Resend clears previous inline test status before generating a new test message.
- Historical outgoing send failures remain available in Email History and are no longer surfaced as a persistent latest-error warning that can become misleading after the configuration changes or a later test succeeds.

## Upgrade safety

- Migration `0064` is data-preserving and performs no network/Cloud AI work. It only reparses retained salary evidence and adds the Portal Root URL setting.
- No Maintenance > Restart System control is included.
- Existing 0.8.103 functionality remains intact, including quiet-day digest fallback, company-context backfill, application cooldown filtering, compensation preference colors, Incoming/Outgoing mail layout and About runtime hints.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application files with the 0.8.104 package, and run the normal ScoutBox restart/upgrade flow. The standard restart applies migration `0064` automatically.
