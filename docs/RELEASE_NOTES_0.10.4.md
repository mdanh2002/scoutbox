# ScoutBox 0.10.4

## Address Book recommendation answer enforcement

- The chatbot still supplies stored email and company background in its compact Address Book context, but 0.10.4 no longer relies on the model to obey that formatting request.
- A deterministic post-processing guard recognizes Address Book entries the model actually recommended and inserts the exact stored email when the model omitted it.
- The same guard inserts a concise `Company Background` from the stored company summary or compact company research when the model omitted it.
- When no stored email exists, a stored phone may be shown instead. Missing contact methods are never invented.
- Structured enum noise such as `full-time`, `remote`, `hybrid`, and similar values is rejected as company-background prose.
- The prompt now explicitly forbids names-only Address Book recommendation lists.

## Existing chatbot correctness protections

- Address Book totals remain authoritative and contacts are not mislabeled as Hidden Leads.
- Country/location queries search the complete loaded workspace before compaction.
- Missing/fabricated contact placeholders, generic recommendation boilerplate, email-link corruption, and substring record linking remain guarded.

## Release numbering

Routine future releases increment the patch component: **0.10.5, 0.10.6, ...**. The 0.10.x line is retained unless a deliberately major release is designated.
