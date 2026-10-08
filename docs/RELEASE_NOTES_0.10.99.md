# ScoutBox 0.10.99 release notes

## Company Info domain creation display

- Building/company badges keep the existing company-age and employee-range lines.
- When domain registration evidence is available, a small inline SVG globe plus the domain creation year is added as the last line, for example `globe 1997`.
- The mini globe is vector SVG rendered with geometric precision at 12px so it stays clear at dense-list size rather than relying on a raster asset.
- Domain-only Company Info badges keep the existing large globe icon, but the line below it now shows the domain creation year instead of `N yrs`.
- Company Info tooltips continue to show available company facts independently and now describe domain registration as `Domain created: YYYY (N years)`.
- Exact RDAP registration dates are preferred. Older records that only have a stored domain-age count derive the best calendar-year display from that evidence.

## Remote and Post Age tooltips

- Remote hover details now use ScoutBox's multiline tooltip surface, matching Company Info.
- Remote status, confidence and reason are placed on separate labelled lines.
- Post Age hover details now use the same multiline tooltip surface rather than the browser's native title tooltip.
- Post age, source, confidence and reason are placed on separate labelled lines.
- The older middle-dot concatenation used by Remote tooltips has been removed.

## Upgrade

No database migration is required. Replace the source package and restart the ScoutBox web/worker services so updated templates/static files are loaded.
