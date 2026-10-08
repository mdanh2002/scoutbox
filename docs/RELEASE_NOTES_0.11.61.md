# ScoutBox 0.11.61

## Daily Digest record presentation

- Opportunity descriptions now use the same concise, grounded summary shown in the Opportunities list instead of appending raw fetched job-description text. This prevents extraction/navigation fragments such as `[APPLICATION] ...` from making the digest look crude.
- Renamed the digest table columns **Why / description** to **Description** and **Contact / URLs** to **URLs**.
- Address Book identities now render as **Name — Company** on one line, with the company styled as secondary text, followed by the discovered timestamp.
- Hidden Leads no longer expose internal workflow text such as `Retained as company-level lead · Relevant: ...`; the digest falls through to useful company summary/evidence instead.
- Digest fallback prose strips leading structured extraction labels while retaining the useful sentence that follows.
- These changes affect Daily Digest presentation only; discovery, selectivity, scoring, and stored records are unchanged.
