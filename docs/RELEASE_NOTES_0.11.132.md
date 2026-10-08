# ScoutBox 0.11.132

## Re-evaluation reliability

- Fixed a Python prompt-construction defect in Opportunity and Hidden Lead manual re-evaluation that applied unary `+` to a string and caused `bad operand type for unary +: 'str'` before the AI provider request was sent.
- Added executable regression coverage for both Local and Cloud prompt-building paths so this class of runtime-only string-expression error is caught before release.
- Added a repeated-internal-error circuit breaker. If the same programming/runtime error hits the first three checked entries, the batch is marked failed and stops feeding the remaining queue instead of producing hundreds of identical failures.
- Cloud re-evaluation now keeps only the configured five tracks in flight rather than pre-submitting the entire batch, making early-stop behavior effective and limiting unnecessary provider work.
- Parallel Cloud re-evaluation now honors the existing repeated-empty-response circuit breaker instead of only counting empty responses.
- A batch in which every selected entry fails is persisted as **failed**, not as a normally completed re-evaluation.
- Added the missing `timed_out` result counter to Local Opportunity, Hidden Lead, and Address Book re-evaluation result state, preventing a completion-time key error in Local Opportunity/Hidden Lead runs.
- Early Local re-evaluation stops now clear the in-flight item marker before persisting the terminal result.

## Re-evaluation scope dialog

- Widened the shared scope chooser so **View Past Results**, **Cancel**, **Local AI Only**, **Cloud AI Only**, and **All Items** fit without overflowing off the left edge.
- Corrected two historical CSS selectors that accidentally widened the generic confirmation dialog instead of the re-evaluation scope chooser. Compact confirmation dialogs remain compact.
- Narrow/mobile layouts continue to wrap scope actions when needed.

## Compatibility

- No database schema or user-data transformation is required; the migration records the 0.11.132 release in the audit log only.
- Candidate Profile document alignment from 0.11.131, Candidate Profile autopopulation, discovery, stored re-evaluation history, and provider/model configuration remain compatible.
