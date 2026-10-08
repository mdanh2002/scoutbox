# ScoutBox 0.11.127

## Re-evaluation result layout

- Opportunity, Hidden Lead, and Address Book result Search fields now occupy about 25% of the detail pane instead of stretching across most of the modal.
- Result tables now fit the available detail pane without forcing the Reason column off the right edge.
- The Refreshed column is removed from all three result list views.
- Entry, Item Date, Decision, Fit (including confidence), and Reason remain sortable.

## Full-run XLSX export

- The footer export now downloads XLSX instead of CSV.
- Export is generated from the complete selected re-evaluation run on the server.
- Current search text, sort order, page number, and page size do not limit the export.
- The workbook contains Entry, Item Date, Decision, Fit/confidence, and Reason for every meaningful result row.

Migration `0199` is release-audit only; there is no schema change.
