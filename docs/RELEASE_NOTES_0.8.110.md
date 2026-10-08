# ScoutBox 0.8.110 Release Notes

Released 26 August 2026.

ScoutBox 0.8.110 focuses on Local AI Discovery precision, chatbot context efficiency, AI-request JSON viewing, Resource Usage presentation, and IMAP dark-theme readability. It does not add a new database migration; `0068_v08108_usage_visibility_salary_cleanup.py` remains the latest required migration.

## Local AI Discovery quality

The Local AI Discovery pipeline now has a semantic quality gate before persistence. This is deliberately local-only and uses the configured Ollama `first_filter` route.

- Fetched pages are classified into one of: `job_opportunity`, `contract_project`, `company_hiring_signal`, `company_outreach_target`, `editorial_seo`, `documentation`, `directory_job_board`, or `other`.
- Only a concrete `job_opportunity` or `contract_project` with adequate confidence, candidate relevance, and actionability can proceed directly to Opportunity persistence.
- Salary guides, job-description templates, career/SEO pages, news/articles, product documentation, tutorials and generic listing/search pages are explicitly non-opportunity page purposes even when they contain matching technical/job keywords.
- Generic phrases such as `job description`, `responsibilities`, `requirements` and `qualifications` are no longer treated as sufficient structural proof that a page is a live vacancy.
- Strong structural evidence includes `JobPosting` structured data, a recognized ATS item, a concrete job/career URL, or explicit apply/hiring language.
- Ambiguous pages that lack strong structural evidence receive a second exact-role local search-provider corroboration pass. A separate employer/ATS item must corroborate the role before the ambiguous page can become an Opportunity.
- Local profile relevance now uses the stricter fetched-page relevance rule for all local search results, reducing query/snippet contamination and one-keyword false positives.
- Local Hidden Leads require an explicit semantic `lead_actionable` decision and a company-hiring/direct-outreach page purpose. A technically relevant article or documentation page is not enough by itself to create a lead.
- The pre-persistence local review supplies fit/recommendation/remote data to the new Opportunity so ScoutBox does not immediately spend another redundant Ollama classification call on the same page.

### Cloud Web compatibility

Cloud Web Discovery is not passed through the new local page-purpose, local corroboration, or local lead-actionability gates. Its existing cloud-native discovery, research, resolver, qualification and persistence behavior remains unchanged.

## Ask ScoutBox context

- Complete Opportunities and Hidden Leads remain represented in chatbot context, but the prompt is progressively compacted instead of injecting every full description, evidence blob and company-research object.
- The compact index contains every current record and a small schema, while `focus_details` carries richer evidence for the records most relevant to the current question.
- The minimum profile omits long per-row summaries rather than accidentally expanding them. This fixes the case where 28 Opportunities + 87 Hidden Leads was estimated at about 465k tokens against a 6k chatbot limit.
- Candidate preferences/company information are also compacted. Applications, contacts and campaign history are supplementary and may be omitted only in the minimum profile; Opportunities/Hidden Leads are never silently dropped.
- If even the minimum complete index genuinely cannot fit the configured model, ScoutBox still fails closed rather than making a claim from an incomplete subset.
- Model-generated record names are post-processed into verified ScoutBox detail links when a matching Opportunity/Hidden Lead is found.

## Resource Usage

- The top-level `Reasoning Tokens` metric card remains visible.
- The selected-period `Cloud Usage — …` panel no longer repeats a separate `Reasoning Tokens` row.
- `Output Tokens` remains visible, and `Output + Reasoning Safety Usage` remains the combined counter used for the existing daily hard limit.

## AI Request JSON viewer

- `View raw` is displayed only when the Input/Output parses as JSON.
- JSON wrapped in a Markdown fence such as ````json ... ```` is unwrapped before parsing and therefore gets the normal tree viewer.
- Expand/Collapse controls appear only for valid JSON tree mode and disappear in raw mode.
- Copy remains available regardless of payload type.
- Raw JSON is syntax-highlighted; non-JSON text is rendered as plain escaped text without misleading JSON controls.

## IMAP Browser

- The sandboxed HTML email preview applies a dark ScoutBox preview background and forces nested message text to a readable light foreground, including legacy `<font>`/inline-color markup.
- Nested email background colors/images are neutralized inside the preview to avoid dark-on-dark or dark-on-transparent text while retaining links in a distinct readable color.
- The HTML remains isolated from the parent ScoutBox page by the existing iframe sandbox.

## Compatibility

Existing 0.8.109 installations can retain `.env`, PostgreSQL/Redis/media volumes and all current records. Replace application files and run `./restart_scout_box.sh`.
