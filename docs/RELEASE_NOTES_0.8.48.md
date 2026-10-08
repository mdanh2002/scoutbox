# ScoutBox 0.8.48

0.8.48 is a focused corrective release on top of 0.8.47.

## Chatbot

- Adds Recycle Bin and deleted-item lifecycle knowledge to the portal-wide product guide.
- Stable navigation/product questions are answered directly from ScoutBox's own product map when possible, so simple help does not fail just because the configured model is unavailable or weak.
- Exact Chatbot provider/model routing remains persistent across navigation by merging route data from legacy routing-holder rows.
- Adds **Test Chatbot** beside **Save chatbot**. The test forces a real request to the exact currently selected provider/model using a fixed ScoutBox question and displays the returned answer in a modal.
- Empty model responses now direct the user to Test Chatbot/provider selection rather than returning the old generic fallback text.

## UI

- Schedule / Limits headings are aligned with the controls below.
- Recycle Bin uses a clearer blocked-domain shield icon for Blacklist items.
- Address Book/email item-type icon is slightly smaller for balance.

No new database migration is required.
