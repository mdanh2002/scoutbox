# ScoutBox 0.9.21

## 32 GB local-model auto-detection cap

- When detected host RAM is 32 GB or less, automatic local model selection uses a maximum generation-model size of 7B.
- The same ceiling is used by **Automatic local** routing and **Optimize for Local** presets.
- If no 7B model is installed, ScoutBox chooses the strongest suitable installed model below that ceiling.
- Manual model selections are not changed or restricted.
- Hosts above 32 GB keep the previous automatic 12B ceiling.

No database migration is introduced in 0.9.21.

### Responsive AI Discovery and Cloud cost routing refresh
- Prevented AI & Discovery routing controls from widening the page: model selectors now shrink within the content pane, the table uses a constrained layout, and Local AI routing reflows into readable stacked records on narrow screens.
- Cloud Web Auto-select now performs a live Internet-research capability probe before it proposes either model.
- Cloud Web can use an economical verified Secondary model for routine high-volume stages including page summarization, while URL discovery and heavier tailoring/inference remain on the stronger Primary lane with failover in the opposite direction.
- Added an About > Redis Example learning section with read-only Docker/redis-cli diagnostics, queue depth, persistence, memory, slowlog, key inspection, and Django broker checks.
