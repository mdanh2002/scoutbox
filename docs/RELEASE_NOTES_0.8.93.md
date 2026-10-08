# ScoutBox 0.8.93

Startup hotfix based on 0.8.92. No database migration is added.

- Fixes the 0.8.92 web-container restart loop caused by `portal/services/mailbox.py` importing `bleach.css_sanitizer.CSSSanitizer` while `tinycss2` was absent from the Docker runtime dependencies.
- Adds `tinycss2` explicitly to `requirements.txt`, preserving the safe CSS-capable email preview introduced in 0.8.92.
- Adds a release regression guard so a CSSSanitizer import cannot be shipped again without its runtime dependency declaration.
- Retains all ScoutBox 0.8.92 features and data-preserving upgrade behavior.
