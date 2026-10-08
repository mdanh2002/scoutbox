# ScoutBox 0.10.1

## Release numbering

- This release starts the 0.10.x line at **0.10.1**.
- Routine future releases increment the patch component: **0.10.2, 0.10.3, ...**.
- The 0.10.x line should only be left for a deliberately designated major release.

## Address Book automatic collection repair

- Added a shared `maybe_persist_addressbook_contact()` policy used by mailbox parsing, Cloud Web contact persistence, source-guided Opportunity/Hidden Lead discovery, manual Cloud filtering, and retained-evidence contact repair.
- Source-guided discovery now extracts only safe, company-owned person/regional contact addresses from the page text it already fetched; this adds no new network or AI request.
- Automatic discovery rejects generic/functional and administrative mailboxes from Address Book while preserving those addresses on the originating Opportunity/Hidden Lead when useful.
- Generic detection now handles separators correctly, so addresses such as `help.join@...` no longer look like named people.
- Automatic public-contact promotion requires the email domain to match either the inspected source domain or the company identity closely enough to be plausible.
- Existing active Address Book contacts may be refreshed, but an exact contact already in the Recycle Bin is never resurrected or touched.
- IMAP contact extraction now uses the same tombstone-aware path and no longer repeatedly updates recycled contacts or queues doomed company-research jobs for them.
- Manual Cloud+Internet filtering promotes newly verified direct contact emails into Address Book through the same policy.
- Migration `0080_v0963_addressbook_autopersist_repair.py` backfills safe existing Opportunity and Hidden Lead contacts without resurrecting deleted Address Book entries.

## Ask ScoutBox / Hidden Lead display hotfix

- Ask ScoutBox now includes Address Book records when the question explicitly refers to contacts or the Address Book, including mixed recommendations against Opportunities and Hidden Leads.
- Contact recommendations prioritize named people at companies already represented by relevant Opportunities/Hidden Leads; Address Book confidence remains a data-quality signal rather than a fit score.
- Chatbot output omits missing contact fields instead of printing placeholders such as `Not provided` with fabricated-looking contact URLs.
- ScoutBox record auto-linking no longer rewrites company names inside existing Markdown links or public URLs, preventing malformed links such as `https://www.[company](/cold-contact/... ).com/...`.
- Hidden Lead summaries suppress structured enum leakage such as `full-time`; existing affected rows fall back to useful match/evidence text and are considered eligible for summary refresh.
- Cloud Hidden Lead persistence now refuses engagement/remote enum values as free-text company summaries.
