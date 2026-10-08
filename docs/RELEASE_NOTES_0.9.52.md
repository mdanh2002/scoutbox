# ScoutBox 0.9.52

## Fixed

- Local Ollama JSON-only requests now pass through ScoutBox's central structured-response preparation before they are logged or returned to task code.
- A single valid Markdown-fenced JSON object/list remains usable even when a model appends prose outside the fence; ScoutBox stores the original raw response and marks the canonical payload as recovered.
- Truncated structured output can now be recovered recursively for arbitrary JSON objects and arrays, not only top-level lists or `{"results": [...]}` envelopes.
- Recovery never fabricates an unfinished scalar. For example, a cut string at the end of an array is discarded while previously complete array values and surrounding containers are preserved.
- Ollama `done_reason`/output-token evidence is recorded so output-cap stops can be distinguished from normal completion, including older servers that omit a stop reason.
- Local query-language planning now allows 600 output tokens instead of 320 and parses the central canonical JSON directly.

## Compatibility

- No database migration.
- Existing AI Request status fields and the `_recover_truncated_json_list` compatibility entry point are retained.
- Provider/model routing is unchanged.
