# ScoutBox 0.8.95

Maintenance release on top of 0.8.94.

- Opportunity list Summary is now backed by a dedicated `list_highlight` field and contains only a few distinctive, evidence-backed signals (for example `Fully remote · occasional travel · dsPIC`) rather than copied job-description prose.
- Existing Opportunities are backfilled during migration so the list is rebuilt immediately after upgrade; future Cloud Web and Local AI classification paths populate the same field.
- Hidden Lead company cells are narrower, the Summary column uses the recovered width, and displayed lead/contact URLs omit `http://`, `https://` and `www.` while the real link target remains unchanged.
- Search-provider liveness heartbeats are hardened and stall-warning defaults are less trigger-happy, reducing false `Possible stall` messages during long provider calls/retries.
- Tiny HTTP health badges keep their compact footprint while rendering text more sharply.
- Rebuild Missing AI Data modal copy is shorter and the range selector is labelled `Selected Duration:`.
