# ScoutBox 0.10.59

0.10.59 adds first-class Forum opportunity discovery on top of 0.10.58.

## Changes

- Adds a flat Configuration > Search Sources > Forums checklist for non-Reddit forum/community sources.
- Seeds forum sources with native-first search metadata, including Discourse JSON/search, phpBB-style search, forum feeds/APIs, and deterministic forum search pages before indexed fallback.
- Keeps existing Reddit and other 0.10.58 community adapters untouched to avoid duplicate source ownership.
- Adds Forum as a high-level source bucket for opportunities, leads, Address Book attribution, statistics, and source charts.
- Adds a Forum contact-method/channel with a discussion-style icon.
- Renames user-facing Apply Via filtering copy to Contact Method and adds a Forum checkbox in Opportunities, Hidden Leads, and Address Book filters.
- Preserves forum post timestamps as the primary age source for forum opportunities; generic thread activity/bumps do not reset age.
- Shortens the Engagement Preferences helper text.

## Upgrade note

Run database migrations after replacing the application files. Existing Reddit, GitHub, GitLab, Hacker News, Lobsters, DEV Community, Indie Hackers, Facebook, and customized source ownership are preserved.

Routine future releases increment the patch component unless a compatibility-breaking change requires a larger version step.
