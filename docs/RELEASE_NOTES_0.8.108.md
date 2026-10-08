# ScoutBox 0.8.108

Released: 26 August 2026

## Usage visibility and cost control

Resource Usage now applies the selected period to its usage/provider/Cloud Usage data. The existing CPU/RAM/Tokens chart path was intentionally left unchanged. Cloud Usage exposes visible output and reasoning separately while preserving the combined output-plus-reasoning counter as the hard daily safety limit.

AI Request records now persist `reasoning_tokens`, `web_search_queries`, and a token usage source flag. Gemini `thoughtsTokenCount` maps to Reasoning Tokens and `groundingMetadata.webSearchQueries` is counted as AI Web Search Queries. These fields are included in request details and exports. Migration 0068 backfills UsageMetric values where historical metadata already contains them and reconstructs informational daily output/reasoning splits without rewriting the existing authoritative hard-limit counter.

High-volume Cloud AI stages use lower Gemini thinking, tighter per-stage input/output caps, JSON response mode when JSON is explicitly requested, and larger candidate verification batches. Existing direct page retrieval, URL/domain de-duplication and company-research caching continue to avoid unnecessary cloud work.

## Chatbot correctness

Ask ScoutBox no longer receives only a small top-ranked subset of Opportunities and Hidden Leads. It builds a complete current non-deleted/non-suppressed inventory of their query-relevant/user-facing data. Simple existence/list/count questions can be answered directly against that complete local inventory without spending AI tokens. Before an LLM call, ScoutBox estimates the complete prompt size; if the configured model cannot accept it, ScoutBox refuses to answer from a silently truncated subset and directs the user to search Opportunities or Hidden Leads.

## UI and data quality

Company Info now treats RDAP/domain-registration age as domain-derived evidence instead of inheriting a generic Low-confidence badge. Generic aggregate confidence is presented as Research confidence. Missing age/size remains `?`.

Quota threshold events are merged with recent operational errors into a de-duplicated Recent Alerts history. The error badge itself remains error-only. Email Configuration uses `Email configuration saved.` and async tests/folder actions clear stale page messages first. Hidden Lead source links are kept inline after the displayed summary. Fit levels use clearly different icon shapes, keeping the smiley only for 5/5.

About ScoutBox now shows live Opportunities/Hidden Leads/Contacts counts, Applications & Outreach count, local Ollama model count, configured cloud provider names/count, and current ScoutBox persistent-storage consumption. It also adds a two-column Troubleshooting Tips reference with safe Docker/Django inspection commands and a credential-storage explanation. Overall System Architecture and Main Workflow use distinct section icons.

Search Activity renames the downloaded payload column to Size. Migration 0068 and salary parsing reject false salary strings where the only numeric value is a year (for example `Backend Developer Salary in Germany [2023]`).
