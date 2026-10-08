# ScoutBox 0.11.128

## Resume-grounded re-evaluation

- Manual Opportunity, Hidden Lead, and Address Book re-evaluation now sends the complete Candidate Profile evidence bundle to the selected model route: saved Resume concepts, likely roles, deterministic Resume-grounded concepts/roles, full parsed text from every active Resume, and campaign steering/provenance when available.
- The same evidence rules apply to Local and Cloud re-evaluation. Full Resume text is authoritative evidence of capability; Candidate Profile priority fields are preferences, not capability whitelists, and low priority is not treated as rejection unless the text explicitly says to avoid/exclude/reject the work.
- Manual re-evaluation bypasses ScoutBox's ordinary compact first-filter input cap, so Candidate Profile and full active-Resume evidence are never silently trimmed before a Local or Cloud model call; an incompatible model fails instead of deciding from a partial CV.

## Candidate Profile vocabulary refresh

- Resume concepts are no longer limited to 40 and likely roles are no longer limited to 24. The supported limits are now 160 concepts and 80 roles, and the profile token editor scrolls cleanly for larger sets.
- Saved Candidate Profile concepts and roles now augment deterministic Resume extraction rather than replacing it, so omitted summary terms no longer erase technologies present in the source Resume.
- Resume concept extraction uses stricter grounding and rejects preference/constraint prose such as job-market, compensation, interview, funnel, or marketplace language.
- The Resume technology lexicon has been expanded across building automation/industrial protocols, cloud/data, full-stack, embedded/virtualization, communications, DevOps, payments, and related technologies.
- On the first 0.11.128 startup with an active Resume, ScoutBox queues a one-time Candidate Profile vocabulary refresh and records a profile vocabulary version marker after successful regeneration.

## Diagnostics

- Diagnostic exports now include the current Candidate Profile, full parsed text from active Resumes, and the effective search vocabulary needed to reproduce fit decisions.
- AI request diagnostics include scrubbed full prompt/output bodies for manual re-evaluations only, so support logs show exactly what candidate evidence reached the model and why the model returned its decision. Manual re-evaluation rows are prioritized before the diagnostic AI-log cap.
- General AI request bodies remain omitted from support diagnostics.

Migration `0200` is release-audit only; there is no schema change. The one-time Candidate Profile regeneration is queued by `seed_defaults` after normal startup migration/seed processing.
