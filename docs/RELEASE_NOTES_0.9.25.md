# ScoutBox 0.9.25

## Local Auto-detect tolerance

- Automatic hardware sizing now treats approximately 29-40 GiB as the 32 GB class, so commonly reported totals such as 31.8 GiB reliably use the 7B automatic ceiling.
- Ollama advertised model tags are used before internal parameter counts for automatic sizing. A model tagged `:7b` therefore remains a 7B-class choice even if Ollama reports an internal count such as 7.6B; an `:8b` model remains above the 7B automatic tier.
- Smaller hardware remains conservative. A 16 GiB discrete GPU still defaults to the 4B tier, and manual model selection remains unrestricted.

## About ScoutBox / Word export

- Export to Word is now a large icon-only action directly beside the ScoutBox heading in the first About card. It has no button border or visible label; the tooltip/accessible label is `Export to Word`.
- The DOCX exporter no longer flattens the architecture SVG into one pipe-delimited paragraph. It exports a structured component flow with boxed stages, arrows, live runtime/version/count hints and the existing architecture notes.
- About learning/reference headings use a common content edge so Useful scripts & key files, Terminal & SQL examples and Redis usage align consistently with their parent sections.

No database migration is required for 0.9.25.
