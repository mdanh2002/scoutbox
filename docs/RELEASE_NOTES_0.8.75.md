# ScoutBox 0.8.75

## Cloud Web research and routing

- Cloud Web uses one explicitly selected enabled Cloud provider plus distinct Primary and Secondary web-capable models. Auto-select is capability-first rather than price-first; Test Selection checks JSON and web-search capability, while Test Discovery remains the full research diagnostic and can be reopened while it is running.
- Cloud research prompts are short, role-focused and use AI-selected CV evidence without dumping the entire profile/campaign configuration. Source-Guided search planning remains separate.
- Verified Cloud Opportunity fields are preserved through dedupe and ingestion. Cloud result status is restored to Apply Now / Review / Information Only from the verifier recommendation/fit instead of defaulting every Cloud result to New.
- Blacklisted website domains are enforced again after exact-URL resolution and at final persistence. Blocking a website from an Opportunity or Hidden Lead now creates an Always/global blacklist rule so the same domain cannot reappear on another discovery surface.

## Opportunity, lead and contact quality

- Opportunities still require one concrete item-level role URL; generic careers/ATS pages are evidence only and cannot be final Opportunities or Hidden Leads.
- Cloud Hidden Leads require a separate direct-outreach qualification pass. Blogs, documentation, job platforms/ATS infrastructure, generic career pages and non-actionable resources are rejected. Adult/sexual-content targets are hard-filtered before persistence.
- Cloud URL inspection records 404/410 status without deleting an otherwise useful Hidden Lead; list rows show a compact warning. Opening an Opportunity or Hidden Lead URL marks it read.
- Address Book contacts from Cloud research use validated email ownership, practical mailbox-derived salutation names, company summaries, and actual company/HQ locations. Administrative privacy/GDPR/EEO/compliance addresses are rejected while legitimate recruiting mailboxes may be retained.

## Location, Post Age and ranking

- Company location is now explicitly separate from remote-work eligibility. Labels such as Remote worldwide, Anywhere, Home based, Global and Distributed are not shown as company location; unresolved company location remains blank.
- Cloud Post Age can classify a current role as Ever-green when grounded evidence indicates a long-running, rolling, standing or repeatedly reposted vacancy. This does not mean closed/ineligible. Cloud research may use archive.org as ordinary web evidence, but ScoutBox never probes the archive.org API directly. Source-Guided freshness behavior is unchanged.
- Pay threshold, company size and engagement type remain soft ranking preferences and never suppress a valid remote niche result merely because values are missing or less preferred.

## Interface and diagnostics

- Opportunity/Hidden Lead list Source columns are hidden. Address Book includes a company Summary column and company location/flag below the company name.
- Hidden Lead Summary and other main list cells are vertically aligned; Hidden Lead notes use a compact three-line preview.
- CPU, RAM & Tokens uses one chart scale with raw current values shown beside the chart. AI Request JSON is syntax-highlighted in previews and rendered as a collapsible tree in the popup while copy/export retains exact raw payloads.
- Campaign custom-instruction dates use DD/MM/YYYY presentation. Cloud runs hide Source-Guided query rotation. Run History exposes Cloud and Source-Guided accounting.
- Post Age refresh and evidence presentation are cleaned up, with concise dated evidence rows and full hover/detail reasoning.
- ScoutBox Disk Usage hides detail components that round to 0 MB while retaining them in the exact total.

## Database

This release includes migration `0041_v0874_cloud_selection_contacts_lead_status.py`, which adds explicit Cloud provider/model selection and company-summary/location/contact/lead-status support introduced during the 0.8.74 development cycle.
