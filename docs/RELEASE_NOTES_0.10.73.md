# ScoutBox 0.10.73

- Removed Boolean OR grouping from Reddit, forum fallback, direct-source fallback, and company-career search queries.
- Reddit/direct searches now issue separate compact rotated queries rather than one parenthesized hiring/job/remote/contract bundle.
- Forum native search remains browse-first and now uses only a tiny broad fallback query set.
- Forum browsing rotates enabled forums across runs, reports the current forum index in progress updates, and has a bounded stage time budget so one slow pass does not sit as “Possible stall” for 30+ minutes.
- Forum source metadata now records source attempts and stage time-budget details for diagnostics.
- No unrelated UI, scoring, Address Book, or chatbot behavior changes.
