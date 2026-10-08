# ScoutBox 0.8.119 release notes

## Chatbot provider/model integrity

0.8.119 fixes a Chatbot configuration bug where switching a provider could preserve the previous provider's model value. If the preserved model was absent from the newly selected provider catalogue, the UI re-added it as a `(configured)` choice. This could make a Gemini model appear under `Ollama local`.

The Chatbot model selector is now explicitly bound to its provider. Provider changes clear stale model state before loading the new catalogue; unmatched models are not injected into a different provider's choices; auto-selection requires an exact catalogue match; and server-side saving rejects an Ollama route whose model is not actually installed.

No database migration is added in this release.
