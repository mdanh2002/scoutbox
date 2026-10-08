# ScoutBox 0.8.86 Release Notes

ScoutBox 0.8.86 is a small diagnostics and toolbar polish release on top of 0.8.85.

- Resource Usage shows the capture timestamp above the current CPU/RAM/GPU mini summary rather than beside the chart heading.
- AI Request detail suppresses Output when the request failed, so the error appears only once.
- Search Activity, AI Requests and Audit Trail no longer show redundant Search buttons; live/as-you-type search remains active.
- AI Request status filtering has enough width for labels such as `All statuses (1576)`.
- Searchable/autocomplete filter inputs omit trailing record counts from the editable selected text while keeping counts visible in the dropdown choices.
- Runtime / Model removes the redundant execution-path line (`Cloud Web`, `Local AI Discovery`, or equivalent), leaving provider/model as the primary cue.
- Dashboard Recent errors keeps its count badge immediately beside the heading instead of pushing it to the far right.
