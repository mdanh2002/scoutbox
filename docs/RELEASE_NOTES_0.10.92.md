# ScoutBox 0.10.92

- Fixed the 0.10.91 `_JOB_AGGREGATOR_BRANDS` NameError in job-board candidate consolidation by using the shared platform/domain classification path.
- Known 0.10.91 failures from that regression no longer keep repaired campaigns circuit-broken for the rest of the current discovery window after upgrade.
- Forum acquisition now defaults to one bounded source about every 15 minutes and rotates sources on a 15-minute bucket. Forum HTTP acquisition can proceed on its dedicated worker while primary campaigns run; AI qualification still yields naturally when AI capacity is unavailable.
- Deleted Opportunities, Hidden Leads, Applications/Outreach records, Address Book contacts, Blacklist rows and Campaigns render with disabled unchecked row checkboxes. Select-all and selected-item re-evaluation therefore cannot include recycle-bin items. Server-side re-evaluation remains active-row-only.
- Re-evaluate explanatory text was shortened and rendered at a smaller helper-text size.
- Blacklist helper text was shortened and rendered at the same compact size.
- Diagnostics now describe the periodic bounded Forum policy rather than the old deep-idle-only policy.
