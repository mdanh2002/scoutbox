# ScoutBox 0.11.122

## Cloud re-evaluation quality gate

- Hidden Lead Cloud re-evaluation now requires a credible current buyer/need signal for outside technical help, contractor/developer/partner/outsourced expertise.
- Mere technical relevance, contact/sales pages, or a company selling similar technical services do not qualify as a buyer signal.
- Hidden Leads without a need signal normally recycle, with a deliberately rare exceptional-interest escape hatch requiring a specific unusual technical activity/problem and >=95 confidence.
- Opportunity Cloud re-evaluation now verifies work arrangement/geographic eligibility. Clearly incompatible restricted/onsite roles recycle unless relocation/visa sponsorship is available or the role passes a deliberately rare exceptional-interest test.
- Existing high-confidence Hidden Lead → Opportunity and Opportunity → Hidden Lead correction paths remain in place and run before final recycle decisions.
- Address Book re-evaluation is unchanged.
- Local GPU/Ollama re-evaluation is unchanged.

## Editable Cloud decision policy

- Opportunity and Hidden Lead re-evaluation dialogs show a short editable `Cloud re-evaluation instructions` field only for Cloud providers.
- The field changes the actual policy text sent to the Cloud re-evaluation request.
- Edited text is persisted as the default for later re-evaluations, so decision policy can be tuned without rebuilding ScoutBox.
- Core JSON/schema and safety/parsing instructions remain internal and are not exposed in the editable prompt.
- Removed the older long explanatory re-evaluation helper copy from the Opportunity popup.

## Search query repair

- Generated queries with an unmatched double quote are repaired before provider dispatch instead of sending malformed syntax such as `reverse engineer "nos parcele Portugal`.
- Repeated generated terms are still deduplicated.
- A bare company domain in generated search text is normalized into a `site:domain` scope. This turns combinations such as `Phoenixtech Phoenixtech phoenixtech.com` into the intended compact company-scoped query instead of repeating the company/domain as free text.

## Hacker News Who is Hiring

- The Algolia `hitsPerPage=20` lookup is treated only as monthly thread discovery; it is not a 20-job cap.
- The newest available monthly Who is Hiring thread now has all of its top-level comments enumerated before ScoutBox applies its local relevance scoring/candidate cap.
- The old early comment truncation is removed, preventing later comments in large monthly threads from being permanently starved.
- ScoutBox stops after the first live newest monthly thread per pass, avoiding multiplication of full-comment traffic across several historical months.
- Other direct adapters that are intentionally first-page bounded were audited but not expanded in this release, to avoid an unrelated traffic-volume change.

Migration `0194` adds only the two persistent Cloud re-evaluation prompt settings plus the release audit entry.
