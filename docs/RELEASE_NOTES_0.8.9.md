# ScoutBox 0.8.9 release notes

ScoutBox 0.8.9 builds on the verified 0.8.8 package. This release is a UI/workflow reliability update and does not add a database schema migration beyond `portal/0008_v086_ui_read_summary.py`.

## Read / unread workflow

- Opportunities and Market Studies both provide **Mark as Read** and **Mark as Unread** actions for selected rows.
- Unread rows continue to use email-style bold emphasis.
- Interacting with an unread row records the row as read without requiring the detail page to be opened. This includes row controls and selection; Select All marks the affected visible unread rows as read. An explicit Mark as Unread action remains the final override.
- Market Studies row-level server actions such as status changes, application preparation, outreach preparation, translation and blacklisting also record the item as read even if the browser-side read update is interrupted by navigation.

## Market Studies and Test Discovery layout

- Market Studies places **Last scanned** on the same line as scan progress, aligned to the far right.
- Test Discovery places **Run test** directly to the right of the **Search runs** field.
- The redundant **ScoutBox Chatbot** heading is removed while the chatbot configuration controls remain unchanged.

## Search provider state clarity

- A configured provider with zero requests for the current day now uses a distinct blue informational indicator.
- Healthy providers with actual traffic remain green; elevated error rate and persistent zero-result states remain separate warning states; unconfigured/disabled providers remain red.
- Dashboard provider-health summary includes the configured/no-requests state separately.

## Blacklist editing

- The edit form now submits an explicit disabled value when the **Blocked** checkbox is unchecked, and the backend parses the boolean explicitly. This prevents unchecked entries from appearing to remain blocked after save.

## Resource Usage and Statistics charts

- Fixed the chart-data handoff used by Django `json_script`: Resource Usage and Statistics now pass native lists/dictionaries instead of JSON strings that were encoded a second time.
- This restores initial rendering for **CPU, Memory & GPU**, **Opportunity Status**, **Search Provider Summary** and **Discovery Source Share** while preserving Y axes and hover details from 0.8.8.
