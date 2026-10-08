# ScoutBox 0.8.79 Release Notes

ScoutBox 0.8.79 is a focused review-UI and Ask ScoutBox polish release. It keeps the 0.8.78 discovery/data behavior and corrects presentation and Chatbot usability issues found during live review.

## Post Age and Hidden Leads

- Evergreen Post Age now places a larger leaf icon above a centered `Evergreen` label in list views.
- Post Age confidence remains encoded by the existing text/icon colour; no confidence percentage is added back to the list cell.
- Hidden Lead HTTP health remains beside the company name, but uses a smaller intrinsic badge so `200`/`404` does not compete with the external-link affordance.

## List controls

- Company-country filters use a shorter, consistent width across Opportunities, Hidden Leads, Address Book, and Applications & Outreach.
- Applications & Outreach now uses the same searchable country picker behavior as the other primary lists.
- Export actions are square, borderless icon controls with a clear hover state instead of squeezed bordered buttons.
- Application ID values remain centered horizontally but are top-aligned with the rest of the row content.

## AI & Discovery / Chatbot

- Chatbot provider/model configuration is constrained to a practical width instead of stretching across the page.
- The Higher-cost configuration warning was removed from Cloud AI Limits; hard limits and quota behavior are unchanged.
- Ask ScoutBox keeps the model-driven path and compact workspace context, but recommendation questions now ask the configured model for a fuller answer: a clear choice, reasons, caveat, and next action where supported by the stored context.
- Upgrade migration `0045_v0879_chatbot_output_default.py` changes only the old shipped 450-token Chatbot answer cap to the current 5,000-token default. Other explicit user-set caps are preserved.
