# ScoutBox 0.11.91

## Reliability and UI repairs

- Restores automatic, bounded Facebook Page title retries. Blank titles retry without a user click and settle after four attempts within a bounded 20-minute window; the status returns to the old borderless clock icon.
- Repairs Tracking Link article-title handling so Markdown-link or bare-URL placeholders are never used as the displayed title. Suspicious stored titles are refreshed asynchronously from live page metadata, preferring normal document metadata and heading text when the HTML `<title>` itself is link-shaped.
- Tightens the Tracking Links Clicks column and contains the First/Last and Created timestamps so the Created column no longer leaks outside its cell.
- Adds an in-button spinner and disabled/loading state while DOCX link scans are running, and restores stable four-column sizing and pagination/list behavior for scan results.
- Fixes Search Activity widths after the Date-column reorder; Results no longer inherits the old wide Query sizing and the desktop table no longer creates a needless horizontal scrollbar.
- Restores Discovery Activity / Discovery Source Activity stability by rendering their compact Results columns server-side rather than reordering table cells after the shared list-table sorter initializes.
- Reworks Usage Events into `Workload` (Events, Requests, Pages) and `AI Usage` (Input, Output, Reasoning, AI Web) columns, with Errors before Avg Latency.

## Versioning

Every shipped build after 0.11.91 advances the patch number sequentially, including small fixes: 0.11.92, 0.11.93, 0.11.94, and onward.
