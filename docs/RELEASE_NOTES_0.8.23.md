# ScoutBox 0.8.23

ScoutBox 0.8.23 is a maintenance/workflow release on top of 0.8.22. It focuses on Market Studies quality, provider configuration clarity, and a single place for application and outreach tracking.

## Search Sources
- Yandex, Baidu and Naver continue to use **Public Access** as the default access mode when no valid saved mode exists.
- The provider modal now selects and re-selects the configured option when opened, including browser page-cache restores, and explicitly styles the selected option so Public Access cannot render as an empty dark dropdown.
- API credential slots remain separate by access type; switching back to Public Access does not delete saved credentials.
- The Custom Domains note is shortened to `Source-guided: adds site:domain searches.` and sits on the same footer line as the page counter/pager.

## Market Studies
- Automated legacy summaries are reset once during migration 0020 and rebuilt under the new summary rules.
- Summaries are natural two-sentence notes with no `Why selected` / `Potential use` labels. The first sentence explains the real product/service/project context and prefers named offerings supported by first-party evidence. The second sentence gives one practical outreach angle without repeating the same keyword list or implying a vacancy.
- Asynchronous refinement fetches the organization homepage as supporting context before summarization, which gives the model a better chance to identify actual products/platforms/services when the original search hit is a deep technical page.
- Product names are no longer guessed from generic article/page titles. Blog/personal-style paths without organization/service signals are filtered more aggressively during new scans.

## Applications & Outreach
- The separate **Applied Roles** and **Application Drafts** navigation surfaces are consolidated into **Applications & Outreach**. Legacy URLs remain as redirects so bookmarks do not break.
- The unified list/editor retains role/company/country/channel/status/applied date/contact/source URL/description/notes/Resume/cover-letter/email/IMAP fields, read state, export, bulk actions, mailbox synchronization and historical application import.
- Manual records can be marked as Application or Outreach.
- Market Studies **Prepare Outreach** now creates the unified outreach record immediately before AI generation begins. When drafting finishes, the worker updates that record and attempts to save the same content to IMAP Drafts. A missing/unavailable email profile no longer makes the ScoutBox draft disappear.
- Migration 0020 backfills Market Studies drafts produced by earlier versions into Applications & Outreach.

## Upgrade
Run the normal `./restart_scout_box.sh` upgrade path so migration `0020_v0823_unified_applications_summary_reset.py` is applied. The migration does not change the database schema.
