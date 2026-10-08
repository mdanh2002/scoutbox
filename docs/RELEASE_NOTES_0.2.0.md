# v0.2.0 release notes

## CV-first automatic discovery

- Added a default enabled **CV-first Automatic Discovery** campaign.
- Every scheduled run reads all active CVs/resumes from the document library.
- Repeated CV signals, individual role-tailored CV focus, High/Medium/Low free-text preferences, and optional campaign role/technology steering are combined into one weighted search profile.
- Added synonym/adjacency expansion and niche vocabulary, including embedded/microcontroller/firmware/RTOS, QEMU/emulation/virtual-device/virtio/KVM, reverse-engineering/binary/firmware/driver/protocol analysis, retro/legacy/BIOS/DOS, PIC/dsPIC, STM32/ESP32, legacy peripheral emulation, DOSBox-X, Buildroot/Yocto and related terms.
- Each query deliberately contains only a small number of specialist concepts. Query variants rotate across scheduled runs.
- Operating location is no longer placed in generated search queries.
- Location is evaluated after discovery: explicit configured-location/global/APAC wording can increase fit; explicit incompatible regional restrictions can decrease/reject according to Search Scope geography policy.
- Campaign role families and technologies are steering/boost inputs, not a required manual keyword list.
- Campaign Detail and Profile screens now expose the derived profile and current query-plan preview.
- Added `python manage.py preview_queries` for a no-search CLI preview.

## Result consolidation

- Raw hits from search providers/queries are canonicalized and consolidated before expensive enrichment.
- Exact URLs are merged; conservative cross-post merging requires an almost identical title plus substantial snippet similarity.
- Search snippets and provider/query provenance are retained.
- A cheap CV-fit pre-score determines which evidence caused a result to survive the fan-in stage.
- Opportunity Detail shows CV profile matches, raw-hit consolidation count and discovery provenance.

## Applied-role import

- Added dedicated `Status / Outcome` and `Notes` fields to imported records.
- Preferred line format: `Company | Role | URL | Email | Date | Channel | Status | Notes`.
- Added labelled-block parsing for TXT/DOCX paragraphs.
- Added header-aware DOCX/XLSX/CSV table parsing (`Status`, `Outcome`, `Notes`, `Comments`, `Details`, etc.).
- Confirmed notes are persisted on the canonical Application record and shown/searched/exported in Applied Roles and Prepared Applications.
- Added small backward-compatible schema updater for existing v0.1 databases.

## Compatibility

- Same Docker-first runtime as v0.1.0.
- Same external Ollama URL abstraction for macOS/Metal, Ubuntu/NVIDIA or CPU-only Ollama.
- Portal remains HTTP-only on host port 80 for this development release.
