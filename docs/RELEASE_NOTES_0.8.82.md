# ScoutBox 0.8.82 Release Notes

ScoutBox 0.8.82 is a focused refinement of 0.8.80 covering discovery-route isolation, review UI, company/role research, campaign reliability, diagnostics, and Ask ScoutBox context/export.

## Local AI Discovery and routing

- The user-facing Source-Guided name is now **Local AI Discovery**, described as search sources plus local Ollama/GPU processing. The stored `source_guided` mode key remains unchanged for upgrade safety.
- Local AI Discovery rejects hidden Cloud execution and remains usable without any Cloud provider configured when Ollama/local AI and search sources are available.
- Cloud Web company/research paths stay on the configured Cloud route and do not silently fall back to Local AI Discovery search/Ollama processing.
- AI Requests expose the intended execution path more clearly, and failed requests no longer present normal-looking `0 in · 0 out` usage when inference never started.

## Opportunity and Hidden Lead review

- Opportunity status is displayed beside the company instead of in a standalone list column, and a compact **Apply Via** column uses an icon-only presentation with the method in a tooltip; an applied date appears beneath the icon when available.
- Cloud-discovered useful public contact emails are captured without replacing a stronger existing contact with a weaker generic mailbox.
- Opportunity notes retain a short distinctive Cloud discovery signal only when the research contains genuinely unusual context rather than generic role wording.
- Hidden Lead HTTP status sits directly after the company name; Source URL is restored beneath Campaign on Opportunity and Hidden Lead detail screens.
- Opportunity and Hidden Lead detail titles now include the role/lead descriptor, company, and ScoutBox record ID; the standalone ID card and duplicate title line are removed.
- Hidden Lead Cloud outreach notes are factual rather than templated: only new concrete contact information such as a public email or a distinct direct-contact URL is saved. The old `Cloud outreach path:` prefix is removed from existing generated notes on upgrade.
- Unread/new Opportunities, Hidden Leads, Address Book entries, and Applications & Outreach rows use the approved full-row `#3C4248` background while preserving normal and semantic text/icon colours.
- The compact toolbar `+` add-entry control has a slightly larger glyph.

## Post Age and company/role research

- `Older / uncertain` is now **Likely Old** and the evergreen state is labelled simply **Evergreen**, with dedicated icon treatments and confidence colouring; numerical confidence percentages are omitted from list display, while tooltips state the confidence level.
- Compact Company Info is available consistently across Opportunities, Hidden Leads, and Address Book. Research supports founding year, public founder information, age bands, approximate size bands, and verified/estimated distinction where evidence permits.
- Opportunity detail includes separate **Role Info** and **Hiring Process** cards. Cloud research may supply salary/context and role-specific or company-general hiring-process evidence with confidence/provenance; missing local capabilities degrade to unavailable rather than invoking Cloud implicitly.

## Ask ScoutBox

- Ask ScoutBox receives a redacted configuration summary including discovery mode, enabled providers/models, Ollama/search-source availability, limits, campaign context, and feature toggles, while explicitly excluding credentials and secrets.
- Chat continues to receive a token-budgeted view of recent workspace state and errors/notifications.
- Chat export is now HTML, preserving message separation, timestamps, links, and rendered Markdown-friendly content. Normal data-list exports remain Excel.

## Campaign reliability and diagnostics

- Cloud campaign progress uses meaningful stages such as Preparing context, Cloud research, Inspecting candidates, Verifying URLs, Qualifying leads, Validating contacts, and Persisting results.
- CampaignRun stores heartbeat, stage, intended provider/model, and stall diagnostic information.
- Dashboard activity shows last real campaign activity and warns after the configurable idle threshold. A longer configurable watchdog threshold marks abandoned Running campaigns failed rather than leaving them running indefinitely.
- Provider/network calls have bounded hard timeouts, and expensive Cloud research is not retried indefinitely.
- Queued campaigns use a distinct non-green visual state; Recent Errors places the unread count directly with the heading and keeps the Dashboard count consistent.

## Follow-up UI and data repair polish

- Fit list cells now use compact face indicators (good, average, poor, or unknown) instead of signal bars; the underlying fit values, filters and editors are unchanged.
- Unknown Company Info is a question mark only. Known Company Info uses related but distinct age/people visual cues, and migration `0049_v0881_backfill_company_contact.py` performs a one-time stored-data backfill for Company Info and structured contact emails.
- Existing emails already present in Opportunity/Hidden Lead stored detail or research data are promoted into the Contact field where appropriate.
- Hidden Lead Company Info sits immediately after Company; Address Book places Phone and Role after Email. Hidden Lead list IDs no longer truncate, and campaign IDs are shown inline beside campaign names in smaller muted text.
- Country filters on Opportunities, Hidden Leads, Address Book and Applications & Outreach now show only represented countries with record counts. United States aliases such as `USA` are normalized so the US flag and filtering work consistently.
- Opportunities gain a **Hide failed URLs** option: URL-based entries whose checked target is not HTTP 200 are hidden while email-based contacts remain eligible. Rows-per-page/export controls are moved to the bottom-centre list footer.
- Dashboard error attention no longer disappears merely with age; it remains until a diagnostics/statistics/settings surface is opened. ScoutBox Activity omits the low-value Search Window chip and instead surfaces a concise linked latest-error hint when one exists.
- Ask ScoutBox visually connects the launcher to the open side panel, has a larger Export HTML control, and exports rendered bold/italic/underline, bullets, section headings and line breaks rather than raw Markdown.
- Dashboard and campaign chart segments visibly brighten/highlight on mouse hover. AI Request Input/Output truncation ellipses have additional spacing.
