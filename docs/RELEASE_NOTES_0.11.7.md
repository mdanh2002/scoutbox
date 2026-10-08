# ScoutBox 0.11.7

Address Book re-evaluation UI hotfix.

- Defines the missing `showContactFilterProgress()` Address Book progress renderer.
- Restores live Address Book re-evaluation progress updates instead of leaving the list page stuck on its initial server-rendered progress value.
- Adds missing Address Book completion summary helpers used when a re-evaluation finishes.
- Marks finished Address Book re-evaluation progress as 100% before reload/summary.
- Frontend-only change; no backend, migrations, search, location, Focus, or repair logic changes.
