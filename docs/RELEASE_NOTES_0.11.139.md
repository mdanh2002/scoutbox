# ScoutBox 0.11.139 — Company Identity Integrity & Detail View Cleanup

- Prevent Local AI company extraction from overwriting trustworthy direct ATS/API or structured JobPosting employer identity.
- Reject JD headings/prose such as `What we`, `Who we are`, `We are`, and sentence fragments as company names.
- Prefer first-party ATS board identity when learning Greenhouse, Lever, Ashby, and SmartRecruiters employer boards.
- Repair malformed ATS-backed employer names in migration 0211 and clear stale company research state for repaired records.
- Reject generic corporate/about-us boilerplate as Opportunity list summaries when retained role evidence can produce a role-specific summary.
- Remove Hidden Lead background-task strip and duplicate Status/Added/Source KPI cards; move Added and Source to metadata rows and compact short form controls.
- Remove Opportunity Status/Added/Channel/Post Age/Remote KPI cards; move Added/Channel/Post age/Remote into detail rows.
- Move the Opportunity fit signal to the right of the fit selector while preserving aligned form columns.
- Keep post-age evidence/refresh actions and remote-state styling intact in the new compact rows.
