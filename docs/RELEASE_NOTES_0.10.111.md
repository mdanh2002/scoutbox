# ScoutBox 0.10.111

## Added

- Multi-location support for Opportunities, Hidden Leads and Address Book records.
- Recruiter-region labels such as Europe, EU, UK & Europe, APAC, Asia, EMEA, Middle East, Africa, LATAM, North America, Worldwide and Global.
- `~ 3 days` post-age display/filter bucket for sub-week posts.
- Internal worldwide source-domain expansion for known job boards and career sites.

## Changed

- Location filters can count and match multiple countries/regions retained in a single record.
- Focus assignment performs stricter membership validation so good labels are not polluted by weak token matches.
- Async list loading always releases spinner state even for aborted/stale requests, with a defensive timeout.

## Fixed

- Jobicy-style `Remote from Europe, Ukraine` records no longer collapse into an arbitrary country such as Albania.
- Hidden Lead blacklist modal/actions now allow a safe direct company domain when the company name is blank.
