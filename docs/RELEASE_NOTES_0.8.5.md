# ScoutBox 0.8.5 release notes

0.8.5 focuses on day-to-day list usability, discovery diagnostics, Market Studies workflow, email testing and navigation consistency. It is an additive upgrade from 0.8.4 and preserves `.env`, credentials and persistent Docker volumes.

## Market Studies and opportunities
- Cold Contact / Hidden Market is renamed **Market Studies** throughout day-to-day navigation and chatbot links.
- Lead matching displays compact Areas text rather than the old “Relevant technical work:” prefix; migration 0007 cleans existing rows.
- The Market Studies screen removes the duplicate heading, places last-scanned state under Leads, moves Manual Scan/Add Lead to the upper right and keeps scan progress directly below the heading.
- Search, Rows and XLSX export share one toolbar; each lead can prepare an application directly.
- Lead details show only one URL when Search URL and Target URL are identical.
- Opportunities place search/status/Rows/XLSX together, support select-all and bulk deletion, and remove the duplicate row-level prepare action.

## List management
- Application Drafts removes the Add Manually tab; Add Manually is a grid action beside bulk deletion, and the duplicate page heading is removed.
- Address Book removes its duplicate heading, moves Add Contact beside Search, adds row/master selection and bulk deletion, and retains only Edit as the row action.
- Blacklist removes the duplicate “Blocked Sources” label, moves Add Domain beside Search, adds row/master selection, explicit Edit dialogs, Reset to Defaults with confirmation, and linked domain cells that open in a new tab.
- XLSX export controls are placed immediately to the right of Rows selectors on major list views, with additional exports for Campaigns/Templates, Campaign detail lists, Email History tabs, Performance Lab, Imports, Search Sources activity and AI Test Discovery runs.

## Resource Usage and Statistics
- Resource Usage now initializes Last updated immediately and keeps quick periods plus custom date range on one line.
- Search Provider Performance aggregates requests, returned pages, unique matches, applied matches, duplicates, errors, average latency, downloaded bytes and the latest provider error.
- Statistics includes Opportunities by Discovery Source, attributing target URLs to non-provider discovery-source presets rather than search-engine providers, with a table and donut chart.

## Discovery Sources
- Non-search-provider source names link to their configured home pages in a new tab.
- Excluded / low-value marketplaces now include Fiverr, PeoplePerHour, Guru, Truelancer and Workana in addition to the existing defaults.

## Email and system configuration
- IMAP Browser lists actual folders directly without an empty “Choose folder” entry.
- Inbox, Drafts and Sent mapping remains a separate configurable control with automatic defaults.
- Internal Development gains **Populate Test Emails**, which appends representative messages to the mapped Inbox, Drafts and Sent folders.
- System Configuration no longer shows the duplicate global/local tab bar on the General settings page.
- Maintenance is reduced to the destructive action buttons; explanatory text and typed CLEAR/RESET confirmation live in dialogs.

## Navigation and chatbot
- The top-left Portal Admin link is removed; Logout sits on the ScoutBox identity row.
- Chatbot transcript and open/closed state persist in browser storage across ordinary ScoutBox page navigation.

## Upgrade
Keep the existing `.env` and Docker volumes, replace the application files, then run:

```bash
chmod +x restart_scout_box.sh
./restart_scout_box.sh
```

Do not rerun the initial setup script on an existing installation.
