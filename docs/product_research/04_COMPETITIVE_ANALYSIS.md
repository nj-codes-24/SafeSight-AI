# 04 — Competitive analysis

Research date: 5 November 2026. Sources: `14_SOURCE_REGISTER.md` (IDs C01–C12). **Rule used throughout:** a capability is listed as *documented* only if it appears in the vendor's own material or a named third party; outcome numbers (for example "91 % fewer recordables") are **vendor claims**, not independently validated results. "Not public" means the information was not found, not that it does not exist.

## 1. Market structure

| Segment | Examples | What they sell |
|---|---|---|
| **Safety video analytics platforms** (direct competitors) | Intenseye, Protex AI, Voxel, viAct, Visionify, Everguard.ai, Kinetic Eye | AI on existing CCTV, a catalogue of unsafe acts and conditions, alerts, workflow, dashboards |
| **General video AI / cloud VMS with safety modules** | Spot AI, Kogniz, camera makers' on-camera analytics | Security plus operations plus some safety detections; per-camera subscriptions |
| **On-vehicle proximity systems** | Blaxtair (stereo camera on the truck), SEEN Safety (hi-vis vest as a sensor target), UWB tag systems (for example ELOKON, Triomobil) | Real-time warnings in the cab; hardware per vehicle |
| **EHS management software** | Intelex, Cority, Enablon, Sphera, VelocityEHS | Incident, action, audit and compliance records; integration targets, not competitors |
| **Open source** | Ultralytics solutions (AGPL-3.0), Roboflow libraries, NVIDIA reference apps, many academic PPE projects | Components; no product, workflow or validation |

Verdantix's 2026 *Smart Innovators: Video Analytics for Safety* benchmarked **10 vendors** on five capability areas: **PPE detection, behavioural safety, unsafe conditions, area controls and vehicle safety** [C07]. That list is effectively the market's definition of "table stakes". Protex AI announced it was the top-scoring vendor (vendor statement) [C02]; viAct and Intenseye are also named as included [C07].

## 2. Competitor profiles

### Intenseye
- **Documented:** computer vision on existing cameras for unsafe acts, ergonomic risks and compliance; an assistant ("SafetyGPT") for compliance questions and reports; product lines for core AI, EHS suite, ergonomics and industrial integrations (IoT devices, facility systems); corrective-action workflows; an on-floor display product ("Intenseye TV", June 2026) [C01].
- **Privacy:** states no facial recognition, real-time masking of faces and bodies by default, "3D anonymisation", timestamp anonymisation, SOC 2 Type II and GDPR alignment [C01]. This is the most developed public privacy position in the segment (vendor claims; not audited here).
- **Scale:** 45–50+ use cases claimed (figures vary by source); about USD 93 M disclosed funding including a USD 64 M Series B (February 2024) [C01].
- **Pricing:** not public.

### Protex AI
- **Documented:** unsafe events on existing CCTV, including PPE non-compliance, forklift–pedestrian conflicts, area breaches, ergonomics and housekeeping; configurable rules; warehouses, manufacturing and ports [C02].
- **Funding:** USD 36 M Series B led by Hedosophia with Salesforce Ventures [C02].
- **Recognition:** top score in Verdantix 2026 report (vendor-announced) [C02], [C07].
- **Pricing:** not public. AWS Marketplace listing exists.

### Voxel
- **Documented:** hazards and risky behaviours from existing security cameras; near-miss vehicle interactions, blocked exits, ergonomics and spills (2024 coverage); routing into assignments, coaching and executive reporting; "deploys in 48 hours" (claim); Risk Insights daily summaries (April 2026) [C03].
- **Funding:** USD 44 M Series B (June 2025), total about USD 61–64 M [C03].
- **Outcome claim:** 91 % reduction in recordable injuries (vendor claim).
- **Pricing:** not public.

### viAct
- **Documented:** scenario-based modules: PPE, fire and smoke, danger-zone intrusion, slip/trip/fall, confined-space monitoring, vehicle and machinery collision, work at height; progress tracking; centralised platform (viHUB) [C04]. Third-party listing says any 2 MP or better RTSP camera can connect to its cloud (unverified).
- **Focus:** construction and infrastructure, strong in Asia.
- **Pricing:** not public.

### Everguard.ai
- **Documented:** "Sentri360" combines computer vision with real-time location systems (RTLS), wearables and edge computing; steel and heavy industry origins (SeAH Group, Zekelman Industries); a construction deployment announced [C05].
- **Note:** most public material is 2020–2022.

### Spot AI and general video AI
- **Documented:** PPE, near-miss, fall and crowding detection on existing cameras as part of a broader security/operations platform; quote-based per-camera subscription. A widely repeated planning figure is about USD 99 per camera per month (third-party guide repeating vendor material) [C06].
- **Comparison pages** on competitor sites (for example Spot AI vs. Kinetic Eye) are marketing and were not used as evidence of competitor capability.

### On-vehicle proximity systems
- **Blaxtair:** stereoscopic camera on the vehicle watching blind spots for pedestrians; vendor reports up to 70 % fewer near misses from internal site data [C08].
- **SEEN Safety:** tagless; detects the retro-reflective material of standard hi-vis clothing [C08].
- **UWB systems:** tags on people and vehicles; detection through racks and around corners; vendors themselves describe camera and UWB as complementary [C08].

## 3. Comparison matrix

Legend: ● documented · ◐ partially documented or third-party only · ○ not found in public material · n/p not public.

| Dimension | Intenseye | Protex AI | Voxel | viAct | Everguard | Spot AI | SafeSight today | SafeSight target (12–18 months) |
|---|---|---|---|---|---|---|---|---|
| Industries | Manufacturing, logistics, heavy industry ● | Warehousing, manufacturing, ports ● | Logistics, manufacturing, retail DCs ● | Construction, infrastructure ● | Steel/heavy industry, construction ● | Cross-industry ● | Construction (demo) | Logistics + manufacturing, then ports and construction |
| PPE | ● | ● | ◐ | ● | ◐ | ● | Hard hat only | Hard hat, hi-vis; station PPE |
| Behaviour | ● (incl. ergonomics) | ● (incl. ergonomics) | ● (incl. ergonomics) | ● (slip/trip/fall, height) | ◐ | ● (fall, crowding) | ○ | Person down; ergonomic screening (analytics) |
| Machinery | ◐ (area controls, integrations) | ◐ (area breaches) | ○ | ● (machinery collision) | ● (sensor fusion) | ○ | Static zones | Typed zones + PLC/OPC UA machine state |
| Vehicles | ● | ● (forklift–pedestrian) | ● (near-miss vehicle) | ● | ● (RTLS) | ● | ○ | Detection + ground-plane TTC/PET near misses |
| After detection | Workflow, corrective actions ● | Workflow ◐ | Assignments, coaching ● | Dashboards ◐ | Alerts to wearables ● | Alerts, search ● | Incident review statuses | Acknowledge → investigate → corrective action, evidence chain |
| Analytics | Dashboards, AI assistant ● | Dashboards ◐ | Risk Insights ● | ◐ | ◐ | ● | Per-session charts | Exposure and near-miss trends, recurring-pattern detection |
| Integrations | IoT, facility systems ● | n/p | n/p | n/p | RTLS, wearables ● | VMS ● | ○ | RTSP/ONVIF, MQTT, OPC UA, webhooks, EHS export |
| Deployment | n/p (cloud platform implied) | n/p | Cloud, existing cameras ● | Cloud (viHUB) ◐ | Edge ● | Cloud + on-site appliance ◐ | Single workstation, offline ● | Edge-first, optional central server, fully offline capable |
| Privacy | Masking, no face recognition, SOC 2 ● | Privacy messaging ◐ | n/p | n/p | n/p | n/p | No identification; evidence unredacted | Redaction by default, retention limits, DPIA kit |
| Pricing | n/p | n/p | n/p | n/p | n/p | ~USD 99/camera/month (third-party) ◐ | Free, open source | Open core; per-camera edge licence for the commercial build |
| Distinctive | Breadth + privacy + assistant | Rules + Verdantix score | Speed to deploy + risk summaries | Construction scenarios | Sensor fusion in steel | Broad video platform | Honest uncertainty, reproducible evaluation | Measured reliability, energy-based risk, edge-first, auditable |

## 4. What competitors already do exceptionally well

1. **Zero-new-hardware deployment** on existing CCTV, with remote onboarding.
2. **Breadth** across the five Verdantix areas; a new entrant cannot match this catalogue in the near term.
3. **Workflow after detection:** assignment, coaching and corrective actions, which is what turns alerts into risk reduction.
4. **Executive-level reporting** and, increasingly, LLM-generated summaries.
5. **Privacy engineering** (Intenseye's masking-by-default is a strong reference point).

## 5. What customers still struggle with

Evidence here is weaker (vendor blogs, one academic system report, and practice literature), so each point is marked with its basis.

| Problem | Basis |
|---|---|
| **False alarms and alert fatigue.** There is an inherent trade-off between alert delay and false-positive frequency [C12]; practitioners report systems being ignored or switched off when false positives exceed tolerance. | Academic (Toolbox Spotter) + practice literature |
| **Outcome claims are not independently validated.** Published results are vendor-reported reductions without methods. | Observed across all vendors |
| **Coverage gaps.** Hazards outside existing camera fields of view require new cameras or repositioning, which erodes the "no new hardware" promise. | Third-party review of Protex AI [C02] |
| **No equipment context.** Video-only systems cannot tell a running machine from a stopped one, or a loaded crane from an idle one, so severity is guessed. | (analysis) from public feature lists |
| **Workforce trust and consultation.** Works councils, unions and privacy regulators require consultation, DPIAs and limits on use for discipline. | EU AI Act Art. 26(7) duty to inform workers' representatives for high-risk systems [L01]; ICO guidance [L09]; BetrVG §87 [L16] |
| **Cloud video export.** Some sites cannot or will not send video off-site (defence suppliers, pharma, data-localisation preferences). | (analysis); supports edge-first |

## 6. Where SafeSight can realistically differentiate

These are opportunities, each tied to evidence of a gap. They are developed in `13_DIFFERENTIATION_AND_INNOVATION.md`.

1. **Measured reliability as the product.** Publish per-site acceptance reports: false alarms per camera-hour, missed-episode rate on labelled footage, latency, with the method. No competitor publishes this. SafeSight's existing evaluation discipline (leak-free splits, run-once test sets, two-threshold policy) is the foundation.
2. **Energy-based exposure, not violation counts.** Align outputs with HECA/SIF practice: "high-energy exposures without a direct control, per shift and area". Industry leaders adopting SIF programmes are asking for exactly this measure [S17], [S18].
3. **Near-miss measurement for vehicle–pedestrian interaction** using surrogate safety measures (TTC, PET) on calibrated ground planes, instead of distance-only proximity.
4. **Machine-state-aware zones** through OPC UA / MQTT, so that a person in a robot cell is critical when the cell is live and informational when it is locked out.
5. **Edge-first, offline, self-hostable**, with redaction by default and evidence that never leaves the site unless the customer chooses.
6. **Auditable open core.** The AGPL code base lets customers, unions and auditors inspect what the system does. That is a trust advantage in regulated environments, if the commercial licensing path is resolved (`10` §6).

## 7. What would make a customer choose SafeSight over an established provider

**Honest answer (analysis):** not breadth, brand or case studies; established vendors win those today. A customer would choose SafeSight when at least two of the following are true:

- They **cannot export video** to a vendor cloud, or connectivity is poor.
- They need **verifiable performance** (insurer, regulator, union or corporate audit) and value a published validation method over vendor claims.
- Their priority risk is **vehicle–pedestrian interaction or machine exclusion zones**, and they want near-miss and exposure measurement rather than PPE counts.
- They want to **own and extend** the system (integrators, large enterprises with in-house engineering, public-sector buyers).
- They are **cost-sensitive mid-market sites** (for example Indian manufacturers and 3PLs) for which per-camera cloud subscriptions are hard to justify.

If none of these apply, an established provider is the better choice for that customer, and SafeSight should not pretend otherwise.
