# v0.4.1 release notes

v0.4.1 is a small credential-recovery/inspection release built on v0.4.0. Search, discovery, ranking, mail workflow, AI routing, token caps, CV-first query generation, import inference, telemetry and tracking behaviour are otherwise unchanged.

## New root helper: `print_creds.sh`

Run:

```bash
./print_creds.sh
```

The helper invokes `python manage.py print_creds` inside the portal environment so encrypted database values are decrypted using the same Fernet configuration as the running application.

It prints:

- both saved Email Profiles, including IMAP and notification-SMTP passwords;
- Mailpit UI and SMTP development credentials;
- GreenMail development IMAP credentials;
- saved OpenAI and Gemini API keys (Ollama normally has no API key);
- Brave Search API key from the runtime environment;
- saved Facebook/Meta Graph token and authenticated browser cookie header, with environment fallback where applicable;
- ToughDev blog-statistics read-only MySQL credentials.

Django administrator passwords cannot be recovered because only their one-way hash is stored. Use `./reset_admin_password.sh` for administrator recovery.

An optional troubleshooting mode is available:

```bash
./print_creds.sh --include-infrastructure
```

This also prints PostgreSQL and selected application environment secrets. Because the output contains live credentials, avoid running either mode where terminal output is logged, recorded or shared.
