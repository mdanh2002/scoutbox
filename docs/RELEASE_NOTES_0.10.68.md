# ScoutBox 0.10.68

0.10.68 is a Chatbot action cleanup patch on top of 0.10.67.

## Ask ScoutBox action buttons

- Removes the broad always-on shortcut button row from ordinary Ask ScoutBox answers.
- Keeps chat action buttons exceptional and caps rendered/persisted action links to two.
- Hides legacy generic shortcut buttons from older saved chat messages on display.
- Keeps specific fallback/configuration buttons when ScoutBox cannot answer from the loaded context or needs to send the user to a corrective page.

## Compatibility

No database migration is required. Existing chat history remains available; redundant generic shortcut buttons are filtered at render time.

Routine future releases increment the patch component unless a larger compatibility change is required.
