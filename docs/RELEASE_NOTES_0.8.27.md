# ScoutBox 0.8.27

This maintenance release focuses on the discovery/application surfaces reported after 0.8.26 and adds source-level regression checks for the repaired workflows.

## Discovery, counts and activity

Search Sources now renders Public Access explicitly for multi-access engines and keeps the Yandex, Baidu and Naver API choices available even when diagnostics fail. Left-menu unread indicators are circular themed badges, bold their menu entries, and display `99+` only when the count is greater than 100. The top-right discovery notification count is deliberately limited to unread Opportunities plus Hidden Leads; Applications/Drafts remain visible in their own left-menu badge but are not added to the top count, preventing duplicate counting.

The activity popover uses “Scanning for opportunities” for campaigns and “Scanning for hidden leads” for Hidden Leads scans, links the campaign name when available, and summarizes the latest error entries against the recent error total. Hidden Leads background work is again visible in Dashboard activity with its progress bar.

## Applications, drafts and prepared files

Applications & Outreach removes Channel and Resume/Cover from the list view and merges Added/Updated into one timestamp using the later value. The import-history modal is widened, prevents horizontal overflow, and keeps proposed dates on one line.

The application editor removes the obsolete mismatch-reason field and top save icon, renames the primary action to Save Draft, and places Delete IMAP Draft on the same action row. Save Draft always persists the internal record and queues the configured IMAP Drafts update. Blank Resume/Cover selectors are validated before integer lookups, eliminating the `Field 'id' expected a number but got ''` failure. Candidate-name placeholders such as `[Your Name]`, `{{ your_name }}` and `[name]` are repaired when drafts are generated, applied, opened, or saved.

The email editor shows To from the opportunity/outreach contact. Draft and draft-delete history records retain that recipient. Resume and Cover Letter preparation are separate queue actions with direct source selectors; dialogs close before queue submission, progress is shown under Prepared files, and completed DOCX/PDF files can be explicitly selected for attachment to IMAP drafts.

Application Questions now provide the answering model with role/company/location/job-description evidence plus candidate priorities, Resume concepts/skills and Likely role targets, and instruct it not to invent missing facts.

## List and history cleanup

Email History removes Classification, adds To to Inbox and Draft Activity, and fixes dark-theme subject/action contrast. Hidden Leads removes Contact from the list while retaining it in detail, and its Actions header is left aligned. Opportunity rows no longer show the blacklist shortcut; blacklist remains available in detailed views. The blacklist global scope label is now “Always”. A general dark-table style guard prevents browser-default white fills on linked/button text cells.

## Facebook and routing

Facebook Pages to Watch removes per-row delete, adds Delete Selected next to Add Page, removes the “Watch this page” control from the add/edit popup, and adds an external-open arrow next to Page ID.

Configuration > Discovery adds Optimize for Cloud. It applies a configured cloud provider to all pipeline stages only when a usable cloud provider/model/API key exists; otherwise it leaves existing routing untouched and reports why. Optimize for Local assigns model sizes according to stage complexity instead of selecting a 27B-class model for every stage.

## Readiness

First Run Readiness now calculates Candidate profile skill and role-target counts from the same composed Resume concepts / Likely roles profile used by discovery, preventing configured profiles from incorrectly showing `0 skills · 0 role targets`.

## Verification

`verify_release.sh` retains the earlier release checks and invokes `scripts/regression_v0827.py`, which source-parses the Python tree and validates the 0.8.27 UI/workflow regressions without requiring Django to be installed in the build container. Full Django runtime checks still require the normal project dependencies/runtime image.
