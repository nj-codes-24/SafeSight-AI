# 02 — Industry research

Research date: 5 November 2026. Source IDs in square brackets (for example [S01]) resolve in `14_SOURCE_REGISTER.md`. Statements marked **(analysis)** are this document's own reasoning, not sourced facts.

## 1. The cross-industry picture

### 1.1 What actually kills and maims workers

| Indicator | Figure | Source |
|---|---|---|
| US fatal work injuries, 2024 | 5,070 (3.3 per 100,000 FTE), down 4.0 % from 2023 | BLS CFOI, released 19 Feb 2026 [S01] |
| US: transportation incidents | 1,937 deaths, 38.2 % of all fatal work injuries (2024) | [S01] |
| US: falls, slips and trips | 844 deaths (2024); construction and extraction workers 370, down from 400 | [S01] |
| US: exposure to harmful substances or environments | 687 deaths (2024) | [S01] |
| US: struck by propelled, falling or suspended object | 357 (2024), 394 (2023), per BLS Table 2 (column order to be re-checked against the full table) | [S02] |
| US: transportation and material moving occupations | 1,391 deaths (2024), down 7.0 % | [S01] |
| Great Britain, workers killed 2024/25 (provisional) | 124; falls from height 35; struck by moving object 18; trapped by collapse/overturn 17; struck by moving vehicle 14 | HSE [S03] |
| US mining, 2025 (unofficial year-end) | 33 deaths; powered haulage 13 (39 %), machinery 6 | MSHA / Pit & Quarry [S05] |
| US forklifts | 75–94 deaths per year 2011–2017 (BLS); pedestrians struck about 12–20 % of fatal forklift cases depending on year and source | [S06], [S19] |
| US oil and gas extraction | motor-vehicle crashes are more than 40 % of deaths; 470 deaths 2014–2019 in the NIOSH FOG database, about three-quarters contractors | NIOSH [S07] |
| Ports (global, ICHCA dataset of about 500 shore-worker incidents over about 25 years) | crush by cargo is the leading cause (over a quarter); pedestrians struck by vehicles, mostly handling equipment, a close second; falls third | ICHCA [S11] |
| US OSHA most-cited standards, FY2026 (preliminary, to 31 Aug 2026) | 1 fall protection (1926.501), 2 hazard communication, 3 lockout/tagout (1910.147), 4 scaffolding, 5 ladders, 6 respiratory protection, 7 powered industrial trucks (1910.178), 8 fall-protection training, 9 eye and face protection (1926.102), 10 machine guarding (1910.212) | OSHA [S04] |

**(analysis)** Three energy sources dominate serious harm across every industry studied: **gravity** (falls of people and of objects), **motion** (vehicles and mobile plant striking people) and **mechanical energy** (machinery: caught-in, crush, amputation). Electrical, thermal/chemical and pressure energy matter enormously in specific industries (utilities, oil and gas, chemicals) but are less camera-observable. This is the single most important input to product strategy: the hazards that kill most often are interactions between people and moving energy, and those interactions are often visible.

### 1.2 Why "SIF prevention" rather than "violation counting"

Industrial safety practice has moved from counting recordable injuries towards preventing **serious injuries and fatalities (SIF)**. The energy-based approach developed by the Construction Safety Research Alliance and standardised by the Edison Electric Institute measures the share of observed **high-energy hazards that have a direct control in place** (the High-Energy Control Assessment, HECA) [S17], [S18]. A "direct control" is a physical barrier or engineering measure that is effective even when people make mistakes; PPE and procedures are not direct controls in that framework.

**(analysis)** This framing matters for SafeSight in two ways:

1. A product that only counts PPE violations measures the weakest layer of control. Safety leaders who follow SIF thinking will value a system that shows *exposure to high energy without a direct control* (a person under a suspended load, a pedestrian in a forklift aisle with no barrier, a person inside a robot cell) far more than a hard-hat count.
2. Cameras can observe some of the HECA inputs at scale: the presence of people near a high-energy source and the presence or absence of some physical controls (barriers, guarding, cones, a closed gate). That is a credible and differentiated role for computer vision.

### 1.3 What cameras can and cannot establish (applies to every industry)

| Cameras can reasonably establish | Cameras cannot reliably establish |
|---|---|
| A person is present in a defined area, and for how long | Whether energy is isolated (LOTO), a line is de-energised, or a machine is truly stopped |
| Relative position and motion of people and vehicles/mobile plant on a calibrated ground plane | Gas concentration, oxygen deficiency, toxic exposure, noise dose, heat stress |
| Visible PPE items on visible body parts, when the image is large enough | That PPE is correctly rated (arc rating, respirator fit, harness inspection status) |
| Visible smoke, flame, large spills and obstructions in fixed views | That an environment is "safe"; absence of a detection is not evidence of safety |
| A person on the ground and not moving for a period | Medical state, intoxication, fatigue, intent |
| Presence or absence of large physical controls in a fixed view (barrier, open gate, guard panel) | Whether a permit is valid or a worker is competent or authorised (needs integration) |

## 2. Industry profiles

Each profile follows the same structure. Tables of the top hazards per industry, scored on severity, exposure, detectability and the other required dimensions, are in `03_HAZARD_AND_FEATURE_CATALOG.md`.

### 2.1 Construction and infrastructure

**How it operates.** Temporary, changing sites; a principal contractor with many subcontractors; work fronts move daily; heavy mobile plant (excavators, dumpers, telehandlers, cranes); work at height on scaffolds, ladders, roofs and MEWPs; outdoor lighting and weather; connectivity often poor; cameras typically few, wide-angle and moved as the job progresses.

**Workers and movement.** Trades work in small crews, often in the same area as plant; frequent climbing; materials lifted overhead; traffic management with banksmen.

**Principal hazards and causes.** OSHA's "Focus Four" (falls, struck-by, caught-in/between, electrocution) account for the majority of construction deaths; falls are the largest share (about 37 % in 2022–2023 per secondary summaries of BLS data) [S15]. In Great Britain over half of construction deaths in the last five years were falls [S03]. Fall protection (1926.501), scaffolding, ladders and fall-protection training are four of OSHA's ten most-cited standards [S04].

**Existing procedures and PPE.** Fall-protection plans, permits for excavation and lifting, toolbox talks, daily inspections, exclusion zones around plant and lifts. PPE: head protection (OSHA's 2023/2024 bulletin recommends considering Type II helmets with chin straps where impact and fall hazards are high; it is guidance, not a new mandate [S16]), high-visibility clothing (ANSI/ISEA 107), safety footwear, eye protection, harnesses.

**Safety officer responsibilities.** Site inductions, permit control, inspections of scaffolds and excavations, incident investigation, subcontractor oversight, reporting to the client.

**Where supervision fails.** Large, changing areas; supervisors spread across many work fronts; exposure is short and intermittent (a worker briefly unclipped at an edge); subcontractor turnover.

**What cameras can do.** PPE on near/mid-field workers; people inside plant swing radius or under a suspended load (with calibrated zones); people in excavation exclusion zones; vehicle–pedestrian conflicts at gates and haul roads; missing edge protection in fixed views (research). **What needs sensors or integration:** plant proximity (tags/radar on machines), crane load and slew data, permit status. **What needs human inspection:** scaffold adequacy, excavation support, harness anchorage quality.

**Expensive or hard problems for management.** Fall exposure that is intermittent and out of sight; plant–pedestrian interaction; proving due diligence across subcontractors.

**(analysis) Fit for SafeSight now:** the current model was trained for this domain, but construction is the hardest place to make camera analytics reliable: distant workers (the model's known failure), moving cameras, weather, and short project lifetimes for each installation. Good second market, not the wedge.

### 2.2 Manufacturing and factory operations

**How it operates.** Fixed layouts, production lines, machine cells, in-plant logistics with forklifts and tuggers, shift patterns, mostly indoor and controlled lighting; many plants already have CCTV.

**Principal hazards.** Caught-in/amputation at machinery (machinery was involved in 58 % of work-related amputations in 2018 per BLS [S10]); powered industrial trucks; falls on the same level; manual handling and repetitive strain; hazardous energy during maintenance. Lockout/tagout (1910.147) is OSHA's 3rd and machine guarding (1910.212) its 10th most-cited standard (FY2026 preliminary) [S04]. OSHA renewed its National Emphasis Program on amputations in manufacturing in June 2025 for five years [S09].

**Procedures and controls.** Machine guarding, interlocked doors, light curtains and safety laser scanners (certified safety functions under ISO 13849 / IEC 62061), LOTO procedures, area marking, PPE (eye, hearing, gloves, safety footwear, hi-vis in logistics areas).

**Where supervision fails.** Bypassed guards and interlocks during jams and changeovers; LOTO steps skipped under time pressure; pedestrians cutting through forklift aisles; ergonomics risk accumulating invisibly.

**What cameras can do.** Person present inside a defined machine-cell or robot-cell exclusion zone *combined with machine state from the PLC* (vision alone cannot know whether the cell is live); forklift–pedestrian interactions; guard panel open in a fixed view (research); visible ergonomic posture risk (screening only). **What must stay with certified safety systems:** stopping the machine. SafeSight is an observer, never a safety function (`10_PRIVACY_SECURITY_AND_COMPLIANCE.md` §2).

**(analysis) Fit:** strong. Fixed cameras, controlled lighting, repeated layouts, and machine-state integration (OPC UA) adds context competitors that rely on video alone lack.

### 2.3 Warehousing and logistics

**How it operates.** Racked aisles, docks, cross-docking, high vehicle density (counterbalance and reach trucks, pallet jacks, tuggers, AMRs), peak seasons with temporary labour, mostly indoor, CCTV usually present for security.

**Principal hazards.** Forklift–pedestrian collisions, forklift tip-overs, falls from docks, struck by falling loads from racking, manual handling, heat. OSHA launched a National Emphasis Program on warehousing and distribution centres (CPL 03-00-026, July 2023, three years) focused on powered industrial vehicles, material handling and storage, walking-working surfaces, means of egress and fire protection, plus heat and ergonomics [S08]. Powered industrial trucks (1910.178) are 7th in OSHA's FY2026 preliminary list [S04]. In Great Britain the share of deaths from being struck by a moving vehicle is much higher in transport and storage than the all-industry 15 % [S03].

**Procedures and controls.** Segregated walkways and barriers, speed limits, horn and blue-light policies, operator training and certification (1910.178(l)), pedestrian crossings, dock locks, rack inspections, exit routes kept clear (1910.37).

**Where supervision fails.** Near misses are rarely reported; pedestrians and drivers adapt to "normal" close calls; exit obstruction is transient; temporary staff unfamiliar with routes.

**What cameras can do.** Detect forklifts and pedestrians, measure separation and closing speed on a calibrated floor plane, flag pedestrians in vehicle-only aisles and vehicles in pedestrian-only walkways, count near misses objectively, detect blocked exits and extinguishers in fixed views, detect hi-vis compliance. **Sensors/integration:** on-truck proximity systems (UWB tags, cameras, radar) act in the cab in real time; SafeSight complements them with site-level analytics and evidence. Vendor comparisons describe the technologies as complementary: UWB sees through racks, cameras recognise people and context [C08].

**(analysis) Fit:** strongest. Fixed indoor cameras, a high-severity hazard (vehicle strikes) that is visible, objective near-miss measurement that safety managers cannot get today, and a commercially usable logistics dataset exists (LOCO [D11]). It is also crowded (Voxel, Protex, Spot AI target it), so the wedge must win on reliability and evidence, not catalogue size.

### 2.4 Oil, gas and petrochemical facilities

**How it operates.** Upstream (drilling, well servicing, remote pads), midstream (pipelines, compression), downstream (refineries, petrochemicals). Hazardous-area classifications constrain electrical equipment (ATEX/IECEx certification for cameras), large outdoor footprints, contractors dominate exposure.

**Principal hazards.** Vehicle crashes (over 40 % of extraction deaths [S07]), struck-by and caught-in on rigs, fires and explosions, toxic gas (H₂S), falls, confined spaces, hot work (CSB counted more than 60 hot-work deaths on tanks in the US since 1990 and issued seven key lessons including atmosphere monitoring and permits [S13]).

**Procedures.** Permit-to-work, gas testing, hot-work permits, process safety management (OSHA 1910.119), H₂S monitors, emergency shutdown systems.

**What cameras can do.** People in restricted areas near rotating equipment or under loads on rig floors; PPE (flame-resistant clothing hard to verify visually); visible flame/smoke as a supplemental indicator; visible large spills; hot-work activity visible in an area without an active permit (with permit integration). **What cannot be done with RGB:** gas detection, H₂S, oxygen deficiency. Optical gas imaging cameras exist for some hydrocarbons but are specialist instruments, not CCTV analytics. **Constraint:** camera hardware in hazardous areas must be certified; this is a deployment cost, not a software problem.

**(analysis) Fit:** later. High value, but hazardous-area hardware, remote connectivity and permit-system integration make it an expansion market.

### 2.5 Mining and heavy machinery

**How it operates.** Surface (haul roads, pits, crushers, conveyors) and underground (confined, dark, dusty). Very large mobile equipment with huge blind spots. Shift and contractor patterns; remote locations.

**Principal hazards.** Powered haulage is the leading cause of US mining deaths (13 of 33 in 2025, unofficial) [S05]; machinery; falls of ground; conveyors; electrical. MSHA's rule requiring written safety programmes for surface mobile equipment took effect in January 2024 [S14]; underground continuous miners already require proximity detection systems.

**What cameras can do.** Vehicle–vehicle and vehicle–pedestrian interactions at fixed points (crushers, workshops, loading points), conveyor-guard area entry, headcount at muster points. **What needs other technology:** collision avoidance on vehicles (radar, GNSS, V2V), underground positioning, dust-penetrating sensing, gas monitoring.

**(analysis) Fit:** later, and mostly as fixed-point analytics; the core collision-avoidance market is on-vehicle and dominated by OEM-integrated systems.

### 2.6 Power plants and electrical utilities

**How it operates.** Generation plants (fixed, process-like), substations (fenced, remote, often unmanned), transmission and distribution field crews (mobile, no fixed cameras).

**Principal hazards.** Electrical contact and arc flash, falls from structures and bucket trucks, struck-by, vehicle incidents. OSHA 1910.269 sets minimum approach distances and arc-flash protection [S12]; NFPA 70E governs electrical safe work practice. The utility industry (EEI) is the origin of the HECA approach [S17].

**What cameras can do.** Substation intrusion and unauthorised approach to energised equipment (fixed cameras, defined approach boundaries as zones); vehicle and boom proximity to overhead lines from fixed views (research, depth-sensitive); PPE presence (not arc rating). **What cannot be done:** verification of de-energisation; field crew monitoring without fixed cameras.

**(analysis) Fit:** substations and generation plants map well onto zone intelligence; field work does not.

### 2.7 Ports, shipping and material handling

**How it operates.** Quays with ship-to-shore cranes, yards with straddle carriers, reach stackers and terminal tractors, lashing on vessels, increasingly automated terminals with segregated areas.

**Principal hazards.** Crush by cargo (leading cause), pedestrians struck by handling equipment (close second), falls, confined spaces [S11].

**What cameras can do.** People in automated or vehicle-only areas; people under suspended containers in fixed quay views; hi-vis compliance; vehicle–pedestrian conflicts at gates. Port areas already have dense CCTV and strict area segregation, which helps.

**(analysis) Fit:** good expansion target after logistics, sharing the vehicle–pedestrian and zone capabilities.

### 2.8 Chemical and pharmaceutical manufacturing

**How it operates.** Batch and continuous processes, cleanrooms (pharma), hazardous materials, process safety management, high regulatory oversight (GMP in pharma).

**Principal hazards.** Fires and explosions, toxic releases, confined-space entry, hot work, chemical splashes, manual handling, in-plant vehicles. Process safety events are rare but catastrophic and are not detectable from CCTV before they develop.

**What cameras can do.** Confined-space entry/exit counting at a manway (attendant support, never a replacement), PPE in defined areas (face shields, goggles, chemical suits are visually distinct), visible spills (research: RGB struggles to separate liquid from floor; thermal helps but loses contrast when the spill reaches floor temperature [P26]), blocked eyewash/safety showers and exits. **What needs sensors:** gas detection, process conditions, permits.

**(analysis) Fit:** selective modules (confined-space entry logging, PPE by area, egress) inside the manufacturing package.

## 3. Cross-industry conclusions

1. **Common core.** Every industry needs: person detection and tracking, typed zones with schedules, vehicle/mobile plant detection, PPE by area, incident workflow with evidence, and a risk model that knows which energy source is involved.
2. **Industry specifics are mostly configuration plus a few dedicated models.** The differences are in which zones and objects matter (racks and docks vs. excavations and cranes vs. machine cells) and in the integrations (PLC state, crane data, permits), not in a different product.
3. **Fixed indoor environments are where camera analytics is most reliable.** That is logistics and manufacturing, then ports and plants; construction and mining are harder.
4. **Gas, energy isolation, competence and permits are not camera problems.** They are integration problems, and SafeSight should integrate rather than pretend.
5. **The biggest unmet need is measurement of exposure and near misses.** Management has injury data (lagging) and audit data (sparse); they lack continuous, objective data on how often people are exposed to high energy without a direct control.
