# ScoutBox 0.11.55

## Daily Digest review layout

- Opportunities, Hidden Leads and Address Book now each contain two clearly separated digest subsections: **New today** and **Recent · last 7 days**.
- Each subsection is capped at 10 rows so a busy week does not turn the daily email into an unbounded dump.
- Digest headline counts now describe the local calendar day's new items, while the review tables also expose earlier items from the preceding seven-day window.
- The first list column is simply **Company**.
- Fit scores are intentionally omitted from digest rows.
- Remote status, posting age, employee count, company age and company location are rendered as separate compact lines instead of one long dot-separated sentence.

## More useful operational context

- The verbose **Major errors** section is removed from the Daily Digest. A compact **Campaigns · last 24 hours** section now shows recent campaign name, status/time and retained Opportunity/Hidden Lead counts.
- The noisy **Budget warnings** section is removed. The misleading aggregate `Automatic runs x/y` budget row is also omitted because that limit is per campaign rather than a global denominator.
- Added a compact **Candidate profile & engagement preferences** section with candidate priorities, operating locations, engagement types, preferred company sizes, pay preferences and hiring-process guidance.
- Current Settings now also reports the independent Opportunity, Lead and Contact admission levels.

## General settings cleanup

- Removed the long explanatory paragraphs below Opportunity selectivity, Lead selectivity and Contact admission.
- Those three dropdowns now use the same 110 px control width as Max concurrent campaigns and the other compact General limits fields.
