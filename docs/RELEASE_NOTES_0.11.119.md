# ScoutBox 0.11.119

ScoutBox 0.11.119 fixes the all-failed Gemini manual re-evaluation regression in the cloud-parallel execution path.

## Gemini re-evaluation reliability

- Hidden Lead, Opportunity, and Address Book manual re-evaluation continue to use the provider/model explicitly selected in the re-evaluation dialog.
- Selecting **Gemini** therefore runs the re-evaluation in the **Cloud**; selecting **Ollama** runs it locally.
- Restores ScoutBox's existing Gemini 3.x empty-visible-output compatibility retry for the parallel cloud path.
- The compatibility retry stays on the same selected Gemini model and retries once with minimal thinking and without forcing JSON MIME, while ScoutBox still validates/parses the required JSON result.
- This specifically fixes the regression where the parallel helpers passed `empty_response_budget=1`, which suppressed that retry and could turn every grounded Gemini result into `AI request returned no visible output.` even though provider connectivity was healthy.
- OpenAI and OpenRouter parallel re-evaluation behavior is unchanged; they retain a one-attempt empty-response budget because the Gemini-specific compatibility retry does not apply to them.
- Local/non-parallel re-evaluation behavior is unchanged.

## Evidence from the reported failure

- The support export showed 131 Hidden Lead re-evaluation requests using `gemini / gemini-3.5-flash-lite`, `runtime=cloud`, with web grounding enabled.
- All 131 stopped at the first empty-visible-output response and none recorded the Gemini compatibility retry.
- The same support export showed successful normal and web-search provider tests for the same Gemini model, confirming that the API key/model connection itself was working.

## Regression coverage

- Verifies that all three parallel manual re-evaluation helpers use the shared provider-aware empty-response budget.
- Verifies that Gemini receives a budget of 2 so the same-model compatibility retry can run.
- Verifies that non-Gemini cloud providers retain a budget of 1.
- Retains the 0.11.118 unresolved-global symbol audit for the three parallel helpers.
