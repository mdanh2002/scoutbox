# ScoutBox 0.8.98

## Changes since 0.8.97

- Opportunity list summaries are less sparse and more useful for scanning. They now extract one or two concrete role/JD signals and add a terse candidate-interest cue, for example `UEFI/BIOS + Secure Boot — firmware/security fit`, `QEMU/KVM — virtualization fit`, or `Embedded Linux + technical writing — technical-writing/domain fit`.
- Highlight generation no longer uses recommendation text or ordinary search-query snippets as evidence. Search snippets are only a last resort when the role title itself is already in a target technical domain, preventing unrelated results such as warehouse/front-of-house roles from inheriting campaign keywords like “reverse engineering”.
- Existing Opportunity highlights are repopulated on upgrade under the new JD-grounded rule.
- The daily digest again includes operational context rather than only the shortlist: rolling-24-hour opportunity/lead/contact/application counts, campaign runs, request totals, input/output token consumption, page/search operations, downloaded bytes, and errors.
- The digest includes current ScoutBox mode/settings, including Local AI Discovery versus Cloud Web Discovery, the active local/cloud AI route where available, background state, and scan interval.
- Today's cloud-budget consumption is always shown separately from rolling-24-hour usage, including requests, input tokens, output + reasoning tokens, page recovery, and automatic-run budget.
- Digest opportunity/lead rows retain the top-five ranking and now show a short readable source-backed description plus explicit `Email:`, `Company:`, `Contact:`, and `Source:` values. ScoutBox does not hide URLs behind hyperlink labels in the generated HTML digest.
- Opportunity Remote unknown state is now rendered as the same plain `?` marker used elsewhere, without a redundant `Unknown` caption below it.
- The 0.8.97 company-domain/domain-age corrections remain included: obvious LinkedIn/job-board/ATS domains are excluded and old false platform-derived ages are repaired/cleared for normal company-domain repopulation.

## Upgrade

Keep the existing `.env` and Docker volumes. Replace the application files with the 0.8.98 package, then run:

```bash
chmod -R +x *.sh
./restart_scout_box.sh
```

Do not run `initial_setup.sh` for an existing installation.

Version 0.8.98 adds one data migration (`0056`) that repopulates stored Opportunity list highlights. It does not remove applications, contacts, settings, or discovery history.
