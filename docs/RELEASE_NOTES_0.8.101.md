# ScoutBox 0.8.101 release notes

ScoutBox 0.8.101 completes the 0.8.100 work and adds two focused corrections requested after review: less repetitive Opportunity summaries and Resend API support for External Mail.

## Opportunity summaries

- Local/fallback Opportunity summaries no longer mechanically end in `fit`.
- Concrete role/JD terms remain first, followed by a short explanation of the relevant work. Examples now read like:
  - `AUTOSAR + MIPS/PowerPC — embedded firmware and platform work`
  - `DITA/Sphinx/MkDocs + technical writing — technical documentation and developer education work`
  - `Linux + networking — systems-adjacent; check for deeper low-level scope`
- Adjacent roles explicitly say when the overlap is limited rather than pretending they are a strong match.
- Cloud Web Discovery continues to use AI-authored 20–30 word summaries (maximum 50 words) and is instructed not to end with generic labels such as `fit`, `good fit`, or `technical fit`.
- Migration `0059_v08101_outgoing_resend_summary.py` rebuilds empty historical summaries and known older synthetic `... fit` summaries from retained role/JD evidence. Other human/AI-written non-empty summaries are left alone.

## External Mail: Incoming / Outgoing and Resend

- For **External Mail**, the Email configuration tabs are labelled **Incoming** and **Outgoing**.
- For **Internal Development**, the tabs remain **IMAP** and **SMTP** only.
- External Mail now has an Outgoing service selector:
  - SMTP
  - Resend API (resend.com)
- Resend configuration stores the API key encrypted and uses the standard `https://api.resend.com/emails` endpoint.
- Sender name and From email remain shared outgoing identity settings. The From domain must already be configured/verified with Resend.
- SMTP credentials remain saved when Resend is selected, so switching back does not require re-entering them.
- Outgoing test mail uses whichever service is selected and runs synchronously.
- Email History records Resend deliveries with `Resend API api.resend.com` in the Server column, including failed attempts.
- Internal Development is forced to SMTP even if an invalid/stale database value suggests otherwise.

## Included 0.8.100 changes

- Empty Opportunity-summary repair from retained JD/source evidence.
- Local GPU filtering of predominantly non-English Opportunity and Hidden Lead pages, while allowing small foreign-language passages/characters. Cloud discovery remains unrestricted.
- Cloud Chatbot **Allow internet search** option with provider-native grounding and matching Test Chatbot behavior.
- Campaign worker heartbeat during long search/fetch/AI calls to reduce false **Possible stall** status.
- Synchronous outgoing test mail and Email History Server tracking.

## Upgrade

Keep `.env` and Docker volumes, replace application files, and run `./restart_scout_box.sh`. Migration `0059_v08101_outgoing_resend_summary.py` is applied automatically by the normal restart path.
