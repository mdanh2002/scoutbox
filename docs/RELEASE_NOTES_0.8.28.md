# ScoutBox 0.8.28

ScoutBox 0.8.28 is a workflow and observability maintenance release focused on discovery-provider configuration, application preparation, AI troubleshooting, source provenance, and list/read-state consistency.

## Search engine Access Type

Yandex, Baidu and Naver now render every supported access mode explicitly and preserve the selected mode correctly. Public Access is a real visible option rather than an empty legacy value. Switching to another API mode no longer causes the empty/Public option to be relabelled as Client ID, Folder ID, or another credential field. The credential-label JavaScript now targets field labels specifically instead of accidentally mutating an option element. Legacy blank or invalid access types are normalized to Public Access by migration 0025.

## Discovery notifications, sources and read state

The first top-right notification badge continues to count only unread Opportunities plus Hidden Leads, intentionally excluding Applications/Drafts to avoid duplicate counting. Its popover now also shows the three most recent unread discovery records beneath the Opportunity/Hidden Lead counts.

Opportunities and Hidden Leads regain a compact Source column. Newly discovered Hidden Leads retain their actual search-provider provenance. Opportunity source display prefers that engine when known, otherwise falls back to a useful website domain. Generic labels such as “Source” are suppressed, and an Opportunity Source is left blank when it would simply duplicate the Contact value.

Opportunities and Hidden Leads use the same Mark as Read / Mark as Unread dropdown pattern as Applications & Outreach, positioned directly after the All items/read-state filter. Applications & Outreach Mark all as read now updates the persisted read state and refreshes its left-navigation badge consistently.

## Applications, email and preparation history

Applications & Outreach adds a Contact / URL column. Type moves to the final column and is represented by a clean icon-only glyph with a tooltip, without a surrounding badge shape.

Delete IMAP Draft has moved from Details to the Email & Application tab. The Save Draft explanatory copy is reduced to a small hint at the bottom of the composer, and the saved-state message gains spacing from adjacent controls.

The Email & Application workspace now has persistent history for generated email variants, ATS/Application Questions answers, prepared Resume files and Cover Letter files. The right-side history panel exposes queued/running/completed/failed state, lets a user reapply a previous generated email body, and lets prepared files be individually selected for IMAP draft attachment instead of only exposing the latest result.

Resume/Cover preparation reports stage-level progress instead of appearing frozen at 1%. PDF conversion has a bounded timeout and degrades gracefully if conversion cannot finish, while the editable artifact remains available. Preparation remains queued and its state is visible in the history panel.

## Candidate/contact personalization

Candidate Profile adds Phone Number. Common “contact number” and “phone number” placeholders in generated email text are populated from that field. Recipient salutations such as `Dear [Recipient's Name],` use the lead/opportunity contact name when available and otherwise fall back to the company name.

Fallback company display is more readable for compact domain-style names. Conservative connector/suffix logic can turn values such as `oadbyplastics` into `Oad By Plastics` without rewriting already formatted company names.

## Application Questions / ATS

Application Questions now build candidate context safely from structured skill and likely-role data instead of attempting to join dictionary values directly. Answers receive role/company/job evidence plus the application profile, and each generated answer is retained as a version in the application history panel.

## GPT Log

System adds a GPT Log for troubleshooting AI usage. Each recorded model request includes the full prompt and full model answer, with long Input/Output content truncated in the list and available in a Details popup. The list supports search, runtime filtering and pagination.

Rows identify the related Opportunity, Hidden Lead, Application/Outreach or system task when a concrete record exists; otherwise the stage/task is retained. Runtime (local/cloud), provider/model, input/output token counts, timestamp, status and error information are recorded. Provider-reported token counts are used when available, with estimates only as a fallback. Attachments are never stored as body content in this log: only filename and size metadata are recorded and displayed.

## Ask ScoutBox

Ask ScoutBox now distinguishes ScoutBox concepts explicitly. Campaign questions are answered from Campaign/CampaignRun and schedule/window state; “next campaign” derives the actual scheduler state; “best job for me now” ranks actionable Opportunity records. Background utility jobs such as Tailor Resume, email tailoring or ATS-question generation are explicitly excluded from being treated as campaigns or jobs. User-facing answers avoid exposing raw internal snapshot keys.

## Campaign lifecycle safety

A campaign with an active queued/running/stopping run cannot be deleted. The detail and bulk-delete UI rejects the operation and instructs the user to stop/pause the active run first, while the backend enforces the same rule against direct requests.

## Hidden Leads, Facebook and UI polish

Hidden Leads moves Fit immediately after Added, keeps Source after Fit, and left-aligns the Actions header and buttons. Facebook Pages to Watch removes the Use toggle entirely: an existing row is considered watched and a user deletes it to stop watching. Row selection remains; Delete Selected matches Add Page sizing; Added date is shown; Page ID retains its external-open action. Existing disabled page rows are normalized enabled during migration.

Email History Draft Activity renders Subject as ordinary text without the unusual bordered treatment. Dashboard shifts the page title down to align better with ScoutBox branding and corrects readiness-detail alignment. Tailor Resume/email/ATS background jobs show only their general activity line on the Dashboard rather than a misleading detailed progress bar. Engagement Preferences widens Currency and Per year selectors so labels are not clipped.

## Migration and verification

Migration `0025_v0828_phone_ai_log_prepared_files.py` adds candidate phone number, Hidden Lead source provenance, persistent prepared application files and AI request logs, normalizes multi-access provider state, and aligns existing Facebook watch rows with the new row-exists-means-watched behavior.

`verify_release.sh` retains inherited release safeguards and invokes `scripts/regression_v0828.py`. The v0.8.28 regression script source-parses the Python tree and validates the provider option-mutation fix, notification/source rules, application history and attachment selection, candidate/recipient substitution, read-state behavior, GPT input/output logging, Ask ScoutBox semantics and campaign deletion guard without requiring Django to be installed in the build container. Full database/Celery/IMAP integration checks still require the normal ScoutBox runtime dependencies.
