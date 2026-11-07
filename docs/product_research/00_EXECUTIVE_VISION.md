# 00 — Executive vision and recommended direction

Date: 5 November 2026. Read this first; everything here is supported in documents 01–14.

## The question

> If a real industrial company deployed SafeSight across its facilities, what meaningful safety problems could it solve, how reliably could it solve them, and why would that company choose it over the alternatives?

## The short answer

**Today:** SafeSight is a carefully built, honest single-camera prototype. It can flag bare heads and restricted-area entries on clear, near-to-mid-range footage, refuses to guess when it cannot see, and records evidence. It has **not** been validated on any real site's cameras, it handles one camera per server, and its champion model **cannot be used commercially** because of its training-data licence (SH17, CC BY-NC-SA 4.0) and framework (Ultralytics, AGPL-3.0). Its reliability on real sites is therefore **unknown**, not poor or good.

**In 12–18 months, if the roadmap is followed:** in warehouses and the material-handling areas of factories, SafeSight could **measure, with published per-camera accuracy, how often people are exposed to moving vehicles and machine zones, catch genuine vehicle–pedestrian near misses, and turn those patterns into layout and procedure changes**, all on-site, without sending video to a cloud, and with every alert explained and every rule approved by a competent person.

**Why a company would choose it:** not for breadth (Intenseye, Protex AI, Voxel and others already offer 40–50+ detections and polished workflows), but because SafeSight would be the one that **proves its accuracy on the customer's own cameras, measures high-energy exposure instead of counting violations, runs fully on-premises, and can be inspected line by line**. Customers who need those properties (privacy- or connectivity-constrained sites, regulated buyers, cost-sensitive mid-market operators) are the target. Customers who do not need them are better served by established vendors today.

## What the research found

1. **The hazards that kill most are people meeting moving energy.** Transportation incidents were 38 % of US work deaths in 2024; falls 844 deaths; vehicles striking pedestrians are a leading cause in ports, warehousing and mining; machinery causes most amputations [S01], [S03], [S05], [S10], [S11]. These interactions are often visible to fixed cameras.
2. **Safety practice has moved from counting injuries and violations to preventing serious injuries and fatalities (SIF)** by checking that high-energy hazards have direct controls (the HECA method used by utilities and construction researchers) [S17]. A PPE-violation counter measures the weakest control layer. SafeSight should measure exposure to high energy.
3. **The market is real and crowded.** Verdantix benchmarked 10 video-analytics-for-safety vendors in 2026 on PPE, behaviour, unsafe conditions, area controls and vehicle safety [C07]. Competitors sell catalogue breadth and workflow; **none publishes validated, per-camera performance**, and outcome figures are vendor claims.
4. **Customers struggle with false alarms, coverage gaps, worker trust and video leaving the site.** These are reliability, evidence and governance problems, which match SafeSight's existing engineering culture.
5. **Cameras cannot detect gases, verify energy isolation, judge competence or validate permits.** Those need sensors and integrations (OPC UA, MQTT, permit systems). Claiming otherwise would be dangerous.
6. **Regulation is tightening and favours privacy-first, explainable design.** EU AI Act prohibitions (including workplace emotion inference) apply since February 2025; Annex III high-risk obligations, which can cover worker monitoring, are deferred to December 2027; India's OSH Code took effect on 21 November 2025 and DPDP obligations phase in through about May 2027; the EU Machinery Regulation applies from January 2027 [L01]–[L07].
7. **Licensing is the hidden blocker.** A commercial product needs a model trained only on commercially usable data and either an Ultralytics Enterprise licence or a move to an Apache-2.0 detector (RT-DETR, D-FINE, RF-DETR) [L18], [P06]–[P08].

## Decisions

| Decision | Choice |
|---|---|
| **Positioning** | An *observational* safety-intelligence layer that measures exposure to high-energy hazards with proven per-camera accuracy. Never a safety function, never "the site is safe". |
| **Wedge** | Indoor fixed-camera facilities: warehouses, distribution centres and factory material-handling areas; mid-size operators (1–5 sites, 20–100 cameras/site); first in India and the EU/UK. |
| **Headline capability** | Vehicle–pedestrian conflicts measured with ground-plane time-to-collision and post-encroachment time, plus typed zones and hi-vis. |
| **Expansion** | Logistics → Manufacturing (machine-state context) → Ports → Construction → Energy, Chemical/Pharma → Oil & Gas, Mining. |
| **Deployment** | Edge-first, offline-capable, optional central server; hybrid for multi-site. |
| **Architecture path** | Evolve, don't rewrite: extract a headless multi-camera runtime; keep Streamlit for the single-node edition until multi-site customers require a dedicated web front end. |
| **Model line** | Keep M5 as the research champion (never shipped); build a product-line detector on commercially usable data after a framework benchmark. |
| **Do not build** | Emotion/fatigue/intoxication inference, face recognition, individual productivity scoring, fire detection claims, gas inference from RGB. |

## Priorities

- **P0 foundations:** hazard taxonomy and risk/policy engine, typed zones, event-level validation (**built in this branch**), plus a headless multi-camera runtime with camera health.
- **P1:** vehicle–pedestrian conflict analytics, incident lifecycle and escalation, recurring-pattern analytics, machine-state context adapter, zone schedules and keep-clear zones, hi-vis, privacy and security controls, shadow mode, and the commercially usable detector.
- **P2:** suspended-load zones with crane data, person-down, station PPE, ergonomic screening, supplemental fire/smoke, AI-drafted summaries, conformal per-camera calibration.
- **P3:** spills, harness, learned trajectory prediction, cross-camera reconstruction.

## What was built in this branch

Foundations that every later capability depends on, with no change to existing behaviour:

- A **hazard taxonomy** with energy sources, default severities and honest implementation status.
- A **configurable, explainable risk policy engine**: severity × exposure, context that can never lower risk when unknown, evidence quality kept separate from risk, and the policy's approval status recorded with every assessment.
- **Typed zones** (machine exclusion, suspended load, electrical, vehicle-only, …) that are backward compatible.
- **Risk assessments stored for every incident**, with exposure duration and escalation tracking.
- **Event-level validation tooling** (event precision/recall with confidence intervals, false alarms per camera-hour, latency, duplicates, missed critical hazards).

## The biggest risk

**No real-site data.** Without a partner site and labelled footage, every capability stays at "controlled demonstration". The single most valuable next step is not code: it is a shadow-mode pilot agreement with one warehouse or plant.

## Next 90 days

1. Secure one pilot site and a data agreement (shadow mode, no worker-facing alerts).
2. Label time-stamped episodes for the existing demo and unseen clips; publish the first event-level baseline with intervals.
3. Build the headless multi-camera runtime with RTSP and camera health.
4. Benchmark Apache-2.0 detectors against the current pipeline and decide the licensing path.
5. Start the vehicle class (forklift, pallet truck) and ground-plane calibration.
