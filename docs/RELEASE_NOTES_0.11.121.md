# ScoutBox 0.11.121

## Manual re-evaluation cross-list correction

- Opportunity re-evaluation can convert an item to Hidden Leads only when the model identifies a non-vacancy company-level target with a concrete, current outreach/commercial signal at very high confidence.
- Hidden Lead re-evaluation can convert an item to Opportunities only when the model verifies one specific current vacancy or contract/project request, including a specific title and exact role/project URL, at very high confidence.
- Conversion thresholds are intentionally stricter than ordinary keep/recycle thresholds.
- Existing application/preparation history protects an Opportunity from automatic cross-list conversion.
- Existing protected Hidden Lead outreach/application state likewise prevents automatic conversion.
- Cross-list conversion reuses an existing active destination record when possible, records an audit entry, and moves the source record to the Recycle Bin rather than hard-deleting it.
- Address Book re-evaluation is unchanged.

## Re-evaluation UI

- Removed the explanatory Internet Search / Fit paragraph from the Hidden Lead re-evaluation popup.
- Re-evaluation history shows cross-list conversions separately and links to the converted destination record.

## Blacklist UI

- The company-name-only guidance now sits directly below the Domain or URL field in small text.
- The minimum company-name length guidance now sits directly below the Company Name field in small text.
- Removed the "Not a useful discovery source" Remark placeholder.

Migration 0193 is release-audit only; there is no schema change.
