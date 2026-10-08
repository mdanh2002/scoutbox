# ScoutBox 0.8.99 release notes

ScoutBox 0.8.99 focuses on Local AI discovery quality, historical Opportunity-summary repair, Hidden Lead URL-health completeness, and source traceability in Applications & Outreach.

## Opportunity summaries and historical rebuild

- Opportunity list summaries keep the short `keywords — why it fits` format but recognize more concrete low-level signals, including OpenBMC, TrustZone/TEE, BSP/Device Tree, NVMe/SSD/NAND, IOMMU/VFIO/SR-IOV, eBPF, kernel live patching, ELF/PE-COFF, disassembly/decompilation, and VxWorks/ThreadX.
- Upgrade migration `0057_v0899_rebuild_relevance_health.py` recomputes `list_highlight` for existing Opportunities using stored title/JD/AI source evidence.
- If an older Opportunity has an empty visible description but its saved AI summary still contains the original fetched `source_text`, the migration restores that source-backed description before rebuilding the compact list summary.

## Local AI discovery false-positive control

- Multi-employer job boards now use a stricter relevance gate. Search snippets, campaign wording, navigation, and related-job widgets cannot by themselves make an unrelated occupation relevant.
- On those boards, ScoutBox requires role-title evidence or stronger grounded evidence in the primary portion of the fetched job description.
- One noisy job-board brand is capped at the best 12 candidates per normal Local AI run before expensive fetch/enrichment work. Direct employer and ATS domains are not capped by this rule.
- The upgrade suppresses obvious historical Local AI job-board false positives that have neither a technical target-role title nor a rebuilt niche summary, while preserving Cloud discoveries, manual/imported rows, and anything already linked to an Application.

## Hidden Lead URL health

- Hidden Market discovery now persists the HTTP status from the page fetch it already performed while qualifying a lead. A newly created lead can therefore show its `200` badge immediately instead of waiting for a separate health task.
- Existing leads with a URL but no recorded status are made eligible for a fresh background health check during upgrade, and the Hidden Leads list queues up to 100 stale/missing checks per visit.

## Applications & Outreach source pointer

- Application context now contains an **Original record** field.
- Outreach created from Hidden Leads links back to the original Hidden Lead. Normal applications link back to their originating Opportunity.

## Upgrade

Keep your existing `.env` and Docker volumes, replace application files with this package, then run:

```bash
chmod -R +x *.sh
./restart_scout_box.sh
```

The normal restart applies migration `0057_v0899_rebuild_relevance_health.py` automatically.
