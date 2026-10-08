# ScoutBox 0.10.34

## Cloud Web source-routing correction

Cloud Web Discovery now keeps a strict acquisition boundary between ScoutBox Search Sources and provider-native Cloud Web research.

When **Cloud Web Discovery** is selected:

- supported direct API/feed/RSS/direct-page/ATS adapters may still retrieve candidates directly from their source;
- those direct candidates can be qualified by the configured Cloud AI route before persistence;
- ScoutBox's configured search engines are **not** executed for source search;
- no `site:` search-engine fallback is triggered when a direct adapter fails, is unconfigured, returns zero records, or returns many records;
- provider-native Cloud Web discovery continues normally and remains the general web discovery surface.

This prevents search-engine SERP titles, snippets and indexed copies from being mixed into the direct-source candidate input set for Cloud Web runs.

## Local AI Discovery unchanged

Local AI Discovery keeps the 0.10.33 additive behavior:

- direct adapters run where available;
- normal configured search-engine discovery still runs;
- every selected direct-capable source can receive its parallel source-targeted `site:` search regardless of direct-source success or result count.

## Opportunity Best Fit preset

The **Filter Opportunities** dialog now includes a **Best Fit** toolbar action. It immediately selects Web, ATS and Email application paths, excludes Unknown/Others application paths, selects only **Fully Remote**, leaves Post Age unrestricted, applies the filter and closes the dialog. The underlying remote bucket remains `fully`; only the user-facing label is clearer.

## Planning isolation

The Cloud Web direct-source pre-pass now builds only the deterministic Resume/profile search context required by direct adapters. It no longer constructs the Local AI/search-engine query plan before direct-source retrieval.

## Search Sources capability text

Search Sources now explains the mode distinction explicitly:

- **Local AI Discovery:** direct + configured search engines;
- **Cloud Web Discovery:** direct adapters + provider-native Cloud Web research; ScoutBox search engines bypassed.

Migration `0088_v01034_cloud_direct_source_routing` refreshes capability labels on existing source rows. It adds no schema columns.

Routine future releases increment the patch component unless a minor/major version change is intentionally chosen. For routine releases, increment only the patch component.
