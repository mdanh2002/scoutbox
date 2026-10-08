# ScoutBox 0.8.67 release notes

ScoutBox 0.8.67 is a UI and Cloud-AI routing refinement release built on 0.8.66. It adds no new database migration and preserves existing data and configuration.

## AI & Discovery

- Fixed the case where an enabled cloud provider such as Gemini had a saved key and had already resolved an **Automatic** model during provider testing, but that model did not appear in Discovery stage dropdowns.
- ScoutBox now reuses the provider test's resolved model when Default model is left on **Automatic**. That model participates in cloud availability, stage choices, cloud presets, Cloud Web routing and readiness checks.
- A successful provider test exposes the resolved cloud model to stage dropdowns immediately and enables the Discovery method selector in the current page without requiring a reload.
- Cloud Web continues to use a concrete provider/model route internally; provider-level Automatic remains a valid operator choice.

## Search Sources / quotas

- Daily-budget warning/info icons are positioned to the right of the normal input width, so quota fields align with neighboring fields.
- Quota/info icons are borderless controls and open a click popup; quota information is no longer carried by hover tooltips.
- Daily Cloud AI request, native web search, input-token, output/reasoning-token, passive-enrichment and page-recovery limits now expose today's used/limit values and local reset time in the same popup style.
- Query variants, queries/provider and max-results controls also expose short explanatory popups.

## Campaigns and Address Book

- The Run Now Note/Custom-instructions explanation is consolidated into one compact hint beneath the text area.
- Campaign list and Run History context lines include a Note or Custom-instruction icon. History-only Note context is italic.
- Address Book removes the standalone Source column. Source links now use a borderless dark-green external arrow on the right side of Name / Company, vertically centered.

## Layout refinements

- Cloud Provider Base URL width is shortened so the first provider row aligns with Default model, Output token cap and Test configuration below it. Ollama remains compact and aligned.
- Maintenance actions are one per row with aligned buttons, explanatory text on the right and more vertical spacing.
- Engagement Preferences stretches Location & engagement and Company & compensation to equal height on desktop; Hiring-process guidance receives additional vertical space.
