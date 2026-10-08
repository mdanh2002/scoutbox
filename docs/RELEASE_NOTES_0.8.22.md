# ScoutBox 0.8.22

ScoutBox 0.8.22 is a maintenance release on top of 0.8.21. It fixes the remaining Market Studies inventory/summary regressions and tightens the Search Sources and Dashboard presentation.

## Market Studies
- Restores valid Market Studies rows that were still being hidden because the discovery `search_url` was incorrectly treated as the company target URL during list filtering. Search-engine provenance is no longer used to disqualify a resolved company lead.
- Legacy sentence-style summaries are replaced on display with a structured **Why selected** / **Potential use** rationale and queued for evidence-aware AI refinement. This removes old polished/random website snippets from the list view.
- New AI refinements are explicitly organization-focused: they explain what the company does, include products/services only when supported by evidence, connect the technical evidence to the candidate profile, and finish with a realistic outreach use.
- The detailed Market Studies background-job row is hidden from Dashboard activity. The normal automatic Hidden Market scan pulse remains the single scan-status indicator.

## Search Sources
- Yandex, Baidu and Naver continue to default to **Public Access** when no valid access mode is saved.
- The provider modal now renders **Public Access** as an explicit first option and client-side normalizes a blank legacy select value to `public`, preventing an empty Access Type field.
- Migration `0019_v0822_provider_public_default.py` re-normalizes blank/invalid persisted access types after upgrade.
- The Custom Domains explanatory hint is moved below the list and pager.

## Dashboard
- The Dashboard heading is moved down slightly so it aligns visually with the status/server controls on the right side of the top bar.

## Upgrade
Run the normal `./restart_scout_box.sh` upgrade path so migration 0019 is applied. Search credentials saved through the ScoutBox UI still apply without an additional restart.
