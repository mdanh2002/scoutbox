# ScoutBox 0.8.29

ScoutBox 0.8.29 is a campaign/discovery workflow and interface reliability release focused on campaign lifecycle safety, useful campaign result history, application preparation ergonomics, notification clarity, diagnostics, and cleanup of user-facing data.

## Campaign lifecycle and templates

Campaigns can now be paused/disabled without deletion and re-enabled later. Deletion is intentionally stricter: only a fully paused/disabled campaign with no queued, running, or stopping run can be deleted. This is enforced in both campaign list/detail UI and the backend, including bulk deletion. The Campaign Detail Delete button now sits directly to the right of Duplicate.

New Campaign always offers a code-defined **CV Discovery** template derived from Candidate Profile/Resume evidence. It is not a database `CampaignTemplate` row, so Maintenance cleanup cannot remove this essential resume-first starting point.

## Campaign results and daily history

Campaign results now track Hidden Leads as well as Opportunities. Campaign list rows, Campaign Detail, and Dashboard recent-campaign views show both counts. Campaign Detail also includes a dedicated **Leads Found** table.

Run history is aggregated by campaign/day rather than exposing every scheduler execution as a separate row. Each day shows first run, last run, run count, Opportunities found, Leads found, and status. Dashboard Recent campaigns uses the same daily summary model.

## Query Rotation

Query Rotation now supports repeatable simulation. **Preview Next** advances an independent preview offset every time it is clicked and does not mutate scheduler state; **Show Current** restores the real current rotation. The two buttons use consistent sizing, the numeric stepper is wider, and its compact hint is simply **Default**.

## Hidden Leads

The Hidden Leads list removes the Actions column and moves Fit to the final column. The company name itself opens the lead detail/edit popup, while a compact external-link icon on the right side of the Company cell opens the lead website. Blacklist Source remains available inside the detail popup rather than occupying the list.

Company-name fallback handling now covers additional domain-style names including `robopenguins` → `Robo Penguins` and `enginuityinc` → `Enginuity Inc`, while preserving existing brand-like names such as Microchip and Qualcomm.

## Discovery notification and status popovers

The first top-right badge remains discovery-only: unread Opportunities plus unread Hidden Leads. The popover no longer repeats a redundant “N unread discovery items” sentence. It shows the Opportunity/Hidden Lead breakout plus up to three recent unread discovery items; when both categories have unread records, at least one of each is reserved. Recent rows use compact type icons rather than a repeated text type label.

When ScoutBox is idle but has a scheduled campaign, status includes the actual timestamp, for example `Next search scheduled for 20 Aug 2026 at 11:15`. If no search is scheduled, it reports that directly.

The header clock uses fixed-width/tabular numerals so changes in seconds do not make the timestamp jump horizontally.

## Dashboard activity and layout

When no campaign is running and no scheduled campaign is enabled, the ScoutBox Activity control shows **Campaign** instead of **Pause Search**, linking directly to campaign management. Scheduled/active/paused states continue to use the appropriate Pause Search or Start Search control.

The Dashboard page heading is shifted slightly farther down for better alignment with the ScoutBox header. Redundant CPU/Memory/GPU status chips are removed from ScoutBox Activity.

## Applications & Outreach and email preparation

The Applications & Outreach navigation badge is based only on unread `Application` rows. Historical application imports are explicitly marked read, and migration 0026 normalizes older imported history so importing an archive cannot make the badge equal the total history size.

The internal `imported.invalid` URL is confirmed as a uniqueness sentinel used when imported history has no real source URL. It remains available internally where required but is stripped from user-facing Contact/URL fields; legacy canonical/target sentinel URLs are cleaned by migration.

Email & Application toolbar controls are simplified and grouped on one row: **Retailor**, **Tailor Resume**, **Tailor Cover Letter**, **Ask Question**, then Delete IMAP Draft and Save Draft at the far right. Queue dialogs now close immediately after validation and before the asynchronous request is submitted, while progress remains visible in the persistent history/prepared-files panel.

## Candidate Profile phone validation

Candidate Profile Phone Number is visually shorter, stored with a 32-character maximum, and validated before save. International forms may use digits, a leading `+`, spaces, parentheses, periods, and hyphens; the value must contain 7–20 digits.

## Country detection

New Opportunities now use the same `infer_country` logic as Hidden Leads, combining page text/location evidence with domain/TLD fallback rather than relying on the previous narrower Opportunity path.

## Resource Usage and provider diagnostics

The CPU/Memory/GPU chart retains the **120-min window** chip but removes the duplicated live CPU/Memory/GPU/Requests tag strip. Search Provider Performance adds a third data dimension for **results returned**: outer ring = requests, middle ring = returned results, inner ring = errors. This makes a provider that responds successfully but consistently returns zero results visually obvious.

Search Source testing now offers **Show in browser** inside the raw-HTML response section. Captured HTML opens through a sandboxed ScoutBox preview endpoint, making captcha/interstitial/provider-response debugging easier without executing page scripts.

## GPT Log

GPT Log has been condensed into operational columns: Date, Related / Task, Runtime / Model, multiline Input, multiline Output, Input Tokens, Output Tokens, and Details. Runtime is represented compactly beside provider/model, and record relation plus task/stage share one column.

Long prompt/output text is multiline-truncated in the list and shown in full through a Details popup. Server-side pagination supports 25/50/100 rows, search/runtime filters remain available, and an Export action sits at the far right of the toolbar. Attachment contents are still never written to the log; only filename and size metadata are retained.

## Discovery mode behavior

Changing Discovery mode no longer requires a separate Save button. Selecting a different mode opens an explicit confirmation prompt, saves it asynchronously, then reloads the page so routing/provider UI cannot remain out of sync with the stored mode.

## Migration and verification

Migration `0026_v0829_campaign_leads_phone_cleanup.py` adds the Campaign ↔ Hidden Lead relation used by campaign lead results, reduces Candidate Profile phone storage to 32 characters, and cleans legacy imported-history placeholder/read state.

`verify_release.sh` retains inherited safeguards and now invokes both the v0.8.28 and dedicated `scripts/regression_v0829.py` source-level suites. The v0.8.29 suite verifies company-name cleanup, paused-only campaign deletion, CV Discovery fallback, daily campaign/lead results, repeatable query rotation, Hidden Leads layout, notification behavior, clock stability, Dashboard idle control, application modal lifecycle, import sentinel cleanup, phone validation, resource/provider charts, country inference, GPT Log structure/pagination/export, Discovery mode confirmation, and sandboxed raw HTML preview without requiring Django in the build container.
