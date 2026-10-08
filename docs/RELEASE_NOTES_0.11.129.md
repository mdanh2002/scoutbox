# ScoutBox 0.11.129

## Candidate Profile autopopulation

- Added **Autopopulate Candidate Profile** beside **Auto-create Campaign Templates** in Candidate Profile → Resumes.
- Runs in the background instead of blocking the page.
- Reads every current uploaded Resume; readable files are analysed independently and unreadable files are explicitly reported as skipped.
- De-duplicates merged terms and respects the existing 160 Resume-concept and 80 likely-role limits.
- Uses fair round-robin merging across Resumes so a long Resume cannot crowd out shorter Resumes.
- Keeps deterministic Resume-grounded technology/domain extraction even if AI extraction fails for an individual Resume.
- Replaces only `cv_concepts` and `likely_roles`; other Candidate Profile preferences and fields are preserved.

## Progress and cancellation

- Candidate Profile shows a top-of-page status notice while autopopulation is queued/running.
- The notice links directly to Dashboard Background Work.
- Dashboard shows the activity as **Candidate Profile** and provides the standard Stop control.
- The profile vocabulary is saved only after the full all-Resume pass completes, so stopping before completion leaves the prior vocabulary unchanged.

## Compatibility

- Existing 0.11.128 Resume-grounded manual re-evaluation and diagnostics behavior is unchanged.
- The 0.11.128 one-time Candidate Profile vocabulary migration marker remains satisfied; the new manual autopopulation algorithm is tracked separately.
