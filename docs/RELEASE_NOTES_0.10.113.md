# ScoutBox 0.10.113

- Fixes Jobicy role-location fidelity for recruiter-region/country labels and re-runs location repair after upgrade so current role locations are not contaminated by related-job cards.
- Changes the newest Post Age bucket from `~ 3 days` to `< 3 days`, with migration normalization for retained records.
- Rebuilds Focus labels independently for Opportunities, Hidden Leads, and Address Book. Company/contact lists now generate company-domain labels rather than reusing open-role function labels from Opportunities.
- Keeps `Worldwide` valid for opportunity eligibility only; removes it from company, lead, and address-book location displays.
- Improves direct/local email-contact extraction and prevents `Contact via email` when no concrete assignable email address is stored.
- Fixes Search Activity text search so it matches the Query text shown in the UI, including direct-stage labels such as `company_career_direct_search`.
- Fixes diagnostic export busy-state clearing so the spinner stops as soon as the iframe download completes or the download token cookie is observed.
