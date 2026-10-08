# ScoutBox 0.10.108

## Fixed

- Focus taxonomies are now managed independently for Opportunities, Hidden Leads and Address Book.
- Campaign names are restored as weak naming inspiration when the record content supports the campaign topic, but campaign dominance cannot assign records.
- Generic Focus labels such as Application Engineer, Software Engineer, Engineer, Developer, Platform and Cloud Technology are rejected or refined.
- Balanced Focus repair avoids both oversized catch-all groups and singleton-heavy taxonomies.
- Upgrade repair rebalances current 0.10.107 Focus damage separately for each list namespace without calling network or AI services.

## Verification

- Python syntax/AST checks.
- Targeted 0.10.108 static regression checks.
- Compose YAML and shell syntax checks where tools are available.
