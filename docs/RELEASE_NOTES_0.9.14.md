# ScoutBox 0.9.14

## AI failover

ScoutBox now treats a provider response with no visible text as a failed attempt for routing purposes. `AIEmptyOutputWarning` is still logged as a Warning rather than a provider Error, but the configured fallback model is attempted immediately when one exists.

The Local Discovery pre-persistence `first_filter` path and Opportunity list-summary path now execute the full saved route. Cloud CV/role selection and the direct-retrieval Custom Domain analysis path also honor their configured secondary model instead of calling only the primary model. Chatbot now likewise attempts its configured Secondary route when the Primary request fails or returns no visible output.

## XLSX parity

The main Hidden Leads and Opportunities exports preserve their existing columns and append list-visible context that had been omitted.

Hidden Leads adds Company Info, Note, URL HTTP Status and Campaigns. Its Summary column now uses the same visible summary fallback as the list.

Opportunities adds List Summary, Company Info, Salary, Contact Email, Note, URL HTTP Status and Campaigns.

## Diagnostic discovery funnel

Maintenance Diagnostic Data format version is now 2. The export adds aggregate discovery-yield diagnostics without exporting raw pre-persistence search-result arrays or AI prompt/output bodies.

New aggregate information includes search-provider returned/unique/applied counts, campaign raw/consolidated/unique/retained conversion, discovery-filter stages and rejection reasons, selected purpose/disposition/language/remote classifications, and AI status/empty-output health by stage/provider/model.

For discovery privacy and size control, general AI request prompts/outputs, generated text bodies, performance input/output text, and raw diagnostic result arrays remain omitted. All Chatbot conversations in the selected diagnostic period are intentionally exported with complete message bodies, role, session grouping, provider/model, links and timestamp so chatbot quality can be troubleshot from the diagnostic package. The normal diagnostic redaction pass still removes configured secrets and known applicant/admin identity values.

No database migration is required.
