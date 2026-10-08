# ScoutBox 0.11.100

- Fixes the Dashboard 500 caused by the Tracking Links metric reversing the non-existent `tracking_links` URL name; the card now targets the existing `links` route.
- Aligns Tracking Link editor labels and all three control rows to one fixed label gutter, including DOCX file/scan controls.
- Removes the empty Acquisition Path toolbar row by moving Export into the card heading.
- Avoids duplicate Audit Trail detail text when a BackgroundJob object title is identical to the audit summary; the secondary line then shows only the object reference, e.g. `(BackgroundJob 7431)`.

The next release is 0.11.101.
