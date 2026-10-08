# ScoutBox 0.11.8

## Hidden Leads minibrowser admission gate

- Adds a Hidden Leads-only bounded minibrowser admission pass before creating a new Hidden Lead.
- Reviews the identified URL, homepage, and likely first-party organization pages such as About, Contact, Services, Products, Team, Careers, and Jobs.
- Asks the configured AI model to decide whether the candidate is a real organization/person/company the user would plausibly want to talk to, track, or contact.
- Enforces a deterministic score cutoff: admit at 75+, review band starts at 55, reject below cutoff.
- Favors small/specialist companies when relevance and contactability are similar.
- Rejects content-only blogs, directories, job boards, marketplaces, documentation-only pages, generic software pages, SEO/listicles, and candidates without a concrete organization identity or practical contact reason.
- Stores admission evidence and scoring metadata in Hidden Lead `ai_state` when a lead is admitted.
- Records rejected candidates as `hidden_lead_minibrowser_admission` discovery-filter usage metrics.
- Leaves Opportunities and Address Book unchanged.
