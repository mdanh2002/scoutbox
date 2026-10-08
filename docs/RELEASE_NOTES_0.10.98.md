# ScoutBox 0.10.98

## Company Info domain tooltip repair

This is a focused correction for Company Info rows whose age/size research had completed but whose tooltip still omitted the company domain and registration age.

- The existing building/globe icons and compact cell display are unchanged.
- The tooltip now uses all already-available official-domain evidence, not only `domain_age_domain`. It can read the normalized company website/domain fields and verified Website/Domain facts immediately.
- A matching official source URL can supply the tooltip domain before the background RDAP backfill finishes; job-board/ATS domains remain excluded.
- When a registration date is already stored, the tooltip derives the human-readable Domain age even if an older record has no `domain_age_label`.
- Company Research now preserves an official `website` / company-domain value returned by research instead of discarding it during normalization.
- Company-research prompts explicitly request the verified official website so new records retain this evidence.
- Existing completed Company Info rows without a resolved domain are re-queued for deterministic domain maintenance on upgrade.
- Deterministic maintenance can perform a tiny bounded public search for the official company site when existing stored evidence has no usable domain, then performs the existing RDAP lookup. This does not invoke Local AI or Cloud AI.
- Missing domain evidence remains retryable instead of being silently treated as permanently complete.

A database migration marks affected existing rows for the bounded background repair. Restart the web, worker, and scheduler/beat services after upgrading.
