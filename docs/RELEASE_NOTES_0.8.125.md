# ScoutBox 0.8.125

## Local AI optimization correction

- Restores **Optimize for Local** as an explicit model-selection preset instead of clearing Primary/Fallback routes to Automatic local.
- Installed Ollama generation models are ranked by approximate parameter size. Models at 4B+ are preferred whenever available.
- Routine Local AI Discovery stages, including `first_filter` and `freshness`, target approximately 7B so a 4B-class model can serve as a meaningful fallback instead of routing classification through 1B/2B models.
- Heavier reasoning stages target approximately 12B. Models above 12B are only selected when needed to meet the stage target and no suitable 4B–12B model does so.
- Fallback selection is strictly smaller than Primary and remains 4B+ whenever any 4B+ model is installed.
- If only sub-4B generation models are installed, ScoutBox uses the best available model and warns the operator.
- **Automatic local** remains available as a manual dropdown choice; only the separate Auto Select Local action remains removed.
- Optimize for Local still warns when ScoutBox cannot confirm a usable local GPU.
- Removes the post-preset success notice. Explicit selections themselves are the confirmation; only actionable warnings are displayed.

No schema changes or migrations are included in this release.
