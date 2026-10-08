# ScoutBox 0.9.43

## Hidden Leads Company Info display

Restored the original Company Info list semantics for Hidden Leads. The column displays only company/domain age and employee count/range. When neither signal is available, it displays `?`.

The generic **Info** fallback badge introduced in 0.9.41 has been removed. Other company-profile facts remain stored and available to the existing detail/research surfaces; they are simply not represented by the compact Company Info list badge.

## Unchanged

- The 0.9.41 Cloud qualification fields that can populate company size and founding information remain in place.
- `cloud_persistence_rejections` diagnostics remain in place.
- Opportunity discovery, filtering, validation, scoring, persistence, and presentation are unchanged.
- The 0.9.42 statistics-label cleanup is retained.
- No database migration is added.
