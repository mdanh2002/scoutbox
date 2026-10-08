# ScoutBox 0.9.19

## About ScoutBox troubleshooting readability

- Moves `./print_creds.sh` out of **Common data checks** and into **Useful scripts & key files**, where it sits with the other operating/recovery helpers.
- Renames **Common data checks and credentials** to **Common data checks**.
- Rewrites the long Django ORM examples as copyable multi-line `docker compose exec ... manage.py shell -c` commands.
- Changes those command blocks to wrap safely instead of creating horizontal scrollbars.
- Keeps the commands read-only and preserves the operational guidance for workers, Redis, Beat, AI Requests, Resource Usage and Diagnostic Data.

No database migration is introduced in 0.9.19.
