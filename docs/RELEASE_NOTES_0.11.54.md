# ScoutBox 0.11.54

## Independent discovery and contact selectivity

- Added three independent Config > General controls instead of one global discovery level:
  - **Opportunity selectivity:** Broad / Balanced / Specialist.
  - **Lead selectivity:** Broad / Balanced / Specialist.
  - **Contact admission:** Broad / Balanced / Verified.
- All three default to **Balanced**, preserving the 0.11.53 admission behavior for existing installations until the user deliberately changes a setting.
- **Specialist Opportunities** require stronger semantic/profile confidence plus direct campaign-specific evidence in the actual vacancy, rather than relying on a high Fit score or a technical employer alone.
- **Specialist Hidden Leads** use higher semantic/minibrowser admission bars and require concrete campaign-specific evidence before a company is retained. Basic company/entity integrity remains mandatory at every level.
- **Verified Contacts** require strong confidence, plausible company ownership, and direct evidence for a real person's supplied name. Email local-parts are not accepted as identity evidence in Verified mode.
- **Broad Contacts** may retain useful recruiting/engineering/research shared routes while keeping them as organization routes instead of fabricating person names.
- Each Campaign Run snapshots the three levels when execution starts. A settings change during a running campaign therefore applies to the next run rather than changing rules midway.
- Campaign support diagnostics record the selectivity snapshot used by each run.
- The Dashboard shows compact **Jobs / Leads / Contacts** level links immediately to the left of the Search/Pause control. Each link jumps directly to its Config > General setting.
- Existing Opportunities, Hidden Leads, and Address Book records are not automatically hidden, deleted, or reclassified when a level is changed.
- **Global Activity Map:** Applications & Outreach is no longer plotted and no longer appears in the map legend; the map now focuses on Opportunities, Hidden Leads, Address Book contacts, and Blacklist entries.
