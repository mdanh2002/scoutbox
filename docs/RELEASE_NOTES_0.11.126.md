# ScoutBox 0.11.126

## Re-evaluation result list views

- Opportunity, Hidden Lead, and Address Book re-evaluation histories now provide a Search field and filtered total at the top of each selected run.
- Every result column is sortable.
- Results paginate at 50 rows by default, with 25/50/100/200 row choices.
- The footer provides CSV export plus page number and first/previous/numbered/next/last navigation.
- Item Date appears immediately after Entry and is populated from the original record date, including recycled records.
- The separate Confidence column is removed; confidence is shown compactly inside the Fit cell.
- The redundant `Showing N ... re-evaluation results` text in the modal header is removed.

## Restore clarity

- Recycled-result Restore confirmations include the Opportunity title/company, Hidden Lead company, or Address Book contact/company identity.
- Existing Keep/Recycle/Failed colors and recycle/restore mechanics remain unchanged.

Migration `0198` is release-audit only; there is no schema change.
