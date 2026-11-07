# 13 — Differentiation and innovation

Date: 5 November 2026. Each opportunity is classified as **Novel** (no public evidence that competitors do it), **Differentiated** (competitors do something similar; SafeSight's version is materially different), or **Parity** (competitors already provide it; needed to compete, not to win). Competitor evidence is in `04`. All assessments are **(analysis)**.

## 1. Summary

| # | Opportunity | Class | Primary user | Feasibility | Cost | Validation difficulty | Priority |
|---|---|---|---|---|---|---|---|
| 1 | Per-camera **validated performance passport** | Novel | EHS manager, insurer, auditor | High | Low | Medium | P1 |
| 2 | **Energy-based exposure index** (HECA-aligned) | Novel | EHS manager, safety leadership | High | Low–Med | Medium | P1 |
| 3 | **Ground-plane TTC/PET near-miss analytics** with uncertainty | Differentiated | Safety officer, logistics manager | Medium | Medium | Medium–High | P1 |
| 4 | **Machine-state-aware zones** via OPC UA/MQTT | Differentiated | Manufacturing EHS, maintenance | Medium | Medium | Medium | P1/P2 |
| 5 | **Policy-as-configuration with competent-person approval** and golden tests | Novel | Safety officer, EHS manager | High | Low | Low | P0 (built) |
| 6 | **Uncertainty-native reporting** (observed / not observable / degraded) | Novel (positioning) | Everyone | High | Low | Low | P0–P1 |
| 7 | **Conformal per-camera alert calibration** with stated false-alarm bounds | Novel (research) | Integrator, EHS | Medium | Low | Medium | P2 |
| 8 | **Layout what-if replay**: test a proposed barrier/crossing against recorded trajectories | Novel | Plant/logistics manager | Medium | Medium | Medium | P2 |
| 9 | **Operator-feedback data engine and drift alarms** | Parity (likely, not public) | Admin, ML engineer | High | Low | Low | P1 |
| 10 | **Privacy-by-default evidence** (redacted frames, skeleton/box-only storage, worker transparency page) | Differentiated (Intenseye has masking) | Works council, DPO, workers | High | Medium | Low | P1 |
| 11 | **Offline edge appliance** with store-and-forward and local alerting | Differentiated | Sites with poor connectivity or no-cloud policy | High | Medium | Low | P0–P1 |
| 12 | **Evidence-linked shift handover brief** (AI draft, human approved) | Parity (Voxel Risk Insights, Intenseye assistant) | Supervisor | High | Low | Medium (hallucination) | P2 |
| 13 | **Natural-language policy authoring** compiled to validated policy JSON | Novel | Safety officer | Medium | Low | Medium | P2 |
| 14 | **Dynamic exclusion zones** bound to tracked vehicles (speed-dependent buffer) from site cameras | Differentiated (on-vehicle systems exist) | Logistics/ports | Medium | Medium | Medium | P2 |
| 15 | **Permit-aware monitoring** (hot work, confined space, maintenance) | Differentiated | Process industries | Medium | Medium (integration) | Medium | P2 |
| 16 | **Confined-space occupancy board** for attendants | Parity (viAct lists confined-space monitoring) | Attendant | High | Low | Medium | P2 |
| 17 | **Open event-level benchmark format** for industrial safety analytics | Novel | Research community, buyers | High | Low | Low | P1 |
| 18 | **Site-specific hazard learning** (open-vocabulary proposals + operator labels → small site detector) | Differentiated (custom rules exist) | Integrator | Medium | Medium | High | P3 |

## 2. Opportunity details

### 1. Validated performance passport (Novel)
- **Problem:** buyers cannot verify vendor outcome claims; insurers and auditors cannot rely on them (`04` §5).
- **What:** for each camera and hazard, a dated document with event recall (with interval), false alarms per camera-hour, latency, slices, known blind spots, and re-validation triggers (`09` §6). Generated from the event-metrics tooling built in this branch.
- **Value:** trust, faster procurement in regulated buyers, possible insurance relevance.
- **Data:** labelled episodes per camera (customer-owned).
- **Safety implication:** strongly positive; makes limitations explicit.
- **Advantage:** hard to copy for vendors whose business depends on breadth claims.

### 2. Energy-based exposure index (Novel)
- **Problem:** leaders running SIF programmes need leading indicators of high-energy exposure, not PPE counts [S17], [S18].
- **What:** for each area and shift: number and minutes of observed high-energy exposures (vehicle conflict, machine zone, suspended load, edge), and the share where a direct control was observed (barrier present, gate closed, machine locked out per PLC). The taxonomy built here already records each hazard's energy source.
- **Feasibility:** exposure counting is feasible now; "direct control present" needs per-site configuration or context signals.
- **Validation:** compare with manual HECA observations on the same shifts.
- **Safety implication:** aligns the product with modern SIF practice; avoids blame on individuals.

### 3. Ground-plane TTC/PET near misses (Differentiated)
- **Problem:** proximity alerts fire on every pass of a parked forklift; managers want genuine conflicts.
- **What:** homography calibration, tracked footprints, closing speed, TTC and PET with error bands; conflict events only when paths converge [P45].
- **Novelty:** competitors advertise "near-miss" detection; none publicly document the measure, thresholds or error.
- **Validation difficulty:** needs labelled conflict episodes; calibration error must be measured per camera.

### 4. Machine-state-aware zones (Differentiated)
- **Problem:** video cannot tell a running cell from a locked-out one, so severity is guessed.
- **What:** OPC UA/MQTT signals as context; "unknown never lowers risk"; reductions only for known safe states allowed by an approved policy. The risk engine in this branch already implements the rule.
- **Safety implication:** must be read-only; never write to PLCs.

### 5. Policy-as-configuration with approval (Novel; built)
- **Problem:** configurable rules exist in competitor products, but who approved them and when is not documented; a rule change can silently hide hazards.
- **What:** JSON policies with version, status (`draft`/`approved`), approver and date, schema validation, and golden assessment tests; every assessment stores the policy version and status.

### 6. Uncertainty-native reporting (Novel positioning)
- **What:** PPE compliance as observed-compliant / observed-non-compliant / not-observable; camera "monitoring degraded" states; evidence quality on every event. Extends the existing UNCERTAIN design.
- **Value:** credibility with safety professionals; resistance to "the dashboard said 98 %" complacency.

### 7. Conformal per-camera calibration (Novel, research)
- **What:** use conformal risk control [P46] on operator-reviewed alerts to choose per-camera thresholds with a finite-sample bound on expected false alarms, under an exchangeability assumption that is stated and monitored.
- **Risk:** guarantees break under drift; must be paired with drift alarms (#9).

### 8. Layout what-if replay (Novel)
- **Problem:** a manager deciding where to put a barrier or a crossing has no data.
- **What:** replay weeks of recorded (anonymous) trajectories against a proposed layout to estimate how many conflicts would have been prevented or displaced.
- **Caveat:** behaviour changes after a layout change; present as an estimate with that caveat.

### 9. Operator feedback and drift (Parity)
Every review becomes a label; per-camera false-alarm rate tracked weekly; alarms on doubling. Expected by sophisticated buyers.

### 10. Privacy-by-default evidence (Differentiated)
Redacted keyframes by default, boxes and skeletons stored instead of frames for low-risk events, short retention, and a worker-facing page explaining what is monitored. Intenseye's masking sets the bar [C01]; SafeSight adds open, inspectable code.

### 11. Offline edge appliance (Differentiated)
All detection, risk and local alerting on site; store-and-forward to a central server; works for 72 h+ without WAN. The current single-workstation design is already offline.

### 12. Shift handover brief (Parity)
Evidence-linked summaries drafted by a local VLM/LLM and approved by the supervisor. Every sentence links to an event; no free-text claims without a source.

### 13. Natural-language policy authoring (Novel)
A safety officer writes "Nobody in the press cell while it runs; tell the shift lead at once." The assistant drafts policy JSON, generates golden test cases, and shows a diff; a competent person approves. The engine never runs an unapproved policy silently.

### 14. Dynamic vehicle exclusion zones (Differentiated)
Polygon around each tracked forklift whose size grows with its speed; pedestrian entry produces a conflict event. Complements on-vehicle systems [C08] with site-level analytics and evidence.

### 15. Permit-aware monitoring (Differentiated)
Integrate permit-to-work status so a hot-work or confined-space zone is "authorised" during a valid permit, and activity without a permit is flagged. Requires customer permit-system APIs.

### 16. Confined-space occupancy board (Parity)
Entry/exit counting at a manway, displayed for the attendant; never replaces the attendant or gas testing.

### 17. Open event-level benchmark format (Novel)
Publish the episode ground-truth format and metric code (built here) so that buyers and researchers can compare systems on their own footage. Positions SafeSight as the honest reference.

### 18. Site-specific hazard learning (Differentiated, research)
Open-vocabulary detectors propose candidates, operators confirm, a small site-specific detector is trained and validated through the passport process. High validation burden; P3.

## 3. What competitors already do that SafeSight should not try to out-build

Catalogue breadth (50+ detections), generic dashboards, LLM chat assistants, and cloud onboarding speed. SafeSight should match only what the wedge needs and compete on **measured reliability, energy-based risk context, openness, and on-site privacy**.
