# ScoutBox 0.11.138 Release Notes

## SearchAPI key confirmation

- Save-time SearchAPI validation now calls the authenticated `/api/v1/me` Account API instead of issuing a live Google SERP request.
- A valid key is therefore no longer shown as “validation unavailable” just because a Google search request times out.
- Any successful SearchAPI service response automatically confirms the shared credential and clears a previous validation warning. A successful Test Search also updates the open SearchAPI dialog immediately instead of requiring a reload.
- Explicit SearchAPI authentication rejection can mark the shared credential invalid again.

## Shared SearchAPI authentication fix

- Fixed an argument-variable collision in the common SearchAPI request helper. Google Forums, Google News, and Google Local pass extra engine parameters; in 0.11.137 the parameter loop could overwrite the Python variable holding the API key, resulting in requests such as an invalid bearer token while Google Jobs/Web still succeeded.
- SearchAPI engine parameters now use separate variable names and cannot alter the credential.
- SearchAPI credential lookup now always prefers the unified Google Jobs hub credential.
- Migration 0210 promotes one legacy child credential if necessary and clears obsolete per-service credential copies.

## Preserved behavior

All 0.11.137 SearchAPI UI, compact test output, worldwide coverage, SearchAPI daily limits, ChatGPT/AI Mode controls, Google Local employer discovery, community-source handling, Search Activity alignment, and quota-pressure colors remain unchanged.
