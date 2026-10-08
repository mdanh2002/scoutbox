# ScoutBox 0.9.49

## Credential recovery mail transport fix

- `print_creds` now reports the effective outgoing service for each saved mail profile.
- External Mail configured for Resend prints `https://api.resend.com/emails` and decrypts the saved Resend API key.
- Stale SMTP credentials remain stored for easy switching back in the UI, but are no longer printed as the active outgoing credentials while Resend is selected.
- SMTP profiles continue to print SMTP host, port, TLS, username and password.

## Email configuration cleanup

- Removes the standalone “Keep ScoutBox outgoing mail separate from your application mailbox identity.” warning from the Outgoing page.

No database migration is required. All other 0.9.48 behavior is retained.
