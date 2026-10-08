# ScoutBox 0.8.68 release notes

ScoutBox 0.8.68 refines Discovery routing, quota diagnostics, run context and error-preview behavior. It adds no database migration and preserves existing campaigns, opportunities, leads, applications, provider credentials and saved local stage routes.

## Discovery routing

- Discovery Method remains the single user-facing algorithm switch: **Source-Guided** or **Cloud Web**.
- Source-Guided exposes the stage table and limits its model choices to enabled local Ollama models. Blank primary selection means **Automatic local**; saved Cloud selections from older releases are retained in storage but ignored by Source-Guided execution.
- Source-Guided keeps **Auto Select Local**, **Optimize for Local**, **Test Selection**, and **Test Discovery**. The former **Optimize for Cloud** action is removed.
- Cloud Web hides the manual stage table. ScoutBox resolves the highest-priority enabled Cloud provider with credentials, a concrete resolved model and usable web capability, then uses the next eligible provider as automatic fallback.
- Compatible Cloud research stages reuse the Cloud Web route where practical; later Cloud stages are also selected automatically from provider priority/capability rather than hidden manual stage values.
- Switching back to Source-Guided restores the saved local routing configuration instead of overwriting it.
- If Cloud Web has no usable web-capable route, ScoutBox returns to Source-Guided rather than leaving a broken Cloud configuration active.
- Cloud provider priority is now explicitly described as the automatic Cloud Web routing order.

## Search Sources quota information

- Neutral information controls now use a muted list/details glyph, clearly different in shape from the amber consumed-quota exclamation mark.
- Both controls remain borderless and click-driven; no quota hover tooltip is required.
- Quota popups present usage as separate points such as consumed today, daily capacity, remaining allowance, scope and reset time.
- Query variants, queries/provider and max-results controls use the same point-form popup pattern for purpose/effect/scope guidance.

## Campaign run context

- Run Now is titled **Add Note for <campaign>** for Source-Guided runs and **Add Custom Instructions for <campaign>** for Cloud Web runs.
- Note/Custom-instruction SVGs are removed from the Run Now field itself; the hint below the text area is contextual to the active mode.
- Campaign-list and Run-History Note/Custom-instruction icons remain, and Note context remains italic.

## Error preview

- The top-right Last 5 Errors preview first selects the newest error from each distinct provider/component, preventing a repeated Bing or other single-source failure from occupying the entire popup.
- If fewer than five distinct components are available, remaining slots are filled with the next-newest errors regardless of component.
- The error badge itself is unchanged and continues to count all new error incidents represented by the existing badge logic.

## Layout

- Source-Guided Primary/Fallback model selectors are wider and the routing table is allowed to scroll horizontally instead of compressing long model IDs.
- All 0.8.67 Maintenance, Address Book, Provider Configuration and Engagement Preferences layout refinements are retained.
## List and editor workflow refinements

- Hidden Leads and Applications/Outreach display their Note in the first list column, consistent with Opportunities.
- Saving Opportunity or Hidden Lead details returns to the relevant list view after a successful save; validation errors remain on the detail page.
- Applications/Outreach **Details** uses **Save Changes**, saves only ScoutBox-side fields, and returns to the list. **Email & Application → Save Draft** continues to update the ScoutBox draft/IMAP Drafts path and remains in the editor.
- Run Campaign hints now show only the explanation relevant to the active discovery mode. Note mode also points to **AI & Discovery → Discovery Method → Cloud Web** for Custom Instructions.
- Query Rotation remains visible and usable for current/next preview, while the per-campaign Queries-per-rotation override row is hidden from Campaign Detail.

## List refresh behavior

- Auto-refreshing list views use a five-minute interval rather than refreshing every few seconds.
- Search Activity keeps the active server-side page during an automatic refresh instead of returning to page 1.
- Client-side paginated list views remember their current page across a reload/refresh within the same browser session.

