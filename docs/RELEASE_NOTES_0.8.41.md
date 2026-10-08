# ScoutBox 0.8.41 release notes

ScoutBox 0.8.41 is a focused refinement of 0.8.40. It preserves the existing discovery, campaign, application, Recycle Bin and provider behavior except for the changes below.

## Statistics

- Added **Opportunities by Country** and **Leads by Country** pie charts.
- Both charts respect the Statistics period/custom date range and existing query filtering.
- The charts group the largest countries individually and combine the long tail into an Other slice for readability.

## Opportunity and Hidden Lead contact email

- Opportunity details now include an editable **Contact email** field beside the source/target metadata.
- Hidden Lead details now include an editable **Contact email** field in the edit form.
- Empty values are allowed; non-empty values are validated as email addresses before saving.
- This lets a user replace a poor automatically extracted address, such as a disability/accommodations mailbox, without changing the rest of the record.

## AI & Discovery routing

- Renamed **Save routing** to **Save**.
- Renamed **Test Model** to **Test Selection**.
- **Auto Select**, **Optimize for Local**, and **Optimize for Cloud** are now client-side presets only. They update the visible primary/fallback dropdowns and token caps but do not write to the database.
- The preset dialog explicitly explains that the user must click **Save** to persist the changes; navigating away discards the unsaved preset.
- **Test Selection** submits and validates the routing currently visible on the page, so unsaved manual/preset selections can be tested before saving.
- Automatic primary selections are resolved to a real enabled provider/model and exercised instead of being treated as valid immediately.
- Selection-specific input/output caps are used during validation.
- Automatic-route signatures normalize blank selection fields so a saved Automatic configuration can retain its completed test state across navigation.
- The running test panel includes **Stop test**. Stopping preserves already-persisted stage results and cancels the background job where supported.

## Persistent provider tests

- The Ollama test-prompt result is restored/resumed when returning to AI & Discovery > Providers.
- OpenAI/Gemini provider test jobs are also restored/resumed, while their provider-level last-test message remains persisted as before.
- Search Source provider test jobs now persist their latest job reference in the rendered page. Reopening a provider resumes a running test or displays the stored completed result, including parsed results/raw-response access.

## Recycle Bin

- Reworked the top toolbar so Search, Rows, Search action, Select All, Restore Selected, Delete Selected and Empty Recycle Bin remain on a single compact row on normal desktop layouts.

## Compatibility

- No new database migration is required for 0.8.41. Migration `0030_v0838_hidden_lead_company_info.py` remains the latest schema migration.
- Existing `.env`, PostgreSQL data, Redis data, media and encryption keys are preserved during a normal upgrade.
