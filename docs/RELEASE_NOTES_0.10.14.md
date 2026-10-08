# ScoutBox 0.10.14

- Removed separate LOCAL / CLOUD / LEGACY row badges. Discovery provenance now lives in the Fit score border: dashed for local/legacy and solid for Cloud-grounded entries. The Fit tooltip names the source and tells local entries to re-evaluate for better accuracy.
- Added Address Book re-evaluation using the same provider/model and all-matching fallback used by Opportunities and Hidden Leads. The toolbar action sits immediately before Add.
- Address Book Summary cells now show the Fit badge on the right, vertically centered.
- Dashboard, Resource Usage and Statistics share rolling 1 hr, 3 hrs, 6 hrs, 12 hrs, 24 hrs, 3 days, 7 days, 30 days and All Data ranges.
- Company Info employee counts are display-safe size bands only: 1–10, 10–20, 20–50, 50–100, 100–250, 250–500, 500–1,000 and 1,000+. Explicit headcount evidence in retained company research can repair stale small-number parses such as 22 versus 22,000.
- No database migration is required.

Routine future releases increment the patch component (0.10.15, 0.10.16, …) unless a deliberately major release is chosen.
