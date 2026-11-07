# 08 — Industry product packages

Date: 5 November 2026. A package is **the common core + a policy template + zone kinds + a small set of models + optional integrations**. Packages are configuration, not forks.

## 1. Common core (every package)

| Capability | Status |
|---|---|
| Person detection, anonymous tracking | Built (M5 research model; product model needed) |
| Typed zones with schedules; foot-point logic | Static typed zones built; schedules P1 |
| Hazard taxonomy, risk policy engine, assessments with explanation | Built in this branch |
| Incident lifecycle, evidence, review, CSV | Built (lifecycle extensions P1) |
| Event-level validation tooling | Built in this branch |
| Camera health and view-integrity checks | P1 |
| Notifications and escalation | P1 |
| Redaction and retention | P1 |
| Analytics: exposure, near-miss and pattern trends | P1 |

## 2. Package overview

Legend: **S** shared core model · **D** dedicated model · **I** integration or sensor required.

| Package | Readiness | Priority |
|---|---|---|
| **SafeSight Logistics** | Wedge; first to pilot | P1 |
| **SafeSight Manufacturing** | Shares 70 % with Logistics; adds machine-state context | P1/P2 |
| **SafeSight Ports** | Vehicle and zone core reused | P2 |
| **SafeSight Construction** | PPE head start; hardest environment | P2 |
| **SafeSight Energy** (substations, generation) | Zone-centric | P2 |
| **SafeSight Chemical & Pharma** | Selective modules | P2/P3 |
| **SafeSight Oil & Gas** | Hazardous-area hardware, permits | P3 |
| **SafeSight Mining** | Fixed-point analytics only | P3 |

## 3. SafeSight Logistics (warehouses, distribution centres, cross-docks)

| Capability | Type | Notes |
|---|---|---|
| Forklift / pallet-truck / tugger detection | D (fine-tuned on LOCO + site data) | Product-line licence-clean |
| Vehicle–pedestrian conflicts: separation, closing speed, TTC, PET | S + ground-plane calibration | The headline capability |
| Pedestrian in `vehicle_only` aisle; vehicle in `pedestrian_only` walkway | S | Typed zones |
| Hi-vis compliance in vehicle areas | D (hi-vis class) | Per-zone requirement |
| `keep_clear` zones: exits, extinguishers, eyewash, dock edges | S (static-object dwell) | OSHA 1910.37 relevance |
| Congestion at intersections and docks | S analytics | Pattern detection |
| Person-down in low-traffic aisles | P2 | Human confirmation |
| Optional: on-truck proximity systems, WMS/telematics, dock-lock status | I | Context, not replacement |

**Default policy highlights:** vehicle–pedestrian conflict severity 5; TTC < 1.5 s → HIGH, < 0.8 s → CRITICAL (starting values for site validation, not validated thresholds); exits blocked > 5 min → MEDIUM.
**Workflows:** shift supervisor reviews near-miss clips daily; weekly route-conflict heatmap for layout changes (barriers, crossings, one-way aisles); monthly report to EHS.
**Metrics:** near misses per 1,000 vehicle-hours by area, pedestrian exposure minutes in vehicle aisles, exit-blocked minutes.

## 4. SafeSight Manufacturing

| Capability | Type | Notes |
|---|---|---|
| Everything in Logistics for in-plant traffic | S/D | |
| Machine / robot cell exclusion zones | S | `machine_exclusion` kind |
| Machine state from PLC via OPC UA or MQTT | I | Severity depends on it; unknown state never lowers risk |
| Conveyor reach-in (wrist keypoint in pinch-point polygon while running) | D (pose) + I | P2 |
| Station PPE: face shields, goggles, welding masks | D (close cameras) | P2 |
| Ergonomic screening by station (trend, not individuals) | D (pose) | P2 |
| Guard-open detection in fixed views | D per guard | P3 |

**Default policy highlights:** person in `machine_exclusion` with machine running → CRITICAL; with machine reported locked out and a maintenance permit → INFO (requires approved policy and both signals).
**Integrations:** OPC UA client, MQTT Sparkplug, CMMS work orders for corrective actions.
**Safety statement in every deployment:** the cell's certified safeguards (guards, interlocks, light curtains, scanners per ISO 13849/IEC 62061, robot safety per ISO 10218-2:2025) remain the safety function.

## 5. SafeSight Ports and material handling

| Capability | Type |
|---|---|
| Pedestrian vs. handling equipment conflicts | S/D (straddle carriers, reach stackers, terminal tractors need site data) |
| Person under suspended container (quay crane) | D + I (crane PLC hook/spreader position) |
| Automated-area intrusion | S + I (access control) |
| Quay-edge zones | S |
| Hi-vis | D |
| Night and rain image-quality monitoring | S (camera health) |

## 6. SafeSight Construction

| Capability | Type | Notes |
|---|---|---|
| Hard hat (existing) and hi-vis | S/D | Retrain on commercially usable data |
| Plant swing-radius and excavation exclusion zones | S | Temporary zones with validity windows |
| Person under suspended load | D + I (crane data) | P2 |
| Vehicle–pedestrian at gates and haul roads | S | Reuses Logistics |
| Edge zones for unprotected edges (drawn by site) | S | P2; automatic edge detection P3 |
| Harness presence | D | P3, never "tied off" |
| Far-field workers | D (higher resolution tiles, P30-style far-field training) | Known current weakness |

**Deployment notes:** camera repositioning is frequent → view-integrity check and zone re-validation workflow are mandatory; solar/4G edge kits; weatherproofing.

## 7. SafeSight Energy (substations and generation plants)

| Capability | Type |
|---|---|
| Approach boundaries around energised equipment (`electrical` zones) | S |
| Substation intrusion | S |
| Switching state / energised status context via SCADA/OPC UA | I |
| PPE presence (not arc rating) | S/D |
| Hot-surface/steam zones | S + thermal optional |

## 8. SafeSight Chemical & Pharma

| Capability | Type |
|---|---|
| Confined-space entry/exit counting and occupancy display for the attendant | S (zone `confined_space`) + I (permit) |
| Area PPE: face shields, goggles, chemical suits | D |
| `keep_clear`: eyewash, safety showers, exits | S |
| Hot-work area with permit context | S + I |
| Visible spills | P3 (thermal recommended) |
| Gas and process conditions | I only (never inferred from video) |

## 9. SafeSight Oil & Gas and Mining (later)

**Oil & Gas:** red-zone management on rig floors (with drilling-system context), hot-work with permit and gas-test integration, site-road vehicle–pedestrian, supplemental flame/smoke. Requires ATEX/IECEx-certified camera housings in classified areas; gas detection stays with certified detectors.

**Mining:** fixed-point analytics at crushers, workshops and loading points; muster headcount with tag integration; dust-induced image-quality monitoring. On-vehicle collision avoidance is out of scope (dedicated CAS vendors).

## 10. What each package shares, needs, and integrates

| | Logistics | Manufacturing | Ports | Construction | Energy | Chem/Pharma | O&G | Mining |
|---|---|---|---|---|---|---|---|---|
| Person tracking, zones, risk, incidents | S | S | S | S | S | S | S | S |
| Vehicle detection + TTC/PET | D | D | D | D | ○ | ○ | D | D |
| Hi-vis | D | D | D | D | D | ○ | D | D |
| Hard hat | ○ | ○ | ○ | S | S | ○ | S | S |
| Pose models | P2 | P2 | ○ | P3 | ○ | ○ | ○ | ○ |
| Machine/equipment state | ○ | I | I (crane) | I (crane) | I (SCADA) | I (DCS) | I (rig) | I |
| Permits / access control | ○ | I | I | I | I | I | I | I |
| Gas / environmental sensors | ○ | ○ | ○ | ○ | ○ | I | I | I |
| Special hardware | — | — | — | Weatherproof, 4G | — | Cleanroom options | ATEX/IECEx | Dust/vibration |

(S shared · D dedicated model · I integration · ○ not needed for the first release)
