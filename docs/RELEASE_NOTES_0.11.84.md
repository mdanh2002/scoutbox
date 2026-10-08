# ScoutBox 0.11.84

## Resource Usage

- Renamed the table below Market Coverage from **Discovery Performance Details** to **Discovery Activity**.
- Added exact totals to the Token Usage ring summary for input, output, and reasoning tokens.
- Added exact totals to the Discovery Performance ring summary for requests, results, and errors.
- Added right-aligned request totals to both the Languages and Markets legend headings in Market Coverage.

## Configuration layout

- Removed the unnecessary separator above the IMAP Browser heading.
- Removed the separators above Gemini, OpenRouter, and Ollama while preserving provider-section spacing and behavior.
- Removed the separators around Resend Config and Outgoing Test, and aligned both headings with their explanatory text.

## Search compatibility

- Bare country-domain search scopes remain supported. ScoutBox continues to accept provider queries such as `site:.kr` and `site:.com.kr`.
