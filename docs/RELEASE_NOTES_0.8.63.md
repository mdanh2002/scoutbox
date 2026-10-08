# ScoutBox 0.8.63 release notes

Released 23 August 2026.

ScoutBox 0.8.63 is a focused Provider Configuration layout and Address Book review-state release. Automatic Cloud provider priority routing behavior is preserved.

## Provider Configuration

- Removes the redundant Provider configuration heading from the Providers tab.
- Aligns provider fields and action controls more consistently.
- Renames Validate to **Validate Config** and Test to **Test configuration**.
- Left-aligns **Save Provider Configuration**.
- Adds spacing above Automatic Cloud provider priority.
- Shows priority inline as **Select priority: 1: [provider] 2: [provider] 3: [provider]**.
- Replaces the longer routing explanation with **Priority order: 1 = highest, then 2, then 3.**
- Left-aligns **Save priority**.
- No provider-routing logic is changed.

## Address Book

- Adds a New/Seen state backed by `Contact.is_read`, following the existing read-state convention while using contact-appropriate terminology in the UI.
- Existing contacts are marked Seen during migration; newly discovered contacts default to New.
- Adds Selected/All Mark as New/Seen actions after Delete Selected.
- Shows a badge and bold Address Book navigation item while non-generic New contacts exist.
- Adds State to the Address Book XLSX export.

## Migration

- Adds `0037_v0863_contact_new_seen.py`.
