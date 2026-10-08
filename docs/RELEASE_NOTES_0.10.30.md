# ScoutBox 0.10.30

0.10.30 fixes Opportunity advanced Post Age filtering and improves its age-range controls.

- Fixes the advanced Post Age filter so rows rendered as `?` are always treated as `Unknown / Others`, even when retained evidence still contains an internal `age_days` estimate.
- Centralizes the Opportunity Post Age display-label calculation so list presentation and advanced filtering use the same visibility contract.
- Adds `<2 months` and `<3 months` Post Age choices before `Older`.
- Makes age thresholds cumulative in the UI and backend: selecting `<1 month` automatically includes `<1 week` and `<2 weeks`; selecting `<2 months` or `<3 months` includes every younger threshold.
- Unchecking a younger threshold also clears larger cumulative thresholds so the checkbox state cannot become contradictory.
- Simplifies the active filter summary with group labels and collapses cumulative age selections to the largest selected range, e.g. `Remote: Fully Remote · Post Age: <1 month, Evergreen`.
- Adds a direct external-link icon at the end of Opportunity summaries, matching the Hidden Lead affordance, without changing existing role/domain link behavior.
- Adds the same summary-row link affordance to Address Book entries, opening the HTTPS homepage for the domain portion of the contact email.
- Preserves the 0.10.29 dialog behavior: unrestricted groups open fully checked, existing selections are restored, Reset appears only for an active advanced filter, and Apply Filter is disabled when any group has no selection.
- No database migration is added.

Routine future releases increment the patch component.
