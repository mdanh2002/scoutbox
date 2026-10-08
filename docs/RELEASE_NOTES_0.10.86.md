# ScoutBox 0.10.86 Release Notes

## Fixes

- Opportunity blacklisting now creates exact company-name rules only. It no longer stores the source/job-board host as the blacklist domain, so aggregators such as Himalayas, LinkedIn, Indeed and similar boards cannot hide unrelated Opportunity rows.
- The v0.10.86 data migration automatically recycles bad non-built-in Opportunity blacklist rows that targeted aggregator domains, converts plausible selected companies to label-only blacklist rules, and restores Opportunity rows that were suppressed only by those bad aggregator-domain rules.
- The bulk Opportunity blacklist confirmation dialog now shows every selected row in a scrollable review table with Domain and Company columns. Rows can be checked or unchecked before submitting, and the selected count updates live.
- Post-age tooltips now use stored post-age evidence fields such as `exact_source` and acquisition metadata, avoiding misleading `Source: Unknown` when evidence exists.
- The Added/Created timestamp columns in Opportunities and Address Book now have explicit right-side spacing so dates are not pinned to the cell edge.

## Upgrade notes

No manual SQL is required. The recovery runs as Django migration `0112_v01086_blacklist_aggregator_recovery` during the normal ScoutBox startup upgrade path.
