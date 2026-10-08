# ScoutBox 0.9.58

- Makes Add/New toolbar actions slightly larger than neighboring destructive actions across list screens.
- Moves Campaign Template Delete to the left of New Template.
- Aligns Hidden Leads Filter, Blacklist, Delete, and Add immediately after Mark as, with Hide failed URLs at the far right to match Opportunities.
- Improves Latest Filter Result display for historical filter jobs: recovers provider/model from item metadata when available, otherwise labels the result as a legacy filter instead of showing `— · —`.
- Historical filters that predate Fit recalculation now show `Not recalculated` rather than `— → —`.
- No database migration is required for 0.9.58.
