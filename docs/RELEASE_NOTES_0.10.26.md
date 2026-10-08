# ScoutBox 0.10.26

## Fixed

- Address Book promotion now accepts a public employer mailbox on third-party job/community hosts only when retained page evidence independently names the organization that owns the email domain.
- Host labels such as GitHub, Findjob24h and short academic-board labels are no longer allowed to block a strongly evidenced real employer such as Pillpresso, InfoDrive Solutions or Rebellions.
- Known job/community hosts never fall back to the host itself as the employer when ScoutBox cannot recover an actual hiring company.
- Korean academic domains such as `snu.ac.kr` use the correct registrable-domain boundary for ownership checks.
- Existing Opportunities and Hidden Leads with clearly recoverable host-as-company labels are repaired during upgrade. Ambiguous records are left unchanged.
- Existing structured contact emails that previously failed Address Book promotion are retried when no active Address Book row exists.
- Accommodation, accessibility, privacy, legal, helpdesk and other non-contact mailbox protections remain strict, including the TAOps/Vertiv safeguards.
- Address Book promotion outcomes are recorded in the Audit Trail and summarized in diagnostic exports (`created`, `updated`, `no_email`, `non_contact_context`, `generic_or_invalid`, `ownership_mismatch`, `recycled`).

## Upgrade

Includes one data-repair migration (`0082_v01026_third_party_employer_repair`). It changes retained company labels only when strong evidence is available; there is no schema change.

Routine future releases increment the patch component.
