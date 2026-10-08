# ScoutBox 0.9.24

## AI & Discovery

- Renames Local Discovery **Optimize for Local** to **Auto-detect**.
- Local Auto-detect uses the same explicit Primary/Secondary pair for every Discovery stage. With a 32 GB-class automatic hardware ceiling it prefers a 7B Primary and a 4B Secondary when both are installed. Smaller hardware tiers use lower models automatically; manual choices are unrestricted.
- Cloud Web model dropdowns load the provider's full returned generation-model catalogue rather than restricting the user to ScoutBox's documented defaults.
- Cloud Web Auto-detect opens a provider selector. The chosen provider is applied to every stage for the prepared defaults, but each stage remains independently editable afterward.
- Cloud Web Auto-detect itself remains metadata-only: it does not run a generation/web-capability probe. High-volume stages prefer economical models (for example Gemini 2.5 Flash / 2.5 Flash-Lite), balanced stages step up, and low-volume reasoning stages use stronger nearby pairs. **Test Selection** remains the live validation action.
- Chatbot Auto-detect now uses an explicit enabled-provider dropdown (Ollama, Gemini, OpenRouter, OpenAI as available). Ollama follows the same hardware-aware Primary/Secondary policy; Cloud providers use a stronger documented Primary and nearby lower Secondary.
- Removes the redundant Local Ollama Chatbot quality warning from the chat composer.

## About ScoutBox

- Adds **Export to Word** beside the About ScoutBox page title. The server renders the full reference page into a timestamped native DOCX for troubleshooting, including commands, Redis/SQL learning material, runtime values, links and a textual rendering of the architecture diagram.
- Removes the Redis **Read-only examples** badge while preserving the examples and safety guidance.
- Normalizes the horizontal alignment of Troubleshooting, Common data checks, Useful scripts & key files, Database Info, Terminal & SQL examples and Redis usage headings.

## Upgrade

No new database schema migration is required for 0.9.24. Migration `0074_v0922_cloud_web_stage_routes` remains included for older upgrades.
