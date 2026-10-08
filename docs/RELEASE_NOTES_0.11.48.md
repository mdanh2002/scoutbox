# ScoutBox 0.11.48

## Changes
- Fixed the Statistics Global Activity Map Blacklist layer appearing empty even when blacklist records existed.
- Blacklist entries can now reuse evidence-grounded locations already retained on matching Opportunities, Hidden Leads, and Address Book records.
- Retained structured latitude/longitude evidence is used directly when available, so precise locations do not depend on a hard-coded city-name list.
- Matching uses ScoutBox's conservative normalized company identity and verified company-domain logic, preventing job-board/ATS domains from being treated as employer locations.
- Blacklist map markers no longer claim `Worldwide` when no location evidence exists.
- The Blacklist legend now distinguishes mapped entries from the total blacklist count when some entries have no defensible geographic location.
- TLD-based location guessing and broad country/world centroids remain disabled.

## Validation
- Added ScoutBox 0.11.48 static regressions for blacklist evidence reuse, safe matching, mapped/total legend counts, and the existing no-TLD/no-worldwide safeguards.
- Python AST parse and compileall.
- Statistics JavaScript syntax check.
- Docker Compose YAML parse.
- Shell syntax checks.
