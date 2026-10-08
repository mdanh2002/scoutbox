# ScoutBox 0.8.102

## Outgoing mail / Resend

- Fixed External Mail tests continuing to use previously saved SMTP settings after the Outgoing service was changed to Resend API.
- `Send test email` now posts the current Outgoing form values, persists the selected delivery method and current outgoing credentials, and then sends synchronously through that method.
- Switching the Outgoing service now regenerates the test subject/body label so the UI clearly says `Resend API` or `SMTP` before the test is sent.
- Failed and successful sends continue to be written to Email History with the actual outgoing server/provider (`Resend API api.resend.com` or the SMTP host/port).
- Internal Development remains SMTP-only.

## Daily digest recipient

- Added `Configuration > General > Daily digest recipient`.
- Scheduled daily digests use this explicit address instead of implicitly picking an administrator every run.
- `Send Test Digest Email` uses the address currently entered in that field and saves it before sending.
- When the field is empty, ScoutBox initializes it from the first active administrator email. Migration `0060` backfills existing installations, and the General settings page/task also self-heal an empty value.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application files, and run the normal restart/upgrade flow so Django applies migration `0060_v08102_digest_recipient`.
