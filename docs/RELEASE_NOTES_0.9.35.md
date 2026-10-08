# ScoutBox 0.9.35

## Conservative structured-response recovery

Cloud models can occasionally reach an output limit after returning several complete JSON records and part of one final record. ScoutBox now attempts a deliberately narrow recovery before discarding that response.

For a top-level array, or the common single-array envelope such as `{"results":[...]}`, ScoutBox decodes records one at a time. Only records that parse completely are retained. The first incomplete trailing record is discarded, the array/object is closed, and the result is parsed again before it is accepted. ScoutBox never fabricates a missing field or guesses how an unfinished object should end.

A successful repair is logged as **Recovered response**. The AI Requests Output panel shows the corrected valid JSON that downstream Discovery actually consumed. Recovery metadata records how many complete items were kept and whether a trailing incomplete item was discarded.

If a structured response cannot be repaired safely, it is logged as **Malformed response** with its own icon. The existing expanded-output retry and configured failover logic remains active for those unusable responses.

## Raw provider output

`AIRequestLog` now has `raw_output_text`. When recovery occurs, the original provider text is retained there for diagnostics while `output_text` stores the corrected payload. Normal list/detail output uses the corrected payload; JSONL diagnostics include both fields.

## Upgrade migration

Migration `0077_v0935_ai_response_recovery` adds the raw-output field and the new status choices. Historical `partial_response` rows are mapped to `malformed_response`, since older ScoutBox versions did not actually salvage them.
