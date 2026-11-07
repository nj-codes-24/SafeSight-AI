# 10 — Privacy, security, standards and compliance

Research date: 5 November 2026. **This is an engineering analysis, not legal advice.** Items marked ⚖ require review by qualified counsel in the relevant jurisdiction before any commercial deployment. Source IDs (L…, S…) resolve in `14_SOURCE_REGISTER.md`.

## 1. Non-negotiable safety principle

SafeSight is an **additional, observational safety layer**. It must never be represented as, sold as, or configured as:

- a replacement for certified safety interlocks, guards, light curtains, safety scanners or emergency stops;
- a replacement for competent safety officers, attendants, banksmen or mandatory procedures (permits, LOTO, gas testing);
- proof that an environment is safe. **Absence of an alert is not evidence of safety.**

**Product controls that enforce this (requirements in `11`):** every UI view and report carries a limitation statement; the system has no output wired to machine safety circuits; marketing claims are restricted to validated, per-camera, per-hazard figures (`09`); the policy engine records whether the active policy is approved.

## 2. Standards: what applies, and how

| Framework | Current status (verified where noted) | Relevance to SafeSight | What SafeSight may claim |
|---|---|---|---|
| **ISO 45001** (OH&S management systems) | 2018 edition current; revision at DIS stage (ballot mid-2026), publication expected 2027 [L05] | Supports hazard identification (6.1.2) and monitoring/measurement (9.1) as an *input* | "Provides monitoring data that can support an ISO 45001 system." Not certifiable itself |
| **ISO 12100** (machinery risk assessment) | 2010 edition [L20] | Method for machine builders; useful vocabulary for severity/exposure | Nothing; SafeSight is not machinery design |
| **ISO 13849-1 / IEC 62061** (functional safety of control systems) | Current editions [L21] | Define safety functions with performance levels/SIL | SafeSight is **not** a safety-related part of a control system; claim none |
| **IEC 61496-4-x / IEC TS 62998-1** (vision-based protective devices, safety-related sensors) | IEC TS 61496-4-2 and 4-3, 2022 editions [L10] | The route a camera-based device must follow to *protect persons* | Explicitly not a protective device |
| **ISO 10218-1/-2:2025** (industrial robots and robot cells) | Part 2 published Feb 2025; integrates collaborative content from ISO/TS 15066 [L11] | Robot cell safeguarding | Observes cell entry; never safeguards |
| **ISO 3691-4** (driverless industrial trucks) | 2023 | Safety of AGVs/AMRs | Not applicable to observation |
| **EU Machinery Regulation (EU) 2023/1230** | Applies from **20 January 2027**; safety components with self-evolving ML behaviour need notified-body assessment [L04] | Would apply if SafeSight were placed on the market as a *safety component* | Design and contracts must keep SafeSight outside that definition ⚖ |
| **OSHA** (US) | Standards are performance requirements on employers; OSHA does not certify products | Supports compliance programmes for 1910.178 (trucks), 1910.37 (exit routes), 1910.147 (LOTO), 1910.212 (guarding), 1926.501 (falls) | "Helps identify conditions related to…"; never "ensures OSHA compliance" |
| **ANSI/ASSP Z10.0** (OHSMS), **ANSI/ISEA 107** (high-visibility), **ANSI/ISEA Z89.1** (head protection) | Current editions per publishers [L24], [L25] | PPE class definitions; hi-vis detection cannot verify performance class | Presence only, not conformity |
| **NFPA 72** (fire alarm) | 2025 edition; video image smoke/flame detection must be **listed** for the purpose [L12] | Fire/smoke analytics | "Supplemental visual indicator", never fire detection |
| **NFPA 70E** (electrical safe work), **NFPA 51B** (hot work) | Current editions | Approach boundaries; hot-work permits | Zone observation only |
| **EU OSH Framework Directive 89/391/EEC** and daughter directives | In force | Employer duties incl. worker consultation | Supports risk assessment evidence |
| **India OSH Code 2020** | In force from **21 November 2025** (S.O. 5321(E)); Central Rules notified **8 May 2026** (G.S.R. 345(E)) per secondary sources; state rules vary [L07] | Employer safety duties; covers establishments with 10+ workers and all mines and docks | Supports employer monitoring; not a statutory device |

## 3. EU AI Act

**Text checked:** Article 5 and Annex III (via artificialintelligenceact.eu) [L01], [L02]. **Timeline:** Article 5 prohibitions apply since **2 February 2025**. The Digital Omnibus on AI (political agreement 7 May 2026; adopted June 2026) defers Annex III high-risk obligations to **2 December 2027** and Annex I (product-embedded) obligations to **2 August 2028**, according to law-firm and specialist summaries [L03] ⚖ (verify against the Official Journal text).

| Question | Analysis |
|---|---|
| **Prohibited practices** | Art. 5(1)(f) prohibits AI that infers emotions of a natural person in the workplace, "except where … intended … for medical or safety reasons." The safety exception is narrow and contested ⚖. **Decision: SafeSight does not build emotion, stress, fatigue or intoxication inference.** Art. 5(1)(g) prohibits biometric categorisation by sensitive attributes. **Decision: no attribute inference about people beyond PPE and posture.** |
| **High-risk via Annex III 4(b)** | Covers AI "intended to be used to make decisions affecting terms of work-related relationships … or to monitor and evaluate the performance and behaviour of persons in such relationships." A system that attributes unsafe behaviour to identifiable workers and feeds discipline is very likely in scope. An area-level exposure monitor that does not identify or evaluate individuals is arguably outside, but this is unsettled ⚖. **Decision:** (a) SafeSight's default design is area- and hazard-centred, without identity; (b) the commercial terms prohibit using SafeSight outputs for individual performance evaluation or discipline unless the deployer accepts high-risk deployer obligations; (c) the product is engineered to the high-risk requirements anyway (risk management, data governance, logging, transparency, human oversight, accuracy and robustness), because that is also good safety engineering. |
| **High-risk via Annex I** | If SafeSight were a safety component of machinery under the Machinery Regulation, it would be high-risk. **Decision:** not a safety component (see §2). |
| **Deployer duties if high-risk** | Art. 26: use per instructions, human oversight, log retention (at least six months), and **inform workers' representatives and affected workers before use at the workplace** (Art. 26(7)). SafeSight should ship a worker-information template regardless. |
| **Transparency** | Signs and notices that AI-assisted monitoring is in use; plain-language description of what is and is not detected. |

## 4. Privacy law by jurisdiction

| Jurisdiction | Key points | Design consequences |
|---|---|---|
| **EU (GDPR)** | Lawful basis typically legitimate interests (Art. 6(1)(f)) or legal obligation for OSH duties (Art. 6(1)(c)); employment-specific national rules (Art. 88); a **DPIA** (Art. 35) is expected for systematic monitoring of workers; EDPB Guidelines 3/2019 on video devices [L15]; works councils have co-determination rights over technical monitoring devices in Germany (BetrVG §87(1) no. 6) [L16] and similar rights elsewhere ⚖ | Redaction, retention limits, purpose limitation (safety only), access logs, no identification, DPIA kit, works-council information pack |
| **UK (UK GDPR)** | ICO *Monitoring workers* guidance (3 Oct 2023): DPIA required for high-risk monitoring and strongly recommended for any worker monitoring; transparency and proportionality [L09] | Same as EU |
| **India (DPDP Act 2023 + Rules 2025)** | Rules notified 13 Nov 2025 with phased commencement; most obligations by about **13 May 2027** [L06]. Section 7(i) allows processing without consent "for the purposes of employment or those related to safeguarding the employer from loss or liability", but its limits are undefined and commentators warn it is not blanket authority for surveillance [L08] ⚖ | Notices to workers, security safeguards, breach-response readiness, purpose limitation, retention limits; keep processing on-premises where customers prefer |
| **US** | No general federal privacy law; some states require notice of electronic monitoring of employees (for example New York Civil Rights Law §52-c) ⚖; biometric laws (for example Illinois BIPA) apply to face geometry and similar identifiers | No face recognition or face templates; monitoring notice templates |

## 5. Fairness and environmental performance

- **Headwear and exemptions.** Caps, hoods, scarves, turbans and other religious headwear are all "not a hard hat" to the current model by design (`docs/limitations.md`). Some jurisdictions exempt turban-wearing Sikhs from head-protection requirements in specific workplaces (for example Great Britain's Employment Act 1989 s.11, later extended) ⚖. **Requirement:** policies must support documented exemptions and per-zone PPE rules; alerts on religious headwear must be reviewable without stigma; evaluation slices must include headwear types.
- **Skin tone and appearance.** SafeSight must not infer sensitive attributes. Fairness is assessed with *appearance proxies that do not require inference about the person*: lighting, distance, clothing colours, PPE colours and headwear type, using labelled evaluation sets.
- **Environment.** Report performance by day/night, weather, camera height and distance band (`09` §4).

## 6. Licensing and commercialisation (Part 17)

| Item | Licence | Commercial position | Action |
|---|---|---|---|
| SafeSight code | AGPL-3.0-only | Commercial use allowed; distributing or serving modified versions over a network triggers source-offer obligations | Decide the business model: open core under AGPL with commercial support, or dual licensing (requires copyright ownership of all contributions; CONTRIBUTING currently uses inbound = outbound AGPL, which would need a CLA to dual-license) ⚖ |
| Ultralytics library and YOLO weights | AGPL-3.0 or Enterprise licence [L18] | Closed-source product requires Enterprise licence; Ultralytics asserts trained models are AGPL by default | Either license from Ultralytics or migrate the product line to an Apache-2.0 detector (RT-DETR, D-FINE, RF-DETR) after benchmarking |
| M5 weights | AGPL-3.0 (Ultralytics) + CC BY-NC-SA 4.0 (SH17) | **Not usable commercially; not distributable** | Keep as research champion; never ship |
| Construction-PPE | AGPL-3.0 | Usable under AGPL; model inheritance question open | Prefer site data + CC BY data for product line |
| Mendeley PPE v6 | CC BY 4.0 | Usable with attribution | Keep |
| SH17, MOCS, CrowdHuman, MOT17/20, Objects365 (per aggregators) | Non-commercial | Research line only | Never in product training |
| LOCO, Open Images | Permissive / CC BY | Usable (verify LOCO LICENSE file) | Product line candidates |
| Python dependencies (PyTorch, OpenCV, NumPy, SciPy, pandas, Pillow, Streamlit, Plotly, …) | BSD/Apache/MIT family per `THIRD_PARTY_NOTICES.md` | Compatible | Keep notices |
| NVIDIA CUDA libraries in the PyTorch CUDA build | NVIDIA terms | Redistribution rules apply to bundled images | Check before shipping container images ⚖ |
| **Patents** | — | Computer-vision safety monitoring is an active patent area (one 2026 industry analysis counted about 60 construction-site monitoring patents that year alone) | Freedom-to-operate search before commercial launch, especially for near-miss/TTC analytics and dynamic zones ⚖ |

**Repository's licence is not changed by this work.** `LICENSE`, `LICENSING_DECISION.md` and `THIRD_PARTY_NOTICES.md` were not modified.

## 7. Security

### 7.1 Current state (from the audit)
- No secrets in the repository (verified by the v0.1.0 audit; `.env.example` documents that none are needed).
- No authentication; the app binds to localhost; evidence and database unencrypted; no audit log; no retention.

### 7.2 Threat model for a deployed system (summary)

| Threat | Impact | Control |
|---|---|---|
| Unauthorised access to live video or evidence | Privacy breach, misuse for surveillance | SSO + roles; evidence access logging; redaction by default; encryption at rest |
| Tampering with policies or zones to hide hazards | Safety failure, liability | Signed, versioned policies; audit log; approval workflow |
| Tampering with evidence | Investigations compromised | SHA-256 hash recorded at write; append-only audit; legal-hold flag |
| Camera network as an attack path into OT | Plant compromise | Cameras on isolated VLAN; edge node outbound-only; IEC 62443 zones and conduits [L23] |
| Model or update supply-chain compromise | Silent failure | Signed model artefacts; hash verification at load (the app already verifies the M5 hash in the settings view) |
| Denial of service / camera failure | Missed hazards | Camera health alarms; "monitoring degraded" state visible to operators |

### 7.3 Data retention and access defaults (proposed)

| Data | Default retention | Access |
|---|---|---|
| Live video | Not stored by SafeSight (VMS remains system of record) | Operators |
| Evidence keyframes (redacted) | 90 days | Safety roles |
| Evidence clips for HIGH/CRITICAL events | 1 year or until investigation closes | Safety roles; access logged |
| Event metadata (no images) | 3 years (trend analysis) | Per role |
| Audit log | 3+ years, append-only | Admin, auditor |
| Legal hold | Overrides deletion | Admin with reason |

Defaults are configurable per site and must match the customer's DPIA ⚖.

## 8. Human review and escalation

- Every CRITICAL/HIGH event is reviewed by a person; the review outcome (confirmed, false alarm, not observable) is recorded and feeds validation metrics.
- "Weak evidence" events go to a review queue rather than real-time paging, unless the hazard severity is 5 (policy decides).
- Escalation follows the approved policy: unacknowledged HIGH alerts escalate after a configurable time.
- Outputs are framed for **coaching and system improvement** (layout, barriers, routes), not discipline, which is both a privacy safeguard and the approach safety research supports.

## 9. Items that require qualified legal review ⚖

1. Whether a given deployment is high-risk under EU AI Act Annex III 4(b) and the scope of the Art. 5(1)(f) safety exception.
2. Final AI Act application dates after the Digital Omnibus (Official Journal text).
3. Lawful basis, DPIA and works-council or union consultation per country.
4. DPDP Act s.7(i) reliance and notice obligations; state-level rules under the OSH Code.
5. Machinery Regulation: confirm SafeSight is not a safety component in each integration.
6. Ultralytics Enterprise licence terms vs. migration; AGPL obligations for hosted offerings; dual-licensing and CLA.
7. Freedom-to-operate (patents).
8. Headwear exemptions per jurisdiction.
