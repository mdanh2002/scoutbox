# ScoutBox 0.10.91

- Fixed bulk Delete for list checkboxes associated with an external bulk form via HTML `form=` attributes.
- Replaced text Show Deleted buttons with compact two-state icon controls; removed the dashed deleted-row divider.
- Added inline Show Deleted / Restore support to Campaigns while leaving Campaign Templates on their existing hard-delete semantics.
- Strengthened employer identity recovery: Working Nomads is classified as a platform, implausible sentence/team fragments are rejected, and strong summary evidence such as `OpenAI seeks...` or `... at NinjaOne` can replace weak local-GPU company guesses.
- Added upgrade-time repair for obvious platform/fragment company identities and cleared contaminated company intelligence for those rows.
- Fixed sortable-header right-side gutters for Added/Created/date columns across the main list tables.
- Removed generic BackgroundJob starvation from forum acquisition and added bounded round-robin forum source rotation. Primary discovery still preempts forum work and AI qualification still respects the AI lane.
