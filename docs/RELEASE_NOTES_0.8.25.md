# ScoutBox 0.8.25

This maintenance release closes several UI regressions from the provider-access and unified application/outreach work, improves role-specific campaign generation, and makes automatic Market Studies scans bounded and recoverable.

## Search providers

Yandex, Baidu and Naver retain Public Access as the default, but their API modes are again selectable. The Access Type JavaScript no longer normalizes the control during `change` and accidentally resets the user's API choice back to Public Access. Yandex exposes API-key and IAM-token modes, Baidu exposes Qianfan Web Search API, and Naver exposes legacy Developers Center and API HUB modes.

Preferred Sources now defaults to all active search engines except Baidu. Upgrade migration 0022 only expands installations that still have the historical empty/Google/Bing default, preserving clearly customized selections.

## Applications, outreach and opportunity details

Prepare Outreach creates a contextual subject before the AI worker starts, rejects generic subjects such as Direct outreach, and uses product/project/technical evidence plus profile relevance for fallback wording. Existing outreach rows with a useful generated email subject but a generic Opportunity title are repaired by migration 0022.

Applications & Outreach italicizes company names, top-aligns Resume/Cover content, and shows a generated Resume PDF when that is the available Resume artifact. Import proposals are separated from the input step by a spaced divider.

Opportunity detail page headings now prefer a valid role title and never promote recommendation prose beginning with `Reason:` or Markdown `### Reason:` into the main heading/breadcrumb.

## Campaign templates

Candidate Profile keeps a configurable campaign-generation prompt. Generated templates use only technologies/concepts supported by the configured profile or active Resume evidence, rank them per role, and apply cross-role duplication control so technical writer, firmware, emulation, reverse-engineering and other templates no longer receive the same global technology list. An available AI route may rank the allowed terms, with a deterministic evidence-only fallback.

## Facebook Pages to Watch

Add Page is now beside Search Pages and opens an in-app form for Page ID and Page Title. The URL column is removed; the title links to the page. Save and delete controls have clearer styling and spacing.

## Market Studies scan timeout

The old scan could fan out across many providers, queries and result-page fetches, while Dashboard also had a separate rule that marked a still-running Hidden Market job failed after 75 minutes. v0.8.25 removes Dashboard-side job mutation. Hidden Market discovery now rotates over at most four preferred providers per scan, uses at most six queries per provider and six results per query, uses shorter page-fetch timeouts, reports progress throughout the scan, and has a 40-minute execution budget. The scheduler releases an orphaned queued/running scan after 50 minutes so a crashed worker cannot block all future scans.

## UI cleanup

About ScoutBox places section icons in the heading row, shortens What it does, and modestly expands Why use ScoutBox. Tracking Links is positioned immediately after ToughDev Stats in Configuration. Dashboard Recent errors keeps severity information in the text/data but removes the decorative yellow/red left bars.
