# ScoutBox 0.10.96

## Company Info tooltip correction

- Keeps the existing Company Info icons and compact age/size display unchanged.
- When the badge is showing normal company age/size, independently resolved company-domain evidence remains supplemental tooltip-only information:
  - `Domain: example.com`
  - `Domain age: 15 years`
- When the badge is already using domain/RDAP age as its primary age signal, the tooltip no longer repeats the same registration evidence as an additional `Domain` / `Domain age` pair.
- Unknown/unresolved Company Info can still expose useful domain evidence when that is the only deterministic information available.

## General settings layout

- Moves **Send Test Digest Email** from the bottom action row to the right of the Digest time controls.
- Uses the same 420 px content width as the Daily digest recipient field so the test button aligns with that field's right edge.
- Narrows the Portal Root URL row to the same width as the recipient field.
- Integrates **Auto-detect** inside the Portal Root URL control area instead of extending the row farther to the right.
- Leaves **Save configuration** as the only bottom action in the General settings card.

## Daily Digest subject

- Changes only the count-group punctuation. The send date remains in square brackets; opportunity/lead/contact counts now use parentheses:
  `[13 Sep 2026] - Daily Digest (47 new opportunities, 14 new leads, 1 contact)`
- Scheduled and manually triggered digest messages use the same subject format.

## Compact Daily Digest operational tables

- Replaces CSS-grid metric blocks for **24-hour activity**, **Current settings**, and **Today's cloud budget** with real HTML tables.
- Uses three metric columns per row so these sections use horizontal space instead of expanding into long vertical lists.
- Adds inline table/cell layout styles and width attributes because email clients are substantially more reliable with traditional table markup than CSS Grid.
- The opportunity, hidden-lead and address-book detail tables are unchanged.

## Upgrade

No database migration is required for 0.10.96. Restart the web and worker services after replacing the source package.
