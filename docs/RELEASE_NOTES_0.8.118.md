# ScoutBox 0.8.118 release notes

## UI corrections

- Replaced the level-1 Fit downward-arrow glyph with `?` so a very-low fit score can no longer be mistaken for a download action. The score/confidence tooltip remains available.
- Shortened Daily digest recipient and Portal Root URL controls in General settings.
- Shortened editable fields in Users / My account / Add administrator while retaining responsive sizing.
- IMAP Browser refresh/detection completion messages no longer linger after successful background operations.
- Replaced the IMAP Detect magnifying-glass icon with a folder-detection icon and retained descriptive tooltips.
- Left-aligned Generate Test Email.

## Compatibility

No database migration is required. The latest migration remains `0069_v08111_chatbot_source.py`.
