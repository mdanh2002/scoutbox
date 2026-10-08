# ScoutBox 0.11.72

- `restart_scout_box.sh` now explicitly builds and starts the optional `stats_service` sidecar when its source folder is present.
- External Statistics remains a soft dependency: if the sidecar source folder is removed from a public/community bundle, or if its build/start fails, ScoutBox continues to rebuild and restart normally.
- Mandatory ScoutBox images are built explicitly so a missing optional sidecar build context cannot abort an upgrade restart.
- The optional sidecar is started after the web migration/bootstrap phase so migrated External Statistics credentials are available before synchronization begins.
