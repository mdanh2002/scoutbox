# ScoutBox 0.9.34

## AI Requests response statuses

The old **Warning** status combined two materially different conditions: a model that returned no visible text, and a model that returned text that ScoutBox could tell was incomplete. 0.9.34 separates them.

- **Empty response** — the provider call completed without usable visible output.
- **Partial response** — output exists, but ScoutBox detects a provider output-token stop/truncation or an incomplete/malformed structured JSON response for a JSON-only task.

`Partial response` is used instead of the broader `Incomplete response` label because it makes clear that some model output was received even though it cannot safely be accepted as the complete structured result.

The AI Requests status filter, row tooltips/icons, detail popup and exported status values use the new statuses. Partial structured responses continue through the existing larger-cap retry and configured failover logic; the status is diagnostic and does not disable recovery.

## Upgrade migration

Migration `0076_v0934_ai_response_statuses` converts historical `warning` rows with truncation metadata to `partial_response`, converts the remaining historical warning rows to `empty_response`, and repairs older blank-completed/truncated-completed records where that state can be identified safely.

No Discovery routing, provider selection or token-budget defaults are changed in this release.
