# ScoutBox 0.8.46

## Campaign token charts

- Replaces the single **AI Token Usage** chart on Campaign Detail with separate **Local Token Usage** and **Cloud Token Usage** charts.
- Token usage is classified by the provider that actually executed each request, so local/cloud fallback behavior is reflected correctly.
- Both token charts share the existing Hour / Day / Week / Month and From / To controls.
- Campaign discovery analytics now fill the existing two-column chart grid as a complete 2×2 layout: Opportunities, Leads, Local Tokens, Cloud Tokens.
- Historical usage without explicit campaign attribution remains intentionally unassigned rather than guessed.
