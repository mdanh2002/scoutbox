# ScoutBox 0.11.76

## Discovery Markets

- Fixes Search markets so rows are actually hidden while typing and restored when the query is cleared.
- Sorts displayed markets alphabetically with Worldwide Remote last.
- Moves the multilingual explanation and enable checkbox above market search, with clear English-primary behavior.
- Replaces native language datalist behavior with ScoutBox's searchable, keyboard-accessible token picker.
- Aligns Market coverage and Exploration strength with their labels and moves Additional languages to its own aligned row.
- Makes Even, Balanced, and Adaptive coverage strategies operational with a rotating fairness anchor, recent market evidence, explicit fallbacks, and run diagnostics.
- Makes Additional languages produce real translated-query work even when a language is not native to an enabled market.
- Applies Low/Balanced/High multilingual limits consistently to Source-Guided and Cloud Web discovery.
- Allows explicitly tagged multilingual Source-Guided results to proceed only after a faithful English interpretation; all normal relevance, opportunity, freshness, remote, and selectivity gates still apply.

## Search Sources

- Aligns source checkboxes and content into responsive, consistent columns without changing source-selection behavior.
- Adds market-routed Major job site presets for Germany, France, Spain, Portugal, the Netherlands, Italy, Poland, the Czech Republic, Denmark, Sweden, Norway, Finland, Japan, South Korea, Brazil, and Mexico.
- Adds matching Discovery Markets and native-language metadata for those countries.

## Verification

- Adds 0.11.76 behavioral regressions for market strategy fallbacks, fair rotation, strength caps, rotating Additional-language assignments, source alignment, live filtering, and the expanded source catalog.
