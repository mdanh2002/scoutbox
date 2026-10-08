# ScoutBox 0.10.16 release notes

ScoutBox 0.10.16 is a migration-free chatbot clarity, compensation matching, and UI resilience release.

- Ask ScoutBox keeps the shared **Typing…** indicator anchored after the newest submitted question while queued or server-side work remains, so follow-up questions never look ignored.
- The chatbot now receives a concise authoritative ScoutBox capability catalog, including **Diagnostic Data Export** under **Configuration → Maintenance → Export Diagnostic Data**, and recognizes feature/how-to/export questions as system questions.
- Hidden Lead summaries uppercase their first alphabetic character at presentation time without rewriting stored text or lowercasing acronyms.
- Address Book re-evaluation uses the concise Dashboard activity label **Re-evaluating…**, avoiding an unnecessary wrapped first column.
- KPI-style counts on Dashboard, Statistics, and Resource Usage share million/billion/trillion compaction, retain exact values in hover titles, and have defensive overflow handling. Current Resource Usage request/token values use the same compaction.
- Salary comparison now normalizes modern and legacy compensation preferences through one helper, so a visible legacy USD/year preference is also honored by enrichment, filtering, and the opportunity salary tooltip. Tooltips clearly separate the configured pay preference result from the salary source.
- Local AI Fit score badges keep a dashed border on hover, focus, and active sort states; the dash thickens instead of receiving a second offset solid ring.

No database migration is required.

Routine future releases increment the patch component on the 0.10.x line unless a release is deliberately designated as major.
