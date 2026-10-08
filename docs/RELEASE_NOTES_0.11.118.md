# ScoutBox 0.11.118

ScoutBox 0.11.118 fixes a runtime failure in manual re-evaluation when a cloud AI provider uses the parallel evaluation path.

## Re-evaluation runtime fix

- Restores the missing `concurrent.futures` import in `portal/tasks.py`.
- Fixes the observed `Hidden Lead re-evaluation failed · name 'concurrent' is not defined` error.
- The same shared missing import affected the parallel **Opportunity** and **Address Book** re-evaluation paths; this release fixes all three together.
- Local/non-parallel re-evaluation behavior is unchanged.
- Parallelism, provider selection, filtering decisions, protection rules, and recycle behavior are unchanged.

## Regression coverage

- Verifies that `concurrent.futures` is imported before any of the three parallel re-evaluation helpers can use it.
- Verifies that Hidden Leads, Opportunities, and Address Book all retain their `ThreadPoolExecutor` / `as_completed` execution paths.
- Performs a targeted AST symbol audit of those helpers to catch another missing module-level name of this class.
