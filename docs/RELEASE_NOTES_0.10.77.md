# ScoutBox 0.10.77

ScoutBox 0.10.77 is a corrective full-package release for list reliability, facet-count consistency, filter-dialog presentation, telemetry layout, and Address Book audit hygiene.

## Fixed

- **Opportunities HTTP 500:** campaign facet evaluation now drops inherited `select_related`/prefetch state before narrowing the queryset with `only()`. This prevents Django's deferred-field/select-related `FieldError` while preserving both origin Campaign and rediscovery Campaign provenance. Hidden Leads uses the same safe relation-reset pattern for campaign facet work.
- **Country dropdown totals:** `All countries (N)` now equals the sum of the country choices actually shown in the dropdown. Blank, placeholder and unrecognized location text no longer inflates the total on Opportunities, Hidden Leads, Address Book, or Applications & Outreach.
- **Hidden Lead country counts:** country options now count the same normalized-company representatives used by the visible Hidden Leads list, so duplicate rows for one company cannot make a country count exceed the visible dataset.
- **Long dropdown labels:** searchable-select and country-picker popovers split a trailing numeric count into a fixed, right-aligned count cell. Long Campaign/provider/country labels can ellipsize without hiding `(N)`, and the full option text remains available by hover title.
- **Token Usage export placement:** the Token Usage legend export icon is now the rightmost heading control, immediately after the current `All tokens` / selected-model status, matching the Discovery Performance heading layout.
- **Filter-dialog empty state:** Opportunities, Hidden Leads and Address Book filter dialogs now show `Select filter conditions, then click Apply.` in their reserved message area until Reset, Best Fit, or validation feedback replaces it.
- **Address Book promotion audit noise:** no-op rediscovery is now reported internally as `unchanged`; only a new contact or a material change to contact/company data produces an `addressbook_promotion` Audit Trail row. Last-seen-only refreshes, skips, invalid/generic mailboxes, ownership mismatches, recycled contacts and unchanged contacts are never written to that audit action.
- **Historical audit cleanup:** migration `0107_v01077_addressbook_audit_cleanup` removes all pre-existing `addressbook_promotion` AuditLog rows, as requested. Future rows are governed by the stricter created/material-update rule above.

## Regression coverage

- Adds a request-level Django regression test that creates a Campaign-linked Opportunity and requires `/opportunities/` to return HTTP 200.
- Adds runtime coverage for country-total invariants on Opportunities, Applications, Address Book and de-duplicated Hidden Leads.
- Adds Address Book promotion tests for create, unchanged rediscovery, material update and invalid-skip audit behavior.
- `verify_release.sh` now validates 0.10.77 release metadata, Python syntax/bytecode compilation, targeted source regressions, shell syntax, and base-template JavaScript syntax when Node is present.

## Consolidated history relevant to this repair

- **0.8.40** introduced searchable Campaign filters with per-Campaign counts.
- **0.8.96** introduced faceted Campaign/country/read/status counts.
- **0.10.27** established stable origin Campaign attribution while retaining later Campaign encounters as rediscovery provenance.
- **0.10.29** fixed an earlier deferred-field/select-related HTTP 500 in Opportunities/Hidden Leads by clearing relation loading before `only()` probes.
- **0.10.37 / 0.10.39** established the stable filter-feedback area and the rule that country/status facet totals should represent displayed options rather than hidden placeholder values.
- **0.10.70** reduced automatic Address Book promotion audit noise by suppressing skipped outcomes by default.
- **0.10.76** added the latest list-count and telemetry changes but regressed the country-total invariant and left the campaign facet vulnerable to the earlier queryset conflict.
- **0.10.77** consolidates those behaviors into one consistent implementation and adds runtime regression coverage for the failures reported above.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application files with the 0.10.77 full package, then run the normal restart/upgrade flow:

```bash
./restart_scout_box.sh
```

The upgrade applies migration `0107_v01077_addressbook_audit_cleanup`, which intentionally deletes historical `addressbook_promotion` Audit Trail rows. No application/contact/opportunity records are deleted by this migration.
