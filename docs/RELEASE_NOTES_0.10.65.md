# ScoutBox 0.10.65

0.10.65 is a focused Search Activity UI patch on top of 0.10.64.

## Fixes

- Fixes the text search inside the Providers multiselect so matching provider rows are actually hidden/shown while typing.
- Removes Cloud Provider from the Search Activity Provider types dropdown because Cloud Provider is not a provider type represented in this activity view.
- Keeps Provider types to the three displayed categories: Search Engine, Direct Search, and Forum.
- Updates Provider type summaries to use the three-type count, for example `2 out of 3 selected`.
- Keeps Cloud-origin rows, if any appear in this view, grouped under Direct Search rather than exposing a separate Cloud Provider type.

Routine future releases increment the patch component from 0.10.65.
