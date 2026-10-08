# ScoutBox 0.8.97

## Changes since 0.8.96

- Opportunity summaries now require specific technical evidence. Arrangement-only and broad-stack filler is rejected, while details such as UEFI/BIOS, EDK II, Secure Boot, BMC/IPMI, PCIe/ACPI, QEMU/KVM, Zephyr, dsPIC and reverse engineering are promoted.
- Existing Opportunity `list_highlight` values are repopulated during upgrade under the stricter rule; unsupported rows intentionally remain blank.
- Cloud Web and fit/remote prompts explicitly allow an empty highlight when no concrete differentiator is supported.
- Daily digest output is capped at the top five new Opportunities and top five new Hidden Leads from the rolling previous 24 hours. Ranking favors remote suitability, fit, post freshness and Company Info completeness; rows include a short source-backed description excerpt plus source/company/contact details.
- Empty “no contacts / no application changes” digest sections were removed. Error/limit sections are emitted only when useful.
- Rebuild Missing AI Data now defaults to Last 24 hours (`now - 24h`), not “Today” from local midnight. Legacy `today` payloads map to the new 24-hour behavior.
- Domain-age fallback now chooses a company-controlled domain and rejects LinkedIn/job-board/ATS domains as well as unrelated recruiter/contact domains when a company name is available. The selected domain is stored as `domain_age_domain` for traceability, and Company Research cache keys use the company domain rather than the job-post host.
- Upgrade cleanup preserves trustworthy first-party domain ages, shares retained trustworthy ages across records for the same company where possible, and removes unsupported platform-derived ages instead of displaying misleading values. Records whose old age cannot be safely reused are marked for a normal Company Research repair pass so RDAP age can be repopulated from a corrected company domain without doing network I/O inside the migration.
- Blank Address Book company summaries are backfilled from retained Company Info / Hidden Lead evidence. New automatic Cloud Web and mailbox contacts reuse retained source-backed company context when available.
- Added a synchronized viewport-level horizontal scrollbar for wide list tables while their native bottom scrollbar is off-screen.
- Standardized Opportunity-list question-mark sizing for unknown Company Info, Remote, Post Age and uncertain Fit states.
