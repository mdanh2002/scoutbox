# ScoutBox 0.10.100 release notes

## Company Info domain creation display

- Fixes building Company Info badges that omitted the small globe/domain creation year even though ScoutBox already had verified domain-age evidence.
- Rendering now recovers domain registration fields from both the structured Company Info payload and legacy/partial `Domain Age` / `Domain created` facts.
- Tooltips continue to show `Domain: ...` and `Domain created: YYYY (N years)` whenever those facts are available, independently of company age and employee-size information.
- The compact badge still uses the 12px vector SVG globe with geometric-precision rendering introduced in 0.10.99.

## Safer domain reuse

- Company-domain cache reuse now bridges harmless spacing variants such as `ExtraHop` and `Extra Hop`.
- Compound company names require a strong full-name/domain correspondence. A partial domain such as `extra.com` is no longer accepted for `Extra Hop` just because the `extra` token matches.
- Existing cached registration evidence is reused before another RDAP request is attempted.

## Existing-data repair

- Migration `0120_v010100_company_domain_evidence_reuse` scans already-stored Company Info and company-domain cache data, identifies verified registration evidence by normalized company identity, and copies it to sibling records that were missing it.
- The repair is local-only: it performs no web, RDAP, Local AI, or Cloud AI calls during migration.
## Post Age tooltip typography

- Post Age hover details keep the same multiline tooltip style as Company Info and Remote.
- Tooltip text explicitly renders at normal weight instead of inheriting the bold weight used by the compact Post Age cell value.

