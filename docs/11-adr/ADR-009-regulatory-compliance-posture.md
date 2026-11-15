# ADR-009: Regulatory compliance posture

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-12 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

The regulatory review (document 15) found four rules that shape the product:

- **Telecom number tagging:** TRAI's TCCCPR, through Regulation 34A as amended in Feb 2025 and Sep 2026, bars call-management apps from tagging, blocking or filtering calls from designated number series (140xx, 1600xx, 1601xx).
- **Data protection:** the DPDP Act, 2023 and the DPDP Rules, 2025 place consent and data-minimisation duties on apps that process personal data. These duties are heaviest for apps that read SMS, call logs or contacts.
- **Criminal law:** the relevant sections (IT Act 66C/66D, BNS 318/319, Telecommunications Act 42) are applied by police and courts. Telling a user which section applies would be legal advice.
- **Reporting channels:** official channels differ by situation. Spam goes to TRAI DND / 1909, suspected fraud to Chakshu, and money already lost to 1930 / NCRP.

It is unclear whether ScamSaathi counts as a "call management application". It does not handle calls, but it does label numbers as risky.

## Options

1. Treat ScamSaathi as out of scope of TCCCPR and label any number freely.
2. Take the conservative position on number labelling, and design to stay out of the device-scanning category.

## Decision

Option 2.

1. **Paste-only input (FR-080).** ScamSaathi never reads SMS inboxes, call logs, contacts or notifications. This is a hard constraint for the prototype and any successor without a fresh ADR.
2. **Designated series are never tagged (FR-081).** Numbers in 140xx, 1600xx or 1601xx cannot be added to the blocklist, and the output never calls them scam or spam numbers. The message content is still assessed. The output states that the series is reserved for regulated senders and advises verifying anyway.
3. **Sender-format signal (FR-082).** A claim to be a bank, regulated financial entity or government body from an ordinary mobile number or an international number counts as a risk signal.
4. **No legal advice (FR-083).** No law sections, charges or punishments appear in assessments. Complaint drafts list facts only.
5. **Notice before use (FR-084)** and **channel routing by situation (FR-085).**
6. **Addendum 2026-11-13 (Regulation 34A read in full).** Regulation 34A also protects government communications and covers "similar services". DLT sender headers, including government (-G) headers, are explained as information and never scored or labelled (FR-086). ScamSaathi offers no in-app spam reporting and keeps no spam reports; it points to 1909, the TRAI DND app, and Chakshu (FR-087, following the Third Amendment 2026).
7. **Addendum 2026-11-13 (Third Amendment 2026 Gazette text).** Regulation 34A(1) now covers call management apps or similar services "that offer users a mechanism to report UCC/spam", and 34A(2) bars spam-reporting features in diallers and third-party apps unless the reports go to the DLT platform. Because ScamSaathi has no reporting feature (FR-087), it is likely outside 34A(1). The conservative position (items 2 and 6) is kept regardless, since FR-087 could change in a later product. 140xx calls are never described as spam (opt-out regime), and 1601xx is described as the utilities, logistics and courier service series (doc 15 section 13).

## Consequences

- **Positive:** lower regulatory exposure, a clear story for evaluators, and stronger privacy.
- **Negative:** paste-only is less convenient than automatic SMS scanning, and a scammer who reaches a user from a designated series cannot be labelled by number (content analysis still applies).
- **Follow-up:** ~~read Regulation 34A in full (R-017), and implement FR-081/FR-082 together with the international-number fix.~~ Done (2026-11-12 and 2026-11-13), including the Third Amendment 2026 Gazette text. Open: show the appeal route once it starts (about 17 Dec 2026).

## Related

Document 15, document 08, ADR-007, R-017 to R-019.
