# ScoutBox 0.11.105

- Fixes Add Tracking Link failing to expand after DOCX scan results are returned.
- Removes the `!important` conflict that pinned the embedded editor to its compact 170px initial height.
- Makes the parent modal's measured iframe height authoritative so scan results can grow up to the available viewport height and then scroll when necessary.
- Adds a `ResizeObserver` to the embedded Tracking Link editor so actual content-size changes trigger a fresh height report, while retaining the existing mutation and window-resize fallbacks.
- Preserves the compact first-open dialog introduced in 0.11.104 and all 0.11.103 alignment, filename-display, date-filter and dashboard-region changes.

Next release: 0.11.106.
