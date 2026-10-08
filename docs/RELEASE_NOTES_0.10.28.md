# ScoutBox 0.10.28

0.10.28 is a migration-reliability hotfix for 0.10.27.

- Fixes PostgreSQL upgrade failure `cannot CREATE INDEX "portal_opportunity" because it has pending trigger events`.
- Keeps 0083 as schema-only work (origin-Campaign fields plus Jitter-field removal).
- Moves the historical origin-Campaign/Naver-title data backfill into 0084 so PostgreSQL completes FK index creation before any backfill updates generate deferred trigger events.
- The 0084 backfill is conservative and idempotent, so it is safe both for installations where 0.10.27 failed and for installations where 0083 already completed.
- No volume reset, database restore, or manual migration fake is required. Restart with 0.10.28 and normal migrations can continue.

This build retains all 0.10.27 functional changes: Naver title cleanup, origin-Campaign filtering, scheduled URL-health checking with the 3-month cutoff, Local-vs-Cloud scheduling semantics with Jitter removed, Recycle Bin URL links, Opportunity advanced filters, and Ad hoc Actions token accounting.

Routine future releases increment the patch component.
