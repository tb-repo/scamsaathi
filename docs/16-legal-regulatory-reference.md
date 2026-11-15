# 16. Legal and Regulatory Reference (India)

| Field | Value |
|---|---|
| Version | 1.0 (Approved) |
| Date | 2026-11-13 |
| Related | ADR-009, document 08, FR-080 to FR-087, R-017 to R-019 |

> **Not legal advice.** This is the project author's research summary for designing a prototype. Punishment figures are taken from the sources listed and must be checked against the official Act text (India Code / Gazette) before they are quoted in the final report. ScamSaathi itself never tells a user which law applies to their case or what punishment an offender may face.

## 1. Why this matters for ScamSaathi

Mobile scams sit across three bodies of rules:

- **Criminal law:** what the scammer did.
- **Telecom regulation:** how the call or SMS reached the user.
- **Data protection:** how ScamSaathi itself handles the text a user pastes in.

The first two shape what the app *recommends*. The third shapes how the app is *built*.

## 2. Authorities and channels

| Authority | Role relevant to scams | What ScamSaathi uses | Verified |
|---|---|---|---|
| I4C, Ministry of Home Affairs | Coordinates cybercrime response; runs the National Cyber Crime Reporting Portal and the 1930 helpline | 1930 and cybercrime.gov.in for money lost. Links users to the portal's suspect search and suspect-reporting pages | Yes, portal pages and I4C FAQ (2026-11-11) |
| National Cyber Crime Reporting Portal | Complaints; **suspect repository** searchable by mobile number, email, bank account, social media ID, UPI ID; suspect reporting | Link only, no scraping. The portal states the database is built from public complaints, is not complete, and does not certify authenticity, so it is never shown as proof | Yes, portal pages (2026-11-12) |
| DoT, Sanchar Saathi | Chakshu (suspected fraud calls, SMS, WhatsApp, including international numbers); international spoofed-call prevention system | Chakshu for suspected fraud. Chakshu is **not** for money already lost | Yes, Sanchar Saathi pages (2026-11-11) |
| TRAI | TCCCPR: spam (unsolicited commercial communication), DND preferences, designated number series, rules for call-management apps | Number-series rules (section 4), header suffixes, 1909 and the TRAI DND app for spam (not fraud) | Yes. TCCCPR Second Amendment 2025 and Third Amendment 2026 read from the official texts (sections 12 and 13, 2026-11-13) |
| MeitY | IT Act, 2000; IT Rules; DPDP Act, 2023 and DPDP Rules, 2025 | Data-handling design (section 5) | DPDP dates from Parliament answers and law-firm summaries |
| RBI / NPCI | Banking and UPI customer-protection guidance; `.bank.in` domain mandate | KB content (doc 07), URL rules | Yes (Phase 2 and 3) |

The "I4C Acts and Rules Portal" named in the author's brief could not be located yet (Q-9).

## 3. Offences that commonly apply to mobile scams

For user education and the final report only. Section numbers come from official sources. Punishment ranges come from the secondary sources listed in section 8, unless marked otherwise.

| Law | Section | Covers | Punishment (as reported) | Typical scam link |
|---|---|---|---|---|
| IT Act, 2000 | 66C | Identity theft: fraudulent use of another person's password, e-signature or other unique identification | Up to 3 years and fine up to ₹1 lakh. **Verified** | OTP and credential theft (SC-03), account takeover |
| IT Act, 2000 | 66D | Cheating by personation using a communication device or computer resource | Up to 3 years and fine up to ₹1 lakh. **Verified** | Fake bank, police or officials (SC-01, SC-02, SC-12) |
| IT Act, 2000 | 43 / 66 | Unauthorised access or damage, malware (43 is civil compensation; 66 makes it an offence when done dishonestly or fraudulently) | 66: up to 3 years or fine up to ₹5 lakh, or both (section 66 text on incometaxindia.gov.in) | Remote-access and APK scams (SC-11) |
| BNS, 2023 | 318 | Cheating (replaces IPC 415/420). 318(4) covers cheating that dishonestly induces delivery of property | 318(2): up to 3 years, or fine, or both. 318(4): up to 7 years and fine. **Verified from the Act text** (section 10) | Most money-loss scams |
| BNS, 2023 | 319 | Cheating by personation (replaces IPC 416/419) | 319(2): up to 5 years, or fine, or both. **Verified** | Impersonation scams |
| Telecommunications Act, 2023 | 42(3)(e) | Obtaining SIMs or other telecom identifiers through fraud, cheating or personation | Up to 3 years, or fine up to ₹50 lakh, or both; all s.42 offences cognizable and non-bailable (s.42(7)). **Verified** | Mule SIMs used for scam calls |
| Telecommunications Act, 2023 | 42(3)(c) | Tampering with telecom identifiers (spoofing numbers, IMEI, SMS headers) | Same as above. **Verified** | Spoofed caller IDs |

Court records found during research show these sections being charged together in real cases (for example, BNS 318(4) and 319(2) with IT Act 66D and Telecom Act 42 in one FIR).

**Design rule (FR-083):** ScamSaathi does not name legal sections in a user's assessment, and does not predict charges or punishments. The police and courts decide which sections apply. The optional complaint draft lists facts only: what happened, when, identifiers, amounts and UTR numbers.

## 4. TRAI rules that change how ScamSaathi labels numbers

Findings, paraphrased from TRAI statements reported in the press and from TRAI consultation documents. Content was rephrased for compliance with licensing restrictions.

1. **1600-series numbers** are reserved for service and transaction calls from entities regulated by RBI, SEBI, IRDAI and PFRDA, and for government-to-citizen calls. Under TCCCPR, apps may not tag, block or filter these calls ([ET Telecom](https://economictimes.indiatimes.com/industry/telecom/telecom-news/trai-bars-apps-from-blocking-tagging-calls-from-1600-number-series/articleshow/132311517.cms)).
2. **140-series numbers** are for registered telemarketers. Apps may not tag or filter them. Users block them through the DND registry (same source).
3. **Regulation 34A** (added by the TCCCPR second amendment, 12 Feb 2025) regulates "call management applications or similar services". The third amendment, issued on 18 Sep 2026, kept the rule that such apps may not flag designated series (140xx, 1600xx, 1601xx) as spam. Users can still block numbers on their own phones ([TRAI PR 119/2026](https://www.trai.gov.in/sites/default/files/2026-09/PR_No119of2026.pdf); [NDTV Profit](https://www.ndtvprofit.com/business/no-data-sharing-no-spam-tagging-what-trais-new-rule-for-truecaller-other-apps-entails-12064008)).
4. **Spam vs fraud:** TRAI asks users to report spam through the TRAI DND app (or SMS/call 1909) so numbers can be traced and disconnected ([TRAI PR 137/2025](https://www.trai.gov.in/sites/default/files/2025-11/PR_No.137of2025.pdf)). TCCCPR amendments extended the complaint window to 7 days after receipt.

**Does this apply to ScamSaathi?** ScamSaathi is not a call-management app: it does not see, block or filter calls on a device. It does, however, label a number as risky in its output. **ADR-009** therefore takes the conservative position:

- Never place a designated-series number on the blocklist, and never label one as a scam or spam number.
- Assess the *message content* on its own merits, and say that the number series is reserved for regulated senders. A designated series is a sign of genuineness, not proof, so the user should still verify.
- A caller claiming to be a bank or government body from an ordinary 10-digit mobile number or a foreign number is a warning sign. Their service calls are meant to come from the 1600 series.

Regulation 34A has now been read in the official text (section 12.2). It covers "Call Management Application or similar services" and also protects government communications. ADR-009's position above already complies and is kept; R-017 is closed.

## 5. Data protection: DPDP Act, 2023 and DPDP Rules, 2025

| Item | Status found | Source type |
|---|---|---|
| DPDP Rules notified | 13 Nov 2025 (Gazette 14 Nov 2025) | Law-firm and DSCI summaries; Lok Sabha answer |
| Phasing | Board provisions immediate; consent-manager provisions from 13 Nov 2026; most data-fiduciary obligations after an 18-month transition (13 May 2027) | Lok Sabha answer (18-month transition); law-firm summaries for exact dates |
| Penalties | Schedule to the Act; highest band up to ₹250 crore for failing to take reasonable security safeguards (section 8(5)); up to ₹200 crore for failing to notify a breach | Multiple secondary sources; check against the Act's Schedule |
| Criminal liability | None under DPDP (civil penalties only) | Secondary |

**How ScamSaathi's design maps to DPDP** (prototype, synthetic data only, A-3):

| DPDP expectation | ScamSaathi design | Status |
|---|---|---|
| Lawful purpose, notice, consent | Single purpose: assess the pasted text. Notice shown before the first analysis (FR-084) | Notice to build in Phase 6 |
| Data minimisation | **Paste-only input.** The app never reads SMS inboxes, call logs, contacts or notifications (FR-080). No account, no device identifiers | By design |
| Storage limitation | Raw text never stored. Masked checkpoints expire after 24 h. Logs roll over after 7 days | Built (ADR-007) |
| Security safeguards | PII masking before any external call or log write; gateway refuses unmasked prompts; secrets in `.env` | Built; international numbers gap open (see doc 13) |
| Erasure / withdrawal | "Clear my session" deletes the checkpoint (doc 08) | Phase 5/6 |
| Third-party data | Pasted text contains other people's data (scammer numbers, sometimes names). Masked before leaving the process; used only for local lookups | Built |
| Processor abroad | Masked text goes to Google Gemini. DPDP section 16 allows transfers unless a country is restricted by notification. Not yet checked for current notifications (Q-10) | Open |
| Children | No age gate in the prototype. A public release would need verifiable parental consent under the Rules | Out of scope (prototype) |

The author's brief notes that apps scanning SMS, call logs or contacts face strict consent duties. ScamSaathi avoids that category entirely by being paste-only. This is recorded as a hard constraint in ADR-009.

## 6. Other rules noted but not yet researched

| Item | Why it may matter | Status |
|---|---|---|
| IT (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021 | Apply to intermediaries hosting third-party content. ScamSaathi hosts none; likely not applicable | To confirm (Q-11) |
| CERT-In directions (2022) on incident reporting | May apply to service providers if the app is deployed publicly | To confirm for any public deployment |

## 7. Changes made or proposed because of this review

| ID | Change | Where |
|---|---|---|
| FR-080 | Paste-only input; never read device SMS, call logs, contacts or notifications | doc 03, ADR-009 |
| FR-081 | Never blocklist or label designated-series numbers (140xx, 1600xx, 1601xx) as scam or spam | doc 03, ADR-009, intel tools (to implement) |
| FR-082 | Treat bank or government claims from non-designated numbers (ordinary mobile or international) as a risk signal | doc 03, intel tools (to implement with the international-number fix) |
| FR-083 | No legal sections, charges or punishments in user assessments; complaint draft lists facts only | doc 03, A8 advisory |
| FR-084 | Show a data-use notice before the first analysis (what is processed, what is sent to the AI provider, what is kept) | doc 03, Phase 6 UI |
| FR-085 | Route spam (unsolicited marketing) to TRAI DND / 1909, suspected fraud to Chakshu, and money lost to 1930 / NCRP | doc 03, advice and contacts. **Done** (1909 verified 2026-11-13, section 12) |
| FR-086 | Recognise DLT sender headers and explain the -P/-S/-T/-G suffix as information only; never score, tag, or label a header (government headers are protected by Regulation 34A) | entities and intel tools. **Done** |
| FR-087 | No in-app "report as spam" store. ScamSaathi never collects spam reports itself; it only points users to official channels (1909, TRAI DND app, Chakshu) | doc 03, ADR-009, Phase 6 UI |

## 8. Sources consulted (2026-11-12)

Primary (government or regulator):
- I4C FAQ: https://i4c.mha.gov.in/FAQ.aspx
- National Cyber Crime Reporting Portal, suspect repository and reporting: https://cybercrime.gov.in (portal reporting and suspect search repository)
- Sanchar Saathi, Chakshu: https://sancharsaathi.gov.in/sfc
- TRAI press releases: https://www.trai.gov.in/sites/default/files/2025-11/PR_No.137of2025.pdf, https://www.trai.gov.in/sites/default/files/2026-09/PR_No119of2026.pdf
- TCCCPR (Second Amendment) Regulations, 2025: http://www.trai.gov.in/sites/default/files/2025-02/Regulation_12022025_0.pdf (located, not yet read in full)
- Lok Sabha answers on the Telecommunications Act s.42 and DPDP: https://sansad.in/getFile/loksabhaquestions/annex/186/AU2966_8ME8jt.pdf, https://sansad.in/getFile/loksabhaquestions/annex/186/AU2776_3nlniT.pdf
- IT Act section 66 text: https://www.incometaxindia.gov.in/w/section-66-112
- BNS full text (NCRB): https://www.ncrb.mha.gov.in/uploads/SankalanPortal/DownloadPDF/BNS2023.pdf (located, PDF not readable by the research tool; read manually before quoting)

Secondary (press and law-firm summaries of official statements):
- ET Telecom on 1600/140 series: https://economictimes.indiatimes.com/industry/telecom/telecom-news/trai-bars-apps-from-blocking-tagging-calls-from-1600-number-series/articleshow/132311517.cms
- NDTV Profit on the third amendment: https://www.ndtvprofit.com/business/no-data-sharing-no-spam-tagging-what-trais-new-rule-for-truecaller-other-apps-entails-12064008
- ETGovernment on Telecom Act s.42(3) penalties: https://government.economictimes.indiatimes.com/news/governance/dot-warns-miscreants-against-tampering-or-spoofing-of-mobile-numbers-ip-address-imei-sms-headers/118726068
- JSA and Legal500 on DPDP Rules timelines and penalties
- Penalty figures for IT Act 66C/66D and BNS 318/319 come from legal-education sites; confirm from the Acts before quoting

## 9. Before the final report

1. ~~Read the BNS, IT Act and DPDP Act texts and correct any figure in section 3 or 5.~~ Done 2026-11-12 from the official PDFs in the repo (section 10).
2. ~~Read TCCCPR Regulation 34A as amended and record whether it covers apps like ScamSaathi.~~ Done 2026-11-13 (section 12.2). ~~Still to do: read the Third Amendment 2026 Gazette text.~~ Done 2026-11-13 (section 13).
3. Locate the I4C Acts and Rules portal (Q-9). `docs/IndianOfficialWebSites/Websites.md` was empty when reviewed.

## 10. Review of the official Act texts (2026-11-12)

The author added 18 official PDFs in `docs/IndianOfficialDocs/`. Text was extracted with `scripts/extract_legal_texts.py` (pypdf 7.0.1) into `.cache/legal/` (git-ignored) and searched with `scripts/find_in_acts.py`. All 18 files produced readable text. Page numbers below are PDF pages.

### 10.1 Provisions verified and how the app uses them

| Act | Provision (verified wording, paraphrased) | Punishment or effect | How ScamSaathi uses it |
|---|---|---|---|
| BNS 2023 | s.204 Personating a public servant (p.70) | 6 months to 3 years and fine | Digital-arrest typology (SC-01) citation |
| BNS 2023 | s.308 Extortion; illustration (e) is a threat sent by electronic message (p.90) | Up to 7 years, or fine, or both | Sextortion (SC-14), loan-app harassment (SC-06) |
| BNS 2023 | s.111 Organised crime expressly includes cyber-crimes and "mass-marketing fraud" (p.48) | Organised-crime penalties | Task fraud and mule networks (SC-05, SC-09, SC-15) |
| BNS 2023 | s.336(3) Forgery of a document or electronic record for cheating (p.103) | Up to 7 years and fine | Fake warrants and notices in digital-arrest scams |
| BNS 2023 | s.351 Criminal intimidation; (4) anonymous communication (p.106) | 351(2): up to 2 years | Threat signals |
| BNS 2023 | s.318(2), (4); s.319(2) (pp.95-96) | See section 3 | Section 3 corrected |
| IT Act 2000 | s.66C, 66D, 66E (privacy: capturing or sending images of private areas) (p.24) | 66E: up to 3 years or fine up to ₹2 lakh | SC-14 citation |
| Telecommunications Act 2023 | s.42(2) personation to access networks; s.42(3)(c), (e); s.42(7) cognizable and non-bailable (pp.17-18) | 42(3): up to 3 years or ₹50 lakh | SIM mule typology (SC-15) |
| Online Gaming Act 2025 | s.2(1)(g) "online money game" covers skill, chance or both when money is staked; s.5 offering, s.6 advertising, s.7 banks facilitating payments are prohibited; s.9 penalties (pp.3, 5, 6) | Offering: up to 3 years or ₹1 crore; advertising: up to 2 years or ₹50 lakh; payments: up to 3 years or ₹1 crore | **New typology SC-13** and `money_game` signal. No offence for players was found in the sections read, so the app does not say playing is illegal |
| POCSO 2012 | s.11(v) threatening to use a real or fabricated depiction of a child; s.12 up to 3 years; s.19 anyone with knowledge must report to the police or Special Juvenile Police Unit; s.21 failure to report up to 6 months (pp.8-11) | | **Child-safety path**: any text with a minor and sexual content is routed to police reporting and "do not forward the images" advice, and scored CRITICAL |
| BNSS 2023 | s.173(1) information on a cognizable offence may be given at a police station "irrespective of the area where the offence is committed", orally or by electronic communication, to be signed within three days; s.173(2) free copy to the informant (p.67) | | `police_reporting` advice: any police station, electronic report, free copy |
| BSA 2023 | s.61 electronic records are admissible; s.63 conditions for computer output (p.29-30) | | `evidence` advice: keep chats, screenshots with number, date and time, the device, and the UTR |
| IT Rules 2021 | r.3(1)(b)(vii) impersonation is prohibited content; r.3(2)(a) the grievance officer acknowledges within 24 hours and disposes within 15 days; r.3(2)(b) intimate or morphed-image complaints must be acted on within 24 hours (p.3, 5) | | SC-14 advice: report to the platform |
| IT Rules Amendment 2026 | G.S.R. 120(E), in force 20 Feb 2026: defines "synthetically generated information" (deepfakes) and brings it within unlawful-information rules; intermediaries must tell users about mandatory reporting under BNSS and POCSO (pp.8-10) | | SC-14 covers AI-generated or morphed images |
| DPDP Act 2023 | s.8(5) security safeguards, 8(6) breach intimation, 8(7) erasure; s.16 transfer abroad restricted only to notified countries; s.17(1)(c) exemption for prevention or detection of offences; Schedule penalties up to ₹250 crore (8(5)) and ₹200 crore (8(6), s.9) (pp.11, 14, 24) | | Section 5 confirmed. The s.17 exemption is **not** relied on: the app keeps its consent-light, minimal-data design |
| PMLA 2002 | Schedule Part A paragraph 22 lists only IT Act offences (s.72, s.75 in the repo copy; the Jan Vishwas Act 2023 substitutes it with s.75 only) | | Background only; no app logic |
| Jan Vishwas Act 2023 | Decriminalises minor provisions across many Acts. In the extracted text, no change to IT Act s.66C/66D was found; the two-column layout makes this check **not conclusive** | | Doc note only |

Not used in app logic: Bankers' Books Evidence Act 1891, Companies Act 2013, Indian Telegraph Act 1885, RBI Act 1934 (s.45-IA registration of lenders and s.45S deposit restrictions noted as possible future checks for fake lenders), TRAI Act 1997.

### 10.2 Changes made to the app

| Area | Change |
|---|---|
| Knowledge base | 3 new typologies: SC-13 online money gaming and betting, SC-14 sextortion and morphed-image blackmail, SC-15 money mule and account or SIM renting. All 15 typologies now carry internal `legal_refs` (for example `LAW_BNS s.318(4)`), validated to point at an Act in the repo, and **never shown to users** (FR-083) |
| Sources | 11 Act documents registered as primary sources (`check: document_read`) |
| Signals | `sextortion_threat`, `money_mule_request`, `money_game` (English and Hinglish), new combos, scoring config v2 |
| Child safety | Minor plus sexual-content screen; CRITICAL floor; child-safety advice and contacts (112, NCRP) replace normal advice |
| Advice | Evidence checklist (BSA), police-reporting steps (BNSS), typology advice for SC-13 to SC-15 |
| Telecom numbers | International numbers masked and flagged; TRAI-designated series left visible, never blocklisted (build fails if one is added), and reported as an information finding; authority claims from international or ordinary mobile numbers flagged (FR-081, FR-082) |
| Tests | `tests/unit/test_legal_review_features.py` (UT-REG-01 to 05 and more), including a check that no user-facing advice names a section |

Content was paraphrased from the official texts; no long passages were copied.

## 11. Review of the official websites (`docs/IndianOfficialWebSites/Websites.md`, 2026-11-12)

| Site | What was found (page loaded unless noted) | Change in ScamSaathi |
|---|---|---|
| sancharsaathi.gov.in/sfc/ (Chakshu) | Two options: **Report Suspected Fraud** and **Report Spam (UCC)**, both "report within 30 days for action". Fraud examples listed include bank, wallet, SIM, gas, electricity, and KYC updates, impersonation of government officials, and **sextortion**. Money already lost goes to 1930 or cybercrime.gov.in | `chakshu_spam` contact closes FR-085 for spam (routed when a 140-series number appears). The 30-day window is added to suspected-fraud advice |
| sancharsaathi.gov.in/InternationalCall/ReportIntCall.jsp | **Report International Call**, for calls from abroad that display an Indian +91 number. The form takes the displayed number, the country, and a date up to 30 days old | `report_intl_call` contact and advice line for digital-arrest cases (SC-01) |
| sancharsaathi.gov.in (home) and Help page | Citizen services: **Know Mobile Connections in Your Name** (see and disconnect SIMs issued against your ID), block a lost or stolen handset, Chakshu | `sanchar_connections` contact and advice line for money-mule and SIM cases (SC-15) |
| i4c.mha.gov.in | Home page: safe-practice tips and news; FAQ already used (1930, NCRP, IT Act s.66 explanation). No separate "Acts and Rules" page found | None; Q-9 remains open |
| trai.gov.in | Home page: news, consultations (an open consultation on responsible AI use in telecom networks, comments due 27 Nov 2026). TCCCPR text not on the home page | None; R-017 remains open |
| meity.gov.in | Home page not machine-readable. MeitY's notifications page (via search) directs readers to India Code (indiacode.nic.in) for the IT Act and its Rules | India Code recorded as the canonical source for re-verification |

FR-085 status: spam routing now uses the official Chakshu "Report Spam (UCC)" option. The TRAI DND app and 1909 remain unverified from a primary source, so they are not shown to users. *(Superseded on 2026-11-13: both verified, see section 12.)*

## 12. Review of the TRAI sources (2026-11-13)

The author added three TRAI documents to `docs/IndianOfficialDocs/` and a TRAI page to `Websites.md`. All three PDFs produced readable text.

| Source | What it is |
|---|---|
| `Regulation_12022025.pdf` | Telecom Commercial Communications Customer Preference (Second Amendment) Regulations, 2025 (1 of 2025), TRAI notification of 12 Feb 2025, with its Explanatory Memorandum. 25 pages, read in full for the items below |
| `Press Release Page _ Press Information Bureau.pdf` | PIB release 2311989 (18 Sep 2026): salient features of the TCCCPR (Third Amendment) Regulations, 2026 |
| `PR_No.88of2024.pdf` | TRAI press release 88/2024 (20 Nov 2024): measures against spam calls and SMS |
| trai.gov.in/node/18099 | TRAI "SPAM" page. Only the page title and address loaded (the content is rendered by script), so nothing was used from it |

### 12.1 Verified facts (paraphrased; page numbers are PDF pages)

| Topic | Fact | Source |
|---|---|---|
| Deceptive messages | A message or call made "in the guise of commercial communication or otherwise" to deceive the recipient is treated as UCC, as far as misuse of telecom resources goes (amended reg. 2(bw), p.3) | 2025 amendment |
| Unregistered senders | Commercial communication from a sender not registered with an operator is UCC; operators must allow commercial traffic only from registered headers or the special number series (reg. 3, p.3) | 2025 amendment |
| Message types | Transactional messages (for example bank OTPs) are sent within 30 minutes of a customer-initiated transaction; promotional content mixed into any other type makes the whole message promotional; promotional messages must carry an opt-out (reg. 2(au), 2(bt), p.2) | 2025 amendment |
| Header suffixes | The message type can be identified from the header by the suffix -P, -S, -T, or -G (promotional, service, transactional, government) (p.13) | 2025 amendment |
| Consent short code | Consent-seeking messages come from the 127xxx short code (p.14) | 2025 amendment |
| Complaint window | A UCC complaint must be made within **7 days** of receipt. It is valid if it has the sender's number, the complainant's number, the date, and a brief description (amended reg. 23, p.5) | 2025 amendment |
| Unregistered senders, no DND needed | Complaints against unregistered senders do not require the complainant to have registered DND preferences (p.5) | 2025 amendment |
| 1909 | Preferences are registered by calling or sending an SMS to 1909, or by USSD (*1909*0# fully block, *1909*50# block promotional, *1909*1# to *1909*8# by category) (pp.15-16). Complaints by SMS or call to 1909 and by mobile app (p.21). *FULLY BLOCK was removed in 2026; see section 13* | 2025 amendment |
| Complaint modes | TRAI DND app, the operator's app or portal, and call or SMS to 1909 | PIB 2311989 |
| Appeal | Consumers can appeal the resolution of a UCC complaint within 15 days | PIB 2311989 |
| Operator apps | Operators' apps must show complaint options on the home screen, may auto-capture call and SMS details with permission, and must accept screenshots (p.16) | 2025 amendment |
| Header misuse | Misused headers or templates are suspended within six hours; a telemarketer responsible loses all telecom resources for one year and is blacklisted | PIB 2311989 |
| A2P calls | Robo-calls, auto-dialled, and pre-recorded or AI-voice calls must be pre-declared; undeclared ones are UCC | PIB 2311989; reg. 4 (2025) |
| AI/ML detection | Operators share AI-detected suspected UCC numbers; 3 complaints in 10 days plus an AI flag triggers action | PIB 2311989 |
| Traceability | Message chains from sender to recipient must be traceable (Direction of 20 Aug 2024; deadline extended to 30 Nov 2024) | TRAI PR 88/2024 |

### 12.2 Regulation 34A (closes R-017)

Inserted by the 2025 amendment (p.13). In paraphrase:

1. No call management application **"or similar services"** may tag, block, filter, or restrict calls or messages from the designated commercial number series, **or communications sent by the Government**.
2. An app that allows blanket blocking of those series, or tags them as spam, is non-compliant. Consumers keep the right to manage their own preferences.

The Third Amendment 2026 (PIB summary) restates this for 140xx, 1600xx and 1601xx, and adds that no call management app may offer users a spam or junk reporting option unless the report is sent to the operators' DLT platform.

**Assessment for ScamSaathi.** ScamSaathi does not intercept, block, or filter calls or messages on a device, so it is not a call management app in the ordinary sense. "Similar services" is not defined, so the conservative reading in ADR-009 is kept and extended:

- Designated-series numbers are never blocklisted, tagged, or labelled (FR-081, already built).
- Government (-G) and other DLT headers are explained as information and never scored or labelled (FR-086, built). The **content** is still assessed: the 2026 amendment itself acknowledges header misuse, and a user who pastes a message is choosing to have it checked, which fits the consumer's retained right to manage their own communications.
- ScamSaathi will not offer its own "report spam" button or keep spam reports (FR-087). It points users to 1909, the TRAI DND app, and Chakshu instead.

This is the author's reading for a prototype, not legal advice.

### 12.3 Changes made to the app

| Area | Change |
|---|---|
| Contacts | `ucc_1909` added (verified 2026-11-13; source PIB 2311989 and the 2025 regulation). Spam routing now shows 1909 and Chakshu spam |
| Advice | Spam advice rewritten: register DND preferences via 1909 or the operator's app; complain via 1909 or the TRAI DND app within 7 days with the sender's number, date, and a short description; Chakshu within 30 days |
| Entities | New entity kind `sender_header` for DLT headers with a type suffix (for example `AX-HDFCBK-S`). Upper case only; headers stay visible (organisation names, not PII) |
| Intel | `sender_header` information finding explains the suffix; designated-series wording now names 1600xx/1601xx and 1909 |
| Tests | Spam routing, 7-day window, header types, look-alike strings, government header with scam content still HIGH or above, 1601 wording |

Not used in app logic: the TRAI Act 1997 (already in the repo, background only), A2P and AI/ML detection rules (operator obligations), and the 127xxx consent short code (noted for a possible future information finding).

### 12.4 IndiaLaw summary of the Third Amendment 2026 (2026-11-13)

Source: https://www.indialaw.in/blog/food/trai-anti-spam-rules/ (law-firm blog, **secondary**; no author or date shown). It says the Third Amendment has been published in the Gazette. Most points match PIB 2311989: A2P declaration, no blanket tagging of government and regulated series, AI/ML detection, header suspension within six hours, 5 paise per minute A2P fee, appeals.

Points not in the PIB release:

| Claim | Effect on ScamSaathi |
|---|---|
| **Phased start**, counted from Gazette publication: general and DND provisions after 30 days; A2P declarations, VNO interfaces, and header suspension after 60 days; **appellate mechanism** and multi-operator AI matching after 90 days | If publication was around 18 Sep 2026, the appeal route would start around mid-December 2026. The 15-day appeal is therefore **not shown to users** until its start date is confirmed from the Gazette (note added to `ucc_1909`) |
| Users on "Fully Blocked" are moved to the new BLOCK PROMO category structure | Advice already says "register your preference via 1909", which stays correct. No USSD codes are shown, so nothing to change |
| TRAI consent covers calls and SMS only and is separate from DPDP consent | Doc note only. ScamSaathi's data-use notice (FR-084) is about DPDP, not TRAI consent |
| Filtering apps must share spam data with operators | Consistent with FR-087 (ScamSaathi collects no spam reports) |
| Staged sender penalties (KYC re-verification, then physical KYC and 15-day suspension, then disconnection, IMEI block, one-year blacklist); AI findings shared within two hours | Operator obligations; no app logic. Differs in detail from the PIB wording (3 complaints plus an AI flag in 10 days), so neither is quoted to users |

None of these claims is used for user-facing facts until the Gazette text is read (section 9, item 2). *(Checked against the Gazette text on 2026-11-13, section 13.5: the summary is accurate on all points above.)*

## 13. TCCCPR (Third Amendment) Regulations, 2026: official text (2026-11-13)

Source: `docs/IndianOfficialDocs/Regulation_18092026.pdf`, TRAI notification No. RG-25/(25)/2023-QoS dated 18 Sep 2026, regulations 05 of 2026, with the Explanatory Memorandum (EM). It is a signed scan with a text layer; the extracted text has OCR errors, so wording below is paraphrased from a careful reading, with PDF page numbers.

### 13.1 Commencement (reg. 1(3) and Annexure, pp.1, 17-18)

Numbers below are regulations of the 2018 principal regulations; the amending regulation is shown in brackets where the Act lists it.

| Phase | What starts | Date if Gazette publication was 18 Sep 2026 |
|---|---|---|
| 30 days | Everything not listed below: new definitions, reg. 21A (AI flagging), reg. 22(1)(i) agreement conditions, reg. 25 (complaints, except the 90-day parts), new reg. 25A, **reg. 34A**, Schedule II (1909 categories) | About 18 Oct 2026, **in force now** |
| 60 days | Reg. 4 A2P declaration (amending reg. 4); reg. 13 VNO interface (amending reg. 6); reg. 22(1)(a) header and template misuse (amending reg. 8(a)); new reg. 35A A2P termination charge (amending reg. 18) | About 17 Nov 2026 |
| 90 days | **Appeal**, new reg. 23(1)(c) (amending reg. 9(a)); corroboration of complaints with AI-flagged senders, reg. 25 main clause and the proviso to 25(4)(d)(ii) (amending reg. 11) | About 17 Dec 2026 |

The exact Gazette publication date is not printed on the copy (it says "to be published"), so these dates are estimates.

### 13.2 Provisions that affect ScamSaathi

| Provision | What it says (paraphrased) | Effect on ScamSaathi |
|---|---|---|
| **Reg. 34A(1), substituted (p.12)** | No call management application or similar service **that offers users a mechanism to report UCC/spam** may tag, block or filter calls from series designated for commercial **and government** communications, treat them differently from genuine communication, or allow blanket spam tagging. Consumers may still block or filter on their own devices, as long as this does not affect other users | ScamSaathi offers no spam-reporting mechanism (FR-087), so on the new wording it is likely outside 34A(1). ADR-009's conservative position (FR-081, FR-086) is kept anyway |
| **Reg. 34A(2), new (p.12)** | No call management app, **including phone diallers and third-party apps**, may offer users a way to report UCC under any name (spam, junk, etc.) unless the report is sent to the operators' DLT platform | Confirms FR-087 from the primary text |
| Reg. 34A(3) | TRAI may act against non-compliant apps after giving them a chance to respond | Background |
| Reg. 21A(1) proviso (p.3) | Operators' AI systems must not flag 140xx, 1600xx or 1601xx numbers as "Suspected UCC/spam" to recipients. AI-flagged CLIs are shared within two hours | Same principle as FR-081 |
| EM on 34A (p.50) | Calls from 140xx **cannot be termed spam**: the system is opt-out, so the customer is treated as agreeing until they register a DND preference. 1600xx is allotted strictly to regulated entities. **1601xx** is being rolled out by a Direction of 10 Aug 2026, first for **utilities, logistics and courier** services. TRAI has seen trusted institutions, including TRAI, falsely attached to numbers through crowd-sourced tagging, which can enable fraud | **Two corrections** (section 13.3). Supports the curated, non-crowd-sourced blocklist design |
| Reg. 23(1)(c), new (p.6) | Appeal to the Appellate Authority within 15 days of the resolution, or, if there is no resolution within 15 days of complaining, within the next 15 days; through any UCC complaint mode | 90-day item; **not shown to users yet** |
| Reg. 25(2), (3) (p.7) | A complaint without the sender's complete telephone number or header is closed. Complaints after 7 days are recorded as reports, not complaints | Advice now says "sender's number or SMS header" |
| Schedule II (pp.13-15) | **FULLY BLOCK is removed**; existing FULLY BLOCK preferences move to BLOCK PROMO within 15 days. Opt out of all promotional categories with 50 / BLOCK PROMO / *1909*50#, or by category 1 to 8. Opt back in with 90 to 98 (*#1909*90# and so on). BLOCK PROMO never blocks transactional, service or government messages | Advice never quoted USSD codes, so no change. Doc 16 section 12.1 marked |
| Reg. 2(k) and EM (pp.1, 18-20) | TCCCPR "consent" only covers permission for calls and SMS. It is separate from DPDP consent, and nothing in TCCCPR exempts a sender from DPDP | Doc note; FR-084 notice is about DPDP |
| Reg. 2(bh), 2(bt) (pp.2-3) | OTPs for app login, password reset and two-factor authentication are now **service** messages; "apps login" was removed from transactional | Header suffix explanation unchanged (it describes the suffix, not the content) |
| Reg. 21A(5), 25(5)-(6) (pp.4, 9) | Staged action against senders: KYC re-verification, then physical KYC with a 15-day bar on outgoing services, then one-year disconnection, blacklisting and device blocking. Action is triggered by 5 or more AI-flagged CLIs in 10 days, or 3 or more complaints plus an AI flag (or 5 or more complaints) in 10 days | Operator duties; no app logic |
| Reg. 4, 35A (pp.3, 12) | A2P calls must be declared in advance, otherwise they are UCC. Termination charge up to 5 paise per minute; designated series exempt | Operator duties |

### 13.3 Changes made to the app

| Area | Before | After |
|---|---|---|
| 1601 finding | Grouped with 1600 as "RBI/SEBI/IRDAI/PFRDA-regulated entities and government" | Separate text: rolled out for service and transaction calls, first from utilities, logistics and courier companies |
| 140 finding | "used by registered telemarketers" | "promotional calls ... allowed unless you register a DND preference" (never says spam) |
| Spam advice | "To complain about a spam call or SMS ..." | Opt-out first. Complain only if calls continue after opting out, or a commercial call or SMS comes from an ordinary number. Give the sender's number **or SMS header** |
| `ucc_1909` note | Appeal start unconfirmed | Appeal rule and 90-day start recorded; still hidden from users |
| Tests | | 1601 wording, 140 never called spam, conditional complaint advice |

### 13.4 Open items

- Confirm the Gazette publication date, then show the appeal route from its start date (about 17 Dec 2026).
- 1601xx is phased. Later phases may add sectors; re-check before the final report.

### 13.5 IndiaLaw summary checked against the Gazette

All claims in section 12.4 match the official text: the 30/60/90-day phasing, FULLY BLOCK migrating to BLOCK PROMO, TCCCPR consent being separate from DPDP, AI flags shared within two hours, the staged penalties, header suspension within six hours, and the 5 paise A2P charge. One difference: the summary says filtering apps "must share their spam data". The text actually prohibits offering spam reporting unless the reports go to the DLT platform (34A(2)).
