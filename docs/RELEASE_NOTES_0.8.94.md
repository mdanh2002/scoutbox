# ScoutBox 0.8.94

## List-view information architecture

- Opportunities move contact email and role-domain/HTTP-health context into the bottom of **Role / Company**.
- The old Opportunity **Contact** column becomes **Summary**, showing at most about 50 words of role-specific evidence. Existing rows derive the summary from already-stored AI job summaries, Cloud research, snippets, notes, fit reasoning or source text, so no data migration is required.
- Hidden Leads move contact email/contact URL into the bottom of **Company**, with an email/link icon after the value.
- Hidden Lead **Summary** gets the recovered width and **Company Info** moves after Summary and before Added.

## Presentation

- Email History preview uses the ScoutBox dark palette while remaining isolated in the sandboxed iframe.
- Domain Age uses a plain globe icon only.
- Search text-box hints are standardized to the short `Search…` placeholder.

## Search consistency

- Opportunity search now includes the stored fields used to construct the visible summary.
- Hidden Lead search includes summary, match summary and evidence, matching the visible fallback behavior.

## Upgrade

No new database migration is required. Keep the existing `.env` and persistent Docker volumes, replace application files, and run `./restart_scout_box.sh`.
