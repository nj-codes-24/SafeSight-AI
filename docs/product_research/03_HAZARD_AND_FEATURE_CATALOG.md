# 03 — Hazard and capability catalogue

Research date: 5 November 2026. Scores are **(analysis)**: structured expert judgement informed by the sources in `02_INDUSTRY_RESEARCH.md` and `05_RESEARCH_PAPERS_AND_TECHNOLOGY.md`, not measured values. They exist to make prioritisation explicit and arguable.

## 1. Scoring scales

| Dimension | Scale |
|---|---|
| **Sev** — worst credible outcome | 5 fatality likely · 4 fatality possible / permanent disability · 3 lost-time injury · 2 minor injury · 1 negligible |
| **Exp** — frequency of exposure in that industry | 5 continuous/many times per shift · 4 daily · 3 weekly · 2 monthly · 1 rare |
| **CV** — detectability from fixed RGB cameras | H reliable with good placement · M feasible with constraints · L research-grade · — not observable |
| **Data** — suitable, usable training/eval data | H commercially usable sets exist · M partial / licence issues · L little or none |
| **Diff** — technical difficulty | L · M · H |
| **Use** — operational usefulness to a safety team | 1–5 |
| **RR** — potential to reduce risk if deployed well | 1–5 |
| **Mode** — primary sensing | CV camera · TH thermal · SEN IoT sensor · INT system integration (PLC, permits, access) · HUM human inspection |

## 2. Industry-to-hazard matrix

### 2.1 Construction and infrastructure

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Fall from unprotected edge / opening | 5 | 4 | L | L | H | 5 | 4 | CV+HUM |
| C2 | Fall from ladder or misuse of ladder | 4 | 4 | M | L | H | 4 | 3 | CV |
| C3 | Fall from scaffold; incomplete guardrails | 5 | 4 | L | L | H | 4 | 3 | HUM+CV |
| C4 | Person within excavator/plant swing radius | 5 | 4 | M | M | M | 5 | 4 | CV+SEN |
| C5 | Person under suspended load | 5 | 3 | M | L | M | 5 | 4 | CV+INT (crane) |
| C6 | Vehicle–pedestrian conflict on haul roads/gates | 5 | 4 | H | M | M | 5 | 4 | CV |
| C7 | Person in excavation exclusion zone | 5 | 3 | H | M | L | 4 | 3 | CV |
| C8 | Missing head protection | 3 | 5 | H | M (licence) | L | 3 | 2 | CV |
| C9 | Missing hi-vis in plant areas | 4 | 5 | H | M | L | 4 | 3 | CV |
| C10 | Missing harness / unclipped at height | 5 | 3 | L | L | H | 5 | 3 | CV (harness), HUM (clipped) |
| C11 | Contact with overhead power lines (boom near line) | 5 | 2 | L | L | H | 4 | 3 | CV+SEN |
| C12 | Struck by falling objects (no toe boards/netting) | 4 | 3 | L | L | H | 3 | 2 | HUM |
| C13 | Blocked access/egress routes | 2 | 4 | M | L | M | 3 | 2 | CV |
| C14 | Fire/smoke on site (hot work, waste) | 4 | 2 | M | M | M | 3 | 2 | CV (supplemental) |

### 2.2 Manufacturing

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| M1 | Person inside live machine/robot cell | 5 | 4 | H (presence) | M | M | 5 | 4 | CV+INT (PLC state) |
| M2 | Guard open / interlock bypassed while running | 5 | 3 | L–M | L | H | 5 | 4 | INT first, CV supplemental |
| M3 | LOTO not applied during maintenance | 5 | 3 | — (lock visible ≠ energy isolated) | L | H | 4 | 3 | INT+HUM |
| M4 | Forklift/tugger–pedestrian conflict in-plant | 5 | 5 | H | H (LOCO) | M | 5 | 4 | CV |
| M5 | Pedestrian outside walkway in vehicle aisle | 4 | 5 | H | M | L | 4 | 3 | CV |
| M6 | Reaching into conveyor/pinch point | 5 | 4 | M (pose+zone) | L | M | 4 | 3 | CV+INT |
| M7 | Missing eye/face protection at defined stations | 3 | 5 | M | M | M | 3 | 2 | CV |
| M8 | Missing hearing protection in noise areas | 2 | 5 | L (earplugs invisible) | L | H | 2 | 1 | SEN (noise) + HUM |
| M9 | Awkward posture / repetitive lifting (ergonomics) | 3 | 5 | M (screening) | M | M | 4 | 3 | CV |
| M10 | Blocked emergency exit / extinguisher / eyewash | 3 | 4 | M | L | M | 4 | 3 | CV |
| M11 | Visible spill/leak on floor | 3 | 3 | L (RGB) / M (thermal) | L | H | 3 | 2 | CV+TH |
| M12 | Slip/trip/fall on same level | 3 | 4 | M (event) | M | M | 3 | 2 | CV |
| M13 | Hot-work without permit | 4 | 2 | M (sparks visible) | L | M | 3 | 2 | CV+INT |

### 2.3 Warehousing and logistics

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| W1 | Forklift–pedestrian near miss (separation and closing speed) | 5 | 5 | H | H | M | 5 | 5 | CV |
| W2 | Pedestrian in vehicle-only aisle / vehicle in walkway | 4 | 5 | H | M | L | 5 | 4 | CV |
| W3 | Forklift speeding in zone | 4 | 5 | M (calibration) | M | M | 4 | 3 | CV (+telematics) |
| W4 | Unsafe reversing / blind-corner crossing | 5 | 4 | M | M | M | 4 | 4 | CV |
| W5 | Person under elevated forks/load | 5 | 3 | M | L | M | 4 | 3 | CV |
| W6 | Dock edge: trailer creep, fall from dock | 5 | 3 | M | L | M | 4 | 3 | CV+INT (dock locks) |
| W7 | Missing hi-vis | 3 | 5 | H | M | L | 3 | 2 | CV |
| W8 | Blocked exits / extinguishers / aisles | 3 | 4 | M | L | M | 4 | 3 | CV |
| W9 | Unstable / overhanging rack loads | 4 | 3 | L | L | H | 3 | 2 | CV+HUM |
| W10 | Manual handling posture | 3 | 5 | M | M | M | 3 | 2 | CV |
| W11 | Congestion at docks and intersections | 3 | 4 | H | M | L | 4 | 3 | CV |
| W12 | Person down / prolonged immobility (lone working) | 4 | 2 | M | M (staged) | M | 4 | 3 | CV |

### 2.4 Oil, gas and petrochemical

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| O1 | Toxic/flammable gas release | 5 | 2 | — (RGB) | — | — | 5 | — | SEN (gas), optical gas imaging |
| O2 | Person in red zone on rig floor while pipe moves | 5 | 4 | M | L | M | 5 | 4 | CV+INT |
| O3 | Hot work without valid permit / gas test | 5 | 2 | M | L | M | 4 | 3 | CV+INT+SEN |
| O4 | Visible fire or smoke | 5 | 1 | M | M (D-Fire) | M | 3 | 2 | CV/TH supplemental to listed detection |
| O5 | Large visible liquid release | 4 | 2 | L–M | L | H | 3 | 2 | CV+TH |
| O6 | Confined-space entry without attendant | 5 | 2 | M (entry count) | L | M | 4 | 3 | CV+INT |
| O7 | Vehicle–pedestrian on site roads | 5 | 3 | H | M | M | 4 | 3 | CV |
| O8 | Person under suspended load (cranes, rig) | 5 | 3 | M | L | M | 5 | 4 | CV+INT |
| O9 | PPE (FR clothing, H₂S monitor worn) | 4 | 5 | L | L | H | 3 | 2 | HUM+SEN |
| O10 | Falls from height (derrick, tanks) | 5 | 3 | L | L | H | 4 | 3 | CV+HUM |
| O11 | Restricted/classified area entry | 4 | 3 | H | M | L | 4 | 3 | CV+INT (access) |

### 2.5 Mining and heavy machinery

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| N1 | Haul truck/loader collision with light vehicle or person | 5 | 5 | M (fixed points only) | M | H | 5 | 3 | SEN (on-vehicle CAS) |
| N2 | Person near conveyor / unguarded pulley | 5 | 4 | M | L | M | 4 | 3 | CV+INT |
| N3 | Crusher/loading point exclusion zone | 5 | 4 | H | M | L | 4 | 3 | CV |
| N4 | Fall of ground (underground) | 5 | 3 | — | — | — | 5 | — | SEN (geotech) |
| N5 | Edge/berm proximity at dumps | 5 | 3 | L | L | H | 4 | 2 | SEN (GNSS) |
| N6 | Missing PPE at plant/workshop | 3 | 5 | M (dust, lighting) | M | M | 3 | 2 | CV |
| N7 | Unaccounted-for personnel at muster | 5 | 1 | M (counting) | M | M | 5 | 3 | INT (tags) + CV |
| N8 | Dust/visibility degradation | 3 | 4 | M (image quality signal) | — | L | 3 | 2 | SEN+CV |
| N9 | Unauthorised entry to blast zone | 5 | 1 | M | L | M | 5 | 3 | CV+INT |
| N10 | Workshop vehicle–pedestrian | 4 | 4 | H | M | M | 4 | 3 | CV |

### 2.6 Power and electrical utilities

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| E1 | Approach inside energised-equipment boundary (substation) | 5 | 3 | H (zone) | M | M | 5 | 4 | CV+INT (switching state) |
| E2 | Unauthorised substation intrusion | 5 | 2 | H | M | L | 4 | 3 | CV |
| E3 | Arc-flash PPE missing during switching | 5 | 2 | L | L | H | 4 | 2 | HUM |
| E4 | Boom/crane near overhead lines | 5 | 2 | L | L | H | 4 | 3 | SEN+CV |
| E5 | Fall from structure/bucket | 5 | 3 | L (no fixed cameras in field) | L | H | 3 | 1 | HUM |
| E6 | Vehicle–pedestrian at generation plant | 4 | 3 | H | M | M | 3 | 3 | CV |
| E7 | Fire/smoke in cable galleries/transformer bays | 5 | 1 | M | M | M | 3 | 2 | CV/TH supplemental |
| E8 | Hot-surface/steam areas entry (generation) | 4 | 3 | H (zone) | M | L | 3 | 3 | CV+TH |
| E9 | Missing hard hat/hi-vis in plant | 3 | 4 | H | M | L | 3 | 2 | CV |
| E10 | Lone worker immobility in plant | 4 | 2 | M | M | M | 4 | 3 | CV+wearables |

### 2.7 Ports and material handling

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| P1 | Person under suspended container/load | 5 | 4 | M | L | M | 5 | 4 | CV+INT (crane PLC) |
| P2 | Pedestrian struck by handling equipment | 5 | 5 | H | M | M | 5 | 4 | CV |
| P3 | Person in automated/vehicle-only area | 5 | 3 | H | M | L | 5 | 4 | CV+INT (access) |
| P4 | Crush between containers/stacks | 5 | 3 | L | L | H | 4 | 2 | CV+HUM |
| P5 | Missing hi-vis | 3 | 5 | H | M | L | 3 | 2 | CV |
| P6 | Fall from quay edge / vessel | 5 | 3 | M (edge zone) | L | M | 4 | 3 | CV |
| P7 | Lashing/twist-lock area entry during operations | 5 | 3 | M | L | M | 4 | 3 | CV+INT |
| P8 | Gate congestion and turning conflicts | 4 | 4 | H | M | M | 4 | 3 | CV |
| P9 | Confined space (holds) | 5 | 2 | L | L | H | 3 | 2 | SEN+HUM |
| P10 | Night/rain visibility degradation | 3 | 4 | M (quality signal) | — | L | 3 | 2 | CV |

### 2.8 Chemical and pharmaceutical

| # | Hazard | Sev | Exp | CV | Data | Diff | Use | RR | Mode |
|---|---|---|---|---|---|---|---|---|---|
| H1 | Process safety event (loss of containment) | 5 | 1 | — (before ignition) | — | — | 5 | — | SEN/INT (DCS, SIS) |
| H2 | Confined-space entry without attendant/permit | 5 | 2 | M | L | M | 5 | 3 | CV+INT |
| H3 | Face shield/goggles missing at charging/sampling | 4 | 4 | M | L | M | 4 | 3 | CV |
| H4 | Chemical suit / respirator area compliance | 4 | 3 | M (suit) / L (fit) | L | M | 3 | 2 | CV+HUM |
| H5 | Visible spill on floor | 4 | 3 | L–M | L | H | 3 | 2 | CV+TH |
| H6 | Blocked eyewash/safety shower/exit | 4 | 3 | M | L | M | 4 | 3 | CV |
| H7 | Hot work without permit | 5 | 2 | M | L | M | 4 | 3 | CV+INT |
| H8 | In-plant vehicle–pedestrian | 4 | 3 | H | M | M | 3 | 3 | CV |
| H9 | Manual handling (drums, bags) | 3 | 4 | M | M | M | 3 | 2 | CV |
| H10 | Person down in process area | 5 | 1 | M | M | M | 4 | 3 | CV+wearables |
| H11 | Cleanroom gowning compliance (pharma, quality more than safety) | 2 | 5 | M | L | M | 3 | 1 | CV |

## 3. Capability families: feasibility verdicts

Each verdict states the evidence a detection needs, how temporal analysis helps, where false positives are unacceptable, and a decision: **Build** (P1/P2), **Research** (P3), **Integrate** (use another system), or **Do not build**.

### A. PPE intelligence

| Item | Visual evidence needed | Verdict |
|---|---|---|
| Hard hat | Head visible at roughly 30 px or more; multi-frame vote | **Built** (M5). Extend with "worn vs. carried" (already handled by head-region association) |
| High-visibility vest/jacket | Torso visible; colour and retro-reflective bands; robust to lighting | **Build (P1)**: highest-value next PPE class for logistics and plant areas; large, visible, low ambiguity |
| Safety boots | Feet visible and large; often occluded | **Do not build** as an alerting feature; too unreliable at CCTV range |
| Gloves | Hands at close range | **Research** for specific stations only |
| Goggles / face shield / welding mask | Face at close range | **Build (P2)** for fixed stations (charging, grinding, welding bays) with close cameras; not site-wide |
| Respirator presence | Lower face visible | **P2** at stations; *fit and cartridge suitability cannot be judged* |
| Hearing protection | Ear muffs visible; ear plugs not | **Do not build** for plugs; muffs only as P3 |
| Harness | Straps on torso visible; *clipped-on status rarely visible* | **Research (P3)**; never claim "tied off" |

**Design rules that apply to all PPE** (analysis, drawing on the existing implementation):
- Association to a tracked worker, never per-frame object counts.
- Temporal vote with an explicit **UNOBSERVABLE/UNCERTAIN** state when the body part is not visible.
- PPE requirements are **per zone** (hi-vis in vehicle areas, face shields at charging stations), not global, which also fixes the "bare head in an office" false alarm.
- Report compliance as *observed compliant / observed non-compliant / not observable* fractions, never a single "compliance %" that hides the unobservable share.

**Universal or specialised models?** A single detector for a shared core (person, head, helmet, hi-vis, forklift and other vehicles) plus small station-specific models for close-range PPE. A universal "all PPE" model trades accuracy on the common classes for classes most sites never need, and makes validation harder. Open-vocabulary detectors are useful for *labelling assistance*, not for production alerting (`05` §2).

### B. Dangerous worker behaviour

| Item | Evidence and method | False-positive tolerance | Verdict |
|---|---|---|---|
| Fall (event) | Pose trajectory: rapid vertical drop + horizontal body + no recovery; temporal models | Low tolerance; staged-to-real gap is large (OmniFall reports over 40 % degradation for pretrained models on real accidents [P24]) | **P2** as "person down" (immobility after a fall-like event) with human confirmation |
| Prolonged immobility / person down | Track stationary, body horizontal, duration > threshold | Moderate; confirmation by operator | **P2** for lone-working areas |
| Running | Speed on calibrated ground plane | High tolerance needed (many false triggers) | **Do not build** as an alert; analytics only |
| Unsafe lifting / repetitive posture | 2D pose → RULA/REBA-like screening; total-score agreement moderate, body-part agreement poor in published studies [P37] | Not an alert; trend analytics only | **P2** as ergonomic *screening*, never individual scoring |
| Ladder misuse | Pose + ladder detection; ladder dataset scarce | Low | **P3** |
| Working at unprotected height | Requires knowing where the edge is (zone) + person + absence of guardrail | Low | **P2** via *edge zones* drawn by the site (feasible); **P3** for automatic edge detection |
| Fatigue, intoxication, illness | Not inferable from CCTV | — | **Do not build.** Also restricted under the EU AI Act where it shades into emotion inference (Art. 5(1)(f), safety exception narrow) [L02] |

### C. Machinery and equipment

| Item | Method | Verdict |
|---|---|---|
| Person in machine exclusion zone | Zone + tracking; **context: machine state from PLC/OPC UA** | **P1** (zone) + **P2** (state integration) |
| Robot-cell entry | Same; robot controller state | **P2**; never a safety function (ISO 10218-2:2025 governs cell safeguarding [L11]) |
| Conveyor reach-in | Pose (wrist keypoint) inside a pinch-point polygon while running | **P2** |
| Guard presence/absence | Fixed-view change detection or a small classifier per guard | **P3**; site-specific training |
| Person under suspended load | Detect load (hook/container) + project footprint to the ground plane; or crane PLC hook position | **P2** with crane data; **P3** vision-only |
| Equipment in pedestrian areas | Vehicle detection + typed zones | **P1** |

PLC/safety-system integration is required whenever the risk depends on whether energy is present. Vision can show *exposure*; only the control system knows *energy state*.

### D. Vehicle and pedestrian

| Item | Method | Verdict |
|---|---|---|
| Proximity (distance threshold) | Detect + track both; ground-plane homography; distance between footprints | **P1** |
| Closing speed and time-to-collision (TTC) | Kalman velocity on the ground plane; TTC = gap / closing speed, with uncertainty | **P1** — this is what separates a *near miss* from mere proximity |
| Post-encroachment time (PET) | Time between one road user leaving a conflict point and the other arriving; standard traffic-conflict measure [P45] | **P1** for intersections and crossings |
| Trajectory prediction | Constant-velocity baseline first; learned predictors (Trajectron++ [P20]) only if they beat the baseline on site data | **P3** |
| Speed estimation | Homography calibration; error grows with distance and mounting angle | **P2** with a stated error band |
| Reversing / blind spot | Vehicle heading from track history + pedestrian behind | **P2** |
| Congestion | Counts per zone over time | **P2** analytics |

**Proximity vs. predictive risk.** A distance alert fires every time a pedestrian walks past a parked forklift; a TTC/PET-based conflict fires only when two road users are on converging paths at speed. The second is what safety managers mean by a near miss, and it produces far fewer false alerts. Surrogate safety measures (TTC, PET) are established in road-traffic safety research [P45]; applying them to forklift–pedestrian conflicts with calibrated fixed cameras is a realistic and under-served capability (see `13_DIFFERENTIATION_AND_INNOVATION.md`).

### E. Environmental and workplace hazards

| Item | Verdict |
|---|---|
| Fire and smoke | **P2 supplemental only.** NFPA 72 requires video image smoke/flame detection systems to be *listed* for that purpose [L12]; an unlisted analytics product must never be presented as fire detection |
| Sparks / hot work | **P2** with permit integration (sparks visible; "permit valid" is not) |
| Spills and leaks | **P3.** RGB struggles; thermal helps until temperature equalises [P26]; synthetic data shows promise [P25] |
| Blocked exits / extinguishers / eyewash | **P1** for fixed views: "region must stay clear" zones with dwell time; simple, valuable, auditable (OSHA 1910.37 requires exit routes free of obstruction) |
| Housekeeping, unsafe stacking, rack damage | **P3** |
| Falling objects | **Do not build** (too rare and fast for CCTV frame rates to be reliable) |
| Visible structural damage | **Do not build** (inspection task) |
| Gas, oxygen, temperature | **Integrate** sensors; never infer from RGB |
| Confined-space entry/exit | **P2**: count entries/exits at a manway and display occupancy for the attendant; never replaces the attendant |

### F. Restricted-zone intelligence 2.0

Zone *kinds* each carry a default hazard, severity and rule (implemented as an optional `kind` field in this branch):

| Kind | Rule | Default hazard |
|---|---|---|
| `restricted` (default, current behaviour) | person entry | Restricted area entry |
| `machine_exclusion` | person entry; severity depends on machine state | Machine exclusion entry |
| `suspended_load` | person entry; severity depends on load present | Person under suspended load |
| `electrical` | person entry; approach boundary | Approach to energised equipment |
| `confined_space` | entry/exit counting, occupancy | Confined-space entry |
| `hot_work` | entry; requires permit context | Hot-work area entry |
| `vehicle_only` | pedestrian entry | Pedestrian in vehicle-only area |
| `pedestrian_only` | vehicle entry (needs vehicle detection) | Vehicle in pedestrian area |
| `excavation` / `edge` | person entry near edge | Fall/collapse exposure |
| `keep_clear` (emergency route, extinguisher, eyewash) | any static object dwell | Blocked emergency equipment |

**Temporary zones** need validity windows (start/end) and an owner; **dynamic zones** attach a polygon to a tracked object (a forklift's footprint plus a speed-dependent buffer) or to equipment telemetry (crane hook position). Dynamic zones are P2, typed and scheduled zones are P1.

### G. Emergency and incident intelligence

| Item | Verdict |
|---|---|
| Worker down | P2 (see B) |
| Abnormal crowd gathering | P2: counts per zone vs. baseline; often a sign of an incident |
| Emergency-route obstruction | P1 (see E) |
| Evacuation monitoring / headcount at muster | P2 with access-control integration; camera counts alone are not a roll call |
| Missing/unaccounted workers | Integrate access control/RTLS; cameras cannot prove absence |
| Evidence collection (pre/post clip, multiple cameras) | **P1**: evidence quality is the product's credibility |
| Timeline reconstruction | P1 (single camera), P2 (cross-camera) |
| Automated report drafts | P2, human-approved |
| Near-miss detection | P1 for vehicle–pedestrian (TTC/PET) |
| Trend analysis and recurring patterns | P1 analytics on the event store |
| Escalation workflows | P1 (risk-level based) |

## 4. Mapping to the implemented taxonomy

The hazards above are encoded in `intelligence/taxonomy.py` with stable codes. The two incident types the current pipeline raises map as follows:

| Pipeline type | Taxonomy code | Note |
|---|---|---|
| `NO_HELMET` | `PPE.HEAD.MISSING` | unchanged behaviour |
| `ZONE_INTRUSION` | `ZONE.ENTRY` (+ zone `kind` refines severity) | `restricted` kind keeps today's semantics |
