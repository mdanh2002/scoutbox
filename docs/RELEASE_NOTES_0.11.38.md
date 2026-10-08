# ScoutBox 0.11.38 Release Notes

## UI fixes

- Reworked the Statistics map into a lighter offline SVG world map with major country, region, ocean, and city labels.
- Renamed the Statistics map heading to **Global Activity Map**.
- Simplified the map layer controls so the checkboxes sit directly at the top-right without panel or chip borders.
- Standardized map markers into fixed-size map pins with different colors by layer instead of per-type glyph icons.
- Changed map labels from **Address Book** to **Contact** and from **Applications** to **Applications/Outreach**.
- Added hover tooltips for map pins using ScoutBox’s floating tooltip style.
- Added click-through map pins for Opportunities, Hidden Leads, Applications/Outreach, Contact, and Blacklist destinations.
- Increased the Statistics map zoom-control margin from the bottom-right corner.
- Moved Email History Rows and Export controls to the bottom-left footer.
- Moved Email History item counts to the top-right and page status to the bottom-right beside pagination controls.

## Validation

- Static regression checks were added for the new Statistics map and Email History footer layout.
