# ScoutBox 0.8.115

## Statistics

- Added `Last 3 days` between Last 24 hours and Week.
- The period is a true rolling 72-hour window.
- Statistics charts use twelve six-hour buckets for this period so the first bucket does not expand backward to midnight.

## Email Configuration

- `Save folder assignments` now starts on the same horizontal axis as the Browse folder selector.
- Existing asynchronous IMAP Refresh, Detect and Generate Test Email behavior is unchanged.

## ScoutBox Chat DOCX export

- Increased normal transcript text size.
- Increased and reformatted timestamps into ScoutBox local time.
- Made `You` and `ScoutBox` message headers larger and visually distinct.
- Removed explicit blank spacer paragraphs between Markdown blocks and messages.
- Consecutive hard-wrapped prose lines are merged so Word performs its own wrapping.
- Tightened paragraph/list/heading spacing while preserving headings, lists, inline formatting and hyperlinks.
- Increased provider/model provenance size while keeping it visually secondary.
- Added support for escaped Markdown ScoutBox links such as `[Lead]\\(/cold-contact/123/)`.

No database migration is required.
