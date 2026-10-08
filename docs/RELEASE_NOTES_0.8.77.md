# ScoutBox 0.8.77

0.8.77 is a focused quality and reviewability update on top of 0.8.76.

- Cloud AI limits default to 100 web searches/run, 50 discovery candidates/run, 250 deep-research candidates/run, 2,000 Cloud requests/day, 2,000,000 output+reasoning tokens/day, and 500 page-view recoveries/day. Exhausted quotas are surfaced in ScoutBox Activity with links to the relevant settings.
- Address Book performs a one-time upgrade cleanup that keeps the best active contact per company, and runtime contact insertion prefers a better personal/specialist address over weaker generic duplicates.
- Opportunity and Hidden Lead duplicate reconciliation remains active across and within the two lists. Opportunity, Hidden Lead, and Application list/detail views expose their internal ScoutBox IDs.
- Hidden Lead URL health is shown compactly next to the company name; Opportunity URL health remains next to the role/contact link.
- Cloud Web campaign runs can prefer or exclude company countries. Opportunities, Hidden Leads, and Address Book add one-country autocomplete filters.
- Post Age adds the ~2 weeks bucket and combines age with confidence so younger, better-supported results are visually stronger; stale or uncertain results use Older / uncertain.
- Chatbot provider selection now drives an explicit model dropdown, uses one provider/model only, defaults to 10,000 answer tokens, and distinguishes a valid local model from an unconfigured chatbot.
- Dashboard new errors show a counted badge and bold Dashboard navigation state. They are acknowledged after 30 minutes from opening Dashboard, when the Errors KPI is clicked, or when Resource Usage is viewed.
- Resume Create Campaign actions, Cloud Web model configuration, campaign execution summaries, and related compact UI areas receive layout cleanup.
