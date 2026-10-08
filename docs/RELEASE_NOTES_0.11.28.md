# ScoutBox 0.11.28

## Fixed

- Opportunity Re-evaluation Results now labels the popup as "All N stored runs" instead of "Last N runs".
- Hidden Lead Re-evaluation Results now labels the popup as "All N stored runs" instead of "Last N runs".
- Address Book Re-evaluation Results now labels the popup as "All N stored runs" instead of "Last N runs".
- Opportunity, Hidden Lead, and Address Book re-evaluation history popups now load every stored BackgroundJob row for their dataset instead of applying a last-10 or pre-sliced history cap.
- Latest-result cards continue to use the latest meaningful completed result, while the popup itself remains complete.

## Notes

No database schema migration is required.
