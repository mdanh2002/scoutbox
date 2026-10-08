# ScoutBox 0.9.1

## AI request timeout controls

- Adds **AI & Discovery → Miscellaneous** with three persisted per-provider-attempt controls:
  - Local AI request timeout: 180 seconds default.
  - Cloud AI request timeout: 120 seconds default.
  - Chatbot provider timeout: 300 seconds default.
- Each setting accepts 30–300 seconds and is validated server-side as well as by the form controls.
- Adds Save and Restore Defaults actions.
- Local Ollama generation, Cloud generation/web research, and Chatbot provider attempts resolve their effective timeout from these settings. Legacy per-call timeout arguments remain compatible but no longer create hidden production timeout differences.
- Chatbot Primary and Secondary attempts each receive the configured Chatbot provider timeout; a slow Primary no longer consumes a hidden aggregate deadline that starves Secondary.
- Other network/connector timeouts are not changed.

## Resource Usage and Dashboard responsiveness

- CPU/RAM/Tokens canvas sizing follows the available card width rather than enforcing a minimum canvas width.
- On laptop-width layouts, current-value details move below the Resource Usage chart so the chart can use the full card width without page-level horizontal scrolling.
- Dashboard activity cards use responsive auto-fit columns and remain contained within their cards.
- CPU/RAM/Tokens x-axis ticks adapt to the represented span: time labels for short ranges, date/time for multi-day ranges, and reduced date/month labels for longer ranges.
- Resource samples for Week/Month/All/Custom ranges are aggregated/downsampled across the complete selected period. Live refresh merges the newest sample into that range instead of replacing the chart with the last few samples.

## ToughDev connector layout

- ToughDev blog statistics settings use one compact vertical field column with a narrower Port field.
- Compatibility mapping uses the same alignment.
- Connector state, save, and read-only SELECT behavior are unchanged.

## Schema

Migration `0072_v091_ai_request_timeouts` adds the three timeout fields to `PortalSettings`.
