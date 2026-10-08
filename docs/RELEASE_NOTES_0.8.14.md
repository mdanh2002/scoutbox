# ScoutBox 0.8.14 release notes

## Discovery quality and sources

- Adds a **Preferred Sources** tab for the initial URL-discovery engines used by Source-Guided Discovery. Google and Bing are the defaults; this preference is independent from the broader enabled-source list.
- Adds searchable, paginated **Custom Domains** with name, domain, note and enable state. Enabled entries participate in targeted `site:` searches.
- Adds a Sources **Default** action that enables recommended sources while excluding low-value marketplaces.
- Rejects confirmed HTTP 404/410 target pages before Opportunity classification or creation; search-result snippets no longer rescue dead pages.

## Opportunities and applications

- Simplifies the Opportunities table by hiding Status and Language; role names open their Opportunity details.
- Replaces Remote tags with bare semantic marks: double green check for confirmed remote, single green check for likely remote, question mark for unknown, and red cross for not fully remote.
- Replaces bold unread styling with a subtler unread color treatment and removes the explanatory read-state legends.
- Preserves source text alongside AI summaries for future discoveries, shows **No Raw text Available** when no source text exists, and adds paragraph breaks to long unbroken text.
- Opportunity details always show Source & Discovery information, hide redundant refresh/translation controls, add a private Note field, and move status editing into the Status KPI.
- Applied Roles hides Confidence; Application Draft editing can change application type/channel.

## Market Studies

- Improves company derivation from page text and registrable domains (for example `os.mbed.com` no longer becomes `OS`).
- Excludes race-to-the-bottom marketplaces and documentation/reference/wiki/man-page style pages.
- Hides Language, shows Country, shows source domain below company, adds direct blacklisting and private notes, and replaces the ambiguous ellipsis detail control with a details icon.

## Dashboard and interface

- Removes the duplicate Dashboard page title, the extra activity line, and redundant Dashboard opportunity status display; aligns the local-model/runtime line.
- Adds a Refresh control to Recent Activity and keeps Diagnostics refresh styling consistent.
- Uses a larger, simpler borderless ScoutBox mark, distinct navigation hover/selected states, and a quieter `© 2026 ToughDev` footer.
- Adds **About ScoutBox** under Quick View with concise build, workflow, concepts and configuration guidance.

## Resource Usage

- Adds best-effort macOS native GPU probes and Linux NVIDIA telemetry with failure-safe fallbacks.
- Reports host RAM and disk totals/usage where available and adds a Disk Space Used metric.
- Aligns KPI labels/values, removes the Input Tokens hover popup, and renames the breakdown to **Token Categories**, counting input plus output tokens.
- Resource-chart tooltips place the timestamp on its own line, then one metric per line.
- Adds one concentric request/error provider visualization above the existing Search Provider Performance table.
