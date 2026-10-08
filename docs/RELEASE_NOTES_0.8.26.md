# ScoutBox 0.8.26

This maintenance release consolidates ScoutBox's non-advertised company discovery into **Hidden Leads**, repairs the remaining multi-access search-provider UI regression, and makes application/outreach preparation less cluttered and more asynchronous.

## Search providers

Yandex, Baidu and Naver now render their full Access Type choices directly from the adapter capability set even if health/telemetry diagnostics fail. Public Access remains the default, but Yandex Search API key / Yandex IAM token, Baidu Qianfan Web Search API, and Naver legacy/API HUB choices remain selectable and reveal their credential fields.

## Hidden Leads

The former Market Studies surface is renamed Hidden Leads in active navigation, headings, activity labels and messages. Summaries avoid numbering, labels and company-name repetition, use up to three lines in the list, prioritize actual named offerings where supported, and provide one practical outreach angle without asserting a vacancy. Legacy domain-derived company names are humanized for display and newly discovered pages prefer a brand-like title segment.

Unread counts for Hidden Leads, Opportunities and Applications & Outreach are shown in the left navigation and top-right attention control. Opening a record and explicit read/unread actions update the count.

## Blacklist scope

Blacklist rows gain scope: All Discovery, Opportunities Only, or Hidden Leads Only. Documentation/community defaults remain global. Large employers are seeded as Hidden-Leads-only, allowing interesting advertised roles to remain discoverable while suppressing low-value cold-contact leads.

## Campaign generation

Profile campaign-template generation runs in a background job. The button displays generation progress and a completion message below it. Keywords are selected per role from Candidate Profile and active Resume evidence; cross-role repetition is penalized. Legacy shipped campaigns are removed while Resume-first Automatic Discovery remains.

## Applications & Outreach

Application details are split into Details and Email & Application tabs. Tailor with another model, Tailor Resume/PDF, and Application Questions are popup tools that queue work asynchronously and expose preview/apply/download results. Async saving always returns JSON, and the browser also handles unexpected non-JSON server responses without throwing a raw JSON.parse SyntaxError. Candidate Profile display name replaces `[Your Name]` in email bodies.

Prepare Outreach notifications link the words Applications & Outreach to the unified workspace. Import-history proposals are visually separated from the import step. Country flags/width, italic company presentation and Resume/Cover alignment are also cleaned up.

## Facebook, Dashboard and list polish

Facebook Pages to Watch uses a compact Add Page button beside search, an in-app Page ID/Title editor, linked titles, click-to-edit Page IDs and no per-row save button. Dashboard Recent Errors keeps error text white and links only the timestamp. Country columns are widened, campaign template names are vertically centered, Campaign Status omits the always-zero error count, and Email History opens full message text from the subject.

## Hidden Leads timeout behavior

The 0.8.25 timeout fix is retained. Dashboard no longer mutates a still-running Hidden Leads scan into a failed job at 75 minutes. Discovery itself is bounded to a rotating provider/query window with a 40-minute execution budget and partial-result preservation; the scheduler releases a genuinely stale queued/running scan after 50 minutes.
