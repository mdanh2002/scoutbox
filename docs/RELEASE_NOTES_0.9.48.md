# ScoutBox 0.9.48

## Credential helper compatibility

- Fixed `./print_creds.sh` on macOS's older Bash when `set -u` is enabled and no optional argument is supplied.
- The helper no longer expands an empty Bash array. Both normal use and `--include-infrastructure` retain the same behavior and warning.

## Regression script housekeeping

- Removed historical `scripts/regression_v*.py` files from the release package.
- `scripts/regression_v0948.py` is now the only versioned regression script shipped.
- The release verifier runs only that current regression suite. Important retained hardware/About compatibility assertions are folded into the current suite rather than depending on an older versioned test file.

No application behavior, provider routing, Opportunity behavior, database schema, or UI behavior is changed in this release.
