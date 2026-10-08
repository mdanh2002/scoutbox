# ScoutBox 0.10.3

## Address Book recommendations are actionable

- “Worth contacting”, “worth reaching out”, and “reach out to” are now classified as recommendation intent.
- Address Book recommendation directories include stored email addresses and a compact company summary for each candidate contact.
- Rich contact context now labels the company background explicitly as `company_summary` and includes compact `company_info` research when available.
- Contact recommendation ranking favors records with an exact stored email, then phone, and gives a small bonus to records with useful company background.
- The prompt requires recommended Address Book entries to show the exact stored email when one exists and to include a short Company Background. Missing contact methods are not invented.

## Existing chatbot correctness protections

- Address Book counts remain authoritative and contacts are not mislabeled as Hidden Leads.
- Country/location queries continue to search the complete loaded workspace before compaction.
- Missing/fabricated contact placeholders, generic fit/outreach boilerplate, email-link corruption and substring record linking remain guarded.

## Release numbering

Routine future releases increment the patch component: **0.10.4, 0.10.5, ...**. The 0.10.x line is retained unless a deliberately major release is designated.
