# ScoutBox 0.9.50

## Opportunity list summary specificity

- Replaces long generic Opportunity-list recommendation prose with short, JD-grounded technical cues.
- The list summary prefers concrete technologies, subsystems, tools, architectures, protocols, responsibilities, or documentation audiences actually present in retained role evidence.
- Generic phrases such as “highly relevant”, “actionable”, “strong match”, “clear opportunity”, and “aligns with the candidate” are no longer accepted as useful list highlights.
- New AI-generated highlights target roughly 8–16 words (20-word hard instruction limit), while a deterministic retained-evidence fallback gives existing rows the same concise presentation without another AI call.
- Added adjacent cues for AI/LLM systems, forward-deployed/client-facing engineering, and systems integration so AI-facing roles can be described specifically without pretending they are embedded/firmware roles.

No database migration is required. Hidden Leads and Opportunity qualification/scoring behavior are unchanged.
