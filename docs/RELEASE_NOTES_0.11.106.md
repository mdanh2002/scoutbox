# ScoutBox 0.11.106

- Fixes generated Tracking Links so the configured **Blog base URL** is the actual public URL prefix.
- A configured base of `https://toughdev.com/blog`, short stem `/fatfs`, and generated suffix `integrating` now produces `https://toughdev.com/blog/fatfsintegrating` instead of `https://toughdev.com/fatfsintegrating`.
- Stores the public tracking path from the resulting URL (`/blog/fatfsintegrating` in the example), keeping external click-statistics synchronization consistent with the generated URL.
- Preserves all Tracking Link dialog sizing, alignment, DOCX scanning, suffix styling, date-filter and dashboard refinements from 0.11.105 and earlier releases.

Existing tracking links are not rewritten, so previously distributed URLs remain unchanged.

Next release: 0.11.107.
