# ScoutBox 0.8.78 Release Notes

ScoutBox 0.8.78 is a focused follow-up to 0.8.77. It keeps the existing discovery/data model and cleans up the review UI, Cloud campaign instructions, Post Age presentation, and Ask ScoutBox behavior.

## Review and list UI

- Hidden Lead HTTP status is compact and appears on the same line as the company name.
- Company-country filters are intentionally short on Opportunities, Hidden Leads, Address Book, and Applications & Outreach.
- Opportunity, Hidden Lead, and Application IDs remain visible and are centered for quick reference.
- Cloud Web provider, Primary model, and Secondary model selectors use the same aligned width as Discovery Method.

## Post Age

- Human ranges are restored: `~1 week`, `~2 weeks`, `~1 month`, `~2 months`, `~3 months`, `~4 months`, `~5 months`, `~6 months`, and `Older / uncertain`, plus Evergreen.
- Evergreen uses a leaf icon.
- Confidence is no longer printed beside the age. The age text/icon uses green for high confidence, yellow for medium confidence, gray for low confidence, and `?` when no usable age/confidence data exists.
- Detailed confidence and evidence remain available in the Opportunity detail evidence view.

## Cloud campaign custom settings

- Cloud Web run dialogs group custom text, preferred company countries, excluded company countries, and the final `Maintain custom settings until` control.
- The custom text and country preferences/exclusions are appended as concise instructions to the initial Cloud Web research request only. They are not implemented as a local post-filter and are not repeatedly appended to later resolver/lead-qualification prompts.

## Ask ScoutBox

- Cloud chatbot model Auto-select is available after choosing a Cloud provider.
- The default chatbot answer cap is 5,000 tokens; the migration changes only a saved value that exactly matches the previous shipped 10,000-token default.
- Normal chat questions are model-driven. ScoutBox supplies recent conversation plus a compact candidate profile, active Opportunities, Hidden Leads, and recent Applications/Outreach to the explicitly selected local Ollama or Cloud provider/model.
- The previous canned keyword/direct-answer path is no longer used for normal questions. Secret-exposure requests continue to be refused locally as a safety boundary.
