# ScoutBox 0.10.97

## Company Info tooltip consistency

- Keeps the existing Company Info icon choice and compact age/size display unchanged.
- Uses the same tooltip field layout for both the normal company maturity/building icon and the domain-age/globe fallback.
- Whenever available, the tooltip includes:
  - `Company: Example Company`
  - `Company age: 10+ yr`
  - `Company size: 100–250 employees`
  - `Domain: example.com`
  - `Domain age: 15 years`
- Domain-derived fallback badges no longer use a separate `Domain age (registration/RDAP)` line. They use the same `Domain` / `Domain age` lines as every other Company Info tooltip.
- A company name can fall back to the resolved Company Info payload/facts when the row-level company value is temporarily blank.
- Facts that are not available remain omitted rather than guessed.

## Portal Root URL layout

- Keeps the overall Portal Root URL control aligned to the 420 px Daily digest recipient field width.
- Shortens the URL textbox so it ends before the Auto-detect button.
- Adds an 8 px gap between the textbox and Auto-detect button.
- Removes the absolute-positioned overlay/padding technique that could visually overlap the textbox border and button.
- On narrow screens the controls may wrap safely rather than overlap.

## Upgrade

No database migration is required for 0.10.97. Restart the web and worker services after replacing the source package.
