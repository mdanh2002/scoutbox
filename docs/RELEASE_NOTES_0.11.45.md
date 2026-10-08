# ScoutBox 0.11.45

## Changes

- Improved Global Activity Map label density so major city/country labels overlap less in interactive view and exported PNGs.
- Kept multi-record/location map pins fixed-size while making them about 130% larger for visibility.
- Reworked high-resolution PNG export to render the offline SVG at export resolution before drawing pins.
- Scaled exported pins with export resolution so map pins render as proper location pins instead of broken tiny glyphs.
- Kept map control hover effects stable without shifting.
- Aligned Email History item count with page status/navigation and removed bold weight from the count.

## Validation

- Static regression checks for 0.11.45 pass.
- Carry-forward checks for 0.11.44 pass.
- No external map service is used.
