# ScoutBox 0.10.115

Hotfix for 0.10.114 startup health blocking. Source-page location refetch repairs are no longer performed inside Django migrations. Startup migrations are database-only; the source-location repair runs after the application is healthy as a queued BackgroundJob visible in Dashboard Activity.

- Removed external page fetches from migration 0134.
- Added migration 0136 to mark source location repair pending for a post-startup background job.
- Updated the country/location repair job to release 0.10.115 with Dashboard Activity visibility.
- Preserved the 0.10.114 UI/data fixes, including source-faithful Jobicy locations, no persisted Worldwide location, independent Focus taxonomies, normalized toolbar heights, `< 3 days`, and Evergreen post age.
