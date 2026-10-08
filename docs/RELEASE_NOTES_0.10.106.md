# ScoutBox 0.10.106

- Fixes Campaign Template deleted-view controls: Delete no longer appears stuck after confirmation, Show Deleted uses its own `show_deleted_templates` state, and deleted templates can be restored inline from the Templates tab.
- Replaces automatic full Focus rebuilds with blank-only Focus recovery. Upgrade stops stale Focus taxonomy jobs, reuses stable campaign-local labels for blank rows where safe, and keeps existing Focus labels untouched.
- Clears noisy Hidden Lead notes and hides unsuitable-opportunity provenance snippets from the Hidden Leads list.
- Keeps remote/timezone/work-arrangement prose out of Opportunity role-location display; those details remain in the Remote column.
- Adds a small loading spinner beside Dashboard Discovery Activity while a user-selected range is being fetched.
- Makes the Focus dropdown panel match the width of the Focus selector.
