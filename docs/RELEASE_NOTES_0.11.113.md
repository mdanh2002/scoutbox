# ScoutBox 0.11.113

- Validates custom **From / To** date ranges consistently in **Statistics**, **Resource Usage**, and every list view that uses the shared date-range control.
- The filter button is disabled until both From and To are entered; an incomplete range cannot be applied.
- Requires **From** to be strictly earlier than **To** and rejects malformed calendar dates.
- Caps manually entered and calendar-selected dates at the application's local **today + 1 day**, allowing a one-day timezone cushion while preventing clearly future ranges.
- Adds the same validation server-side so invalid custom ranges cannot be applied by bypassing browser controls.
- Invalid fields are visually marked and the disabled filter button explains the validation issue in its tooltip.
- Preserves the 0.11.112 rule that Statistics and Resource Usage preset segments do not by themselves highlight the separate filter icon.
- Preserves all Tracking Links, resource-chart hover, and other behavior from 0.11.112.

Next release: 0.11.114.
