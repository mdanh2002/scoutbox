# ScoutBox 0.10.64

0.10.64 is a focused patch on top of 0.10.63.

## Fixes

- Fixed Search Activity provider-type counts by classifying concrete UsageMetric rows with provider, category, stage and metadata instead of provider name alone.
- Preserved 0.10.63 forum browsing semantics: browse marketplace/listing pages before broad native search, avoid exact campaign technology combinations that are too narrow for forums.
- Fixed provider-type filtering so selecting Search Engine, Direct Search, Cloud Provider or Forum returns the matching rows reliably.
- Polished the re-evaluation **View Past Results** button so it closes the source dialog, clears focus, and no longer appears permanently pressed.

## Release numbering

Routine future releases increment the patch component from 0.10.64.
