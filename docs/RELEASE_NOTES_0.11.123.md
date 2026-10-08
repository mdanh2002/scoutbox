# ScoutBox 0.11.123

## Re-evaluation dialogs

- Opportunity and Hidden Lead Cloud instruction fields now use a wider dialog and a full-width textarea with the label above it.
- The visible **Enable Internet Search** checkbox is removed from Opportunity, Hidden Lead, and Address Book re-evaluation.
- Internet Search is now automatic: enabled for Cloud providers and disabled for Local/Ollama providers.
- Address Book explanatory text about Internet Search, fit recalculation, recycling, and request count is removed.
- Address Book decision logic itself is unchanged.

## Application/outreach protection

- Opportunity and Hidden Lead re-evaluation may not recycle a record that already has application/outreach work.
- A high-confidence type correction can still move an Opportunity to Hidden Leads or a Hidden Lead to Opportunities.
- Hidden Lead protection uses ScoutBox's broader outreach-history detector, including prepared outreach drafts and linked outreach/application records.
- Cross-list conversion keeps the source record in the Recycle Bin for audit/recovery; linked application/outreach records are not hard-deleted.

Migration `0195` is release-audit only; there is no schema change.
