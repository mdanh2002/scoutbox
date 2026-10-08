# ScoutBox 0.8.54

## Lead and opportunity review

- Preparing cold outreach from Hidden Leads no longer creates a visible duplicate Opportunity. The internal compatibility backing row is suppressed from Opportunity discovery/list/count views; existing Hidden-Lead outreach backing rows are normalized by migration 0036.
- Opportunity and Hidden Lead detail views allow a manual 0–100 fit override.
- Private notes are surfaced as compact, icon-labelled previews in Opportunity and Hidden Lead list views.
- Hidden Lead company names still open ScoutBox details, the displayed company domain now opens the company homepage, and the right-side open icon continues to open the original discovered/source URL.

## Diagnostics and resource usage

- Search Activity result sorting treats errors/no-results as numeric zero, and each logged query has a small public-search repeat action using the same provider where possible.
- AI Requests Runtime, Provider and Task Type filters are wider.
- Host Disk Usage reconciles its displayed component rows to physical Host Disk Used and separately explains Ollama logical model sizes, which can double-count shared layers.
- Opportunity Detail avoids repeating the Search Source when discovery provenance already supplies it.
- Fixes the missing `hashlib` import in Hidden Leads refresh/change detection.
