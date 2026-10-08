# ScoutBox 0.10.85 Release Notes

## Fixes

- Prevents Local AI lane deadlocks from leaving campaigns apparently running while CPU/GPU are idle.
- Changes Ollama generation to streamed requests with a true wall-clock timeout, so a stalled HTTP/proxy connection cannot hold the Local AI lane indefinitely.
- Adds heartbeat metadata to Redis Local AI lane locks and reclaims stale or legacy v0.10.84-style locks automatically.
- Propagates Local AI lane contention out of pre-persistence discovery, fit/remote enrichment, and company research instead of swallowing it as a normal classification failure.
- Lowers stale heartbeat recovery thresholds to fail clearly abandoned campaign runs faster; the independent worker heartbeat still protects healthy long-running provider/model calls.
- Reduces stale limits for AI-backed background jobs such as Company Research and Summary jobs so interrupted workers do not leave permanent running placeholders.
- Adds an upgrade migration that marks stale running campaign/background AI rows as failed so v0.10.84 residue does not survive deployment.

## Operational note

After installing this version, recreate the full Compose stack so any old worker processes and legacy Redis Local AI lane locks are gone. v0.10.85 also self-reclaims old lock values when a new worker encounters them.
