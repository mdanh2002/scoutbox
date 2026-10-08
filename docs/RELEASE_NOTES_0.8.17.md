# ScoutBox 0.8.17 release notes

0.8.17 is a runtime/UI reliability update over 0.8.16.

- Search Sources is fail-soft if provider diagnostics/history fail, while retaining the last 20 provider requests and errors for debugging.
- Market Studies summaries are generated as a single concise sentence at ingestion; migration 0015 rebuilds existing summaries from stored evidence. Grid-level outreach controls and manual-scan UI are removed while automatic scanning remains enabled.
- Dashboard action icons, error coloring, local Recent Activity refresh, search-window navigation and host facts are tightened for consistency.
- Resource Usage keeps memory in MB/GB on a second chart axis, fixes GPU hover fallback, refreshes every 15 seconds, and aligns live tags and provider charts.
- Saved campaigns and query/cache surfaces are scrubbed again for legacy `generic full stack` and unary search-engine exclusion syntax; outbound search requests remain exclusion-free and ScoutBox applies negative filtering after retrieval.
- Applied-role import places Sync Mailbox alongside bulk actions and removes the duplicate card title.
- ScoutBox chat is keyboard-first: Enter submits, Shift+Enter inserts a line break, a Typing indicator is shown, and up to five outstanding questions are queued safely.
