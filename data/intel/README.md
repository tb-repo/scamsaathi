# Intelligence data

Seed data for the threat intelligence tools (docs/07 section 5). Rebuilt into SQLite by `scamsaathi.tools.intel_db.build_db`.

| File | Content | Provenance |
|---|---|---|
| `official_domains.csv` | Official domains of organisations commonly impersonated | Each `verified` row was checked by loading the site on `verified_on`. `legacy` = old domain that now redirects to the official one. `unverified` = not yet confirmed (the site could not be read); treated as official but must be verified before release (R-009) |
| `blocklist.csv` | Known-bad indicators | **Synthetic only.** Domains use reserved TLDs (`.example`, `.test`, RFC 2606) so they cannot belong to anyone. UPI IDs use the fictional `@demo` handle |
| `allowlist.csv` | Known-good indicators | Synthetic |
| `shorteners.txt` | URL shortener domains | Public knowledge |
| `suspicious_tlds.txt` | TLDs often abused in phishing | Heuristic list, weak signal |

## Important

- The synthetic phone numbers (`+91 90000 0000x`) are made up for demos, but any 10-digit number could belong to a real person. Never present them as real scammers; the UI must say "on the ScamSaathi demo blocklist".
- Banks in India moved to the RBI-mandated `.bank.in` domain (deadline 31 Oct 2025; registrar IDRBT). Government sites use `.gov.in` / `.nic.in` (registrar NIC). The URL analyzer treats these as restricted suffixes.
- Real-world indicators may only be added with a documented public source.
