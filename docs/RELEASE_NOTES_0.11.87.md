# ScoutBox 0.11.87

## Facebook Pages and Tracking Links

- Repaired Facebook Pages bulk Mark as Seen/New actions by correctly reading form-associated selections.
- Added search-as-you-type, server-side sorting for every data column, standard numbered pagination and consistent toolbar sizing.
- Replaced pending-title text with a compact clock indicator and tooltip, widened Discovery Evidence, and corrected Page ID link contrast.
- Made All and Mark actions visually neutral until a specific state/action is active.
- Changed Tracking Links synchronization to a refresh icon, removed the misleading human-click subtotal, and allowed the same-origin Add Tracking Link page to render inside its modal.

## Resource Usage, Market Coverage and Search Activity

- Kept request/token history across the selected chart range even when CPU/RAM samples have a shorter retention window; missing hardware samples remain absent rather than being reported as zero.
- Matched Market Coverage height to Discovery Performance, fixed the chart in place and made only long legends scroll.
- Restored Discovery Activity as a separate table after Market Coverage.
- Corrected Search Activity market names for both language-country and country-language provider settings, including `ko-KR` and `kr-kr`.
- Reduced the Search Activity request-count weight.

## List views, profile and About

- Made Blacklist scope choices derive from non-zero scope types present in the current list.
- Kept Candidate Profile Operating locations aligned in the second form column and limited the field to 10 unique locations while allowing it to grow vertically.
- Presented Common data checks, Useful scripts & key files, Terminal & SQL examples, Redis usage and External Statistics as distinct reference cards without redundant top rules.
- Standardized External Statistics command-card label typography.
