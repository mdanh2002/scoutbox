# ScoutBox 0.10.82

Focused hotfix for post-0.10.81 campaign throughput and UI polish.

- Prevents malformed outgoing search requests with multiple `site:` operators. Search query sanitizers now keep only the first normalized host-only `site:domain` constraint and drop later `site:` operators, so generated queries cannot become impossible combinations such as `site:facebook.com site:oracle.com ...`.
- Restores parallel Local Discovery scheduling. Automatic Local campaigns are no longer capped by `SCOUTBOX_LOCAL_AI_GENERATION_LANES`; that setting continues to limit short Ollama generation calls only. The scheduler now follows the discovery worker/auto-inflight capacity by default, with an explicit `SCOUTBOX_LOCAL_CAMPAIGN_INFLIGHT` override for installations that want a smaller campaign cap.
- Cleans the Campaigns list Status column. Retained Opportunity/Hidden Lead totals are no longer shown in Status, because those totals are historical and misleading beside a live run state. Active campaigns now show concise timing such as `For 18 min · since 14:32`; queued and stopping runs show similarly compact state timing.
- Removes the trailing spacer/message area from the Email History date-range toolbar, eliminating the odd empty boxed region at the end of the range controls.

No discovery scoring, persistence policy, application workflow, or Address Book promotion logic was changed in this release.
