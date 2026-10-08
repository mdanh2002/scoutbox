# ScoutBox 0.8.76

## Discovery integrity and evidence

- Cloud Web and Source-Guided discovery are hard-isolated at routing/runtime boundaries. Cloud Web does not silently invoke Ollama/local discovery stages; Source-Guided does not silently invoke Cloud AI.
- Cloud Web Raw Text is cleaned content fetched from the final HTML role URL. The Cloud research response is retained as the Opportunity AI Summary instead of being re-summarized.
- Opportunity/Hidden Lead persistence uses normalized URL/domain/company/title identity. Same-list duplicates are suppressed conservatively and a concrete active Opportunity wins over a generic company Hidden Lead. Existing overlaps are reconciled during the upgrade while campaign associations are retained.
- Opportunity and Hidden Lead final URLs record lightweight HTTP health. Opportunity lists show the status beside the link; Hidden Lead summaries retain the company and append a compact health hint when the target is unavailable.

## Address Book and company data

- Company/HQ location is separate from remote-role eligibility; Remote/Worldwide/Global/Anywhere/Distributed labels are not retained as company locations.
- Empty summaries display as blank and legacy dash-only summaries are cleared. Domain-derived company names are humanized, including `Implicitconversions` → `Implicit Conversions`.
- Contact Name and Company remain separate editable values. Automatic contact collection avoids repeatedly adding recent contacts for the same company unless the new address is meaningfully stronger, such as a named personal mailbox replacing a generic jobs/info address.
- Company flags and source-link presentation are aligned with the other list views.

## Candidate Profile, campaigns and chatbot

- Candidate Profile no longer embeds Campaign Templates. Each Resume row now has **Create Campaign** after Delete. The form uses the selected Resume plus Resume Concept, Likely role and an optional additional prompt to add a new campaign template; existing templates are never removed.
- Campaign execution summaries are formatted as compact structured lines instead of dense mixed counters. Campaign-name styling reflects campaign status.
- ScoutBox chat is a multi-turn conversation over current Opportunities, Hidden Leads, Blacklist, Applications/Outreach and Recycle Bin context. It can expand to a full-window view and safely renders basic Markdown.
- Chatbot routing uses one explicit provider/model only. There is no hidden fallback provider/model, and the UI warns when chat is not configured for Cloud AI.

## Review UI, age, quotas and diagnostics

- Post Age uses Evergreen, ~1 week, ~1 month through ~6 months, then **Older / uncertain** with an archive-style indicator rather than an awkward less-than-or-equal label.
- Opportunity detail metadata is more compact, remote checkmarks render consistently, and Search URL / Target URL rows are hidden when they normalize to the same value.
- Hidden Lead notes live in Summary and receive useful three-line wrapping; similar note layouts align wrapped text after their icons.
- AI Request list previews strip leading Markdown JSON fences, avoid horizontal overflow, and link related Campaigns. JSON detail/copy behavior remains structured/raw respectively.
- Blacklist scope filters show item counts. Cloud AI Limits show compact usage/limit summaries and default to 250 discovery candidates, 250 deep-research candidates and 500 page-recovery operations per day.
- Source-Guided Test Selection distinguishes queued, actively testing, successful and failed items.
- Ollama Test Configuration aligns with other provider actions; CPU current-value details have additional right padding; chart bars/arcs/segments visually highlight on hover in addition to showing tooltips.
- ScoutBox Activity shows reached search-provider or Cloud-AI quotas beside the Search Window chip, with direct links to the relevant configuration section.

## Database

Migration `0042_v0876_quality_and_url_health.py` adds Opportunity target-URL health fields, updates Cloud candidate/recovery defaults, clears invalid company-location placeholders and dash-only summaries, and performs conservative active Opportunity/Hidden Lead reconciliation on upgrade.
