# v0.7.1 release notes

- Patch release over v0.7.0; ScoutBox functionality and configuration remain unchanged.
- Fixes first-start Django failure: `portal/admin.py` no longer attempts to register abstract model base classes such as `SingletonModel` with Django admin.
- Concrete `portal` models continue to be automatically registered with the optional Django admin.
- Includes the previously supplied `initial_setup_macos.sh` helper in the package root for easier fresh macOS installation.
- No database migration is required.
