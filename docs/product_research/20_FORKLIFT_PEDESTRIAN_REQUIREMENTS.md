# 20 — Forklift–pedestrian risk intelligence: research and data requirements

Prepared 5 November 2026 during milestone M2.1. **Not started, and gated**: no detector, model or rule for this
capability exists or is being built. This document defines what must be true before work begins, and what data and
evaluation it would need. SafeSight remains an additional, advisory monitoring layer: it does not control vehicles or
machinery, and it does not claim to prevent accidents.

## 1. Gate to begin (all required)

| # | Condition | Where it stands |
|---|---|---|
| G1 | Existing helmet and zone functions re-scored against independently verified labels, with the corrected framework (`19`) | Blocked: human review prepared (M3 packages `reviewer_1`, `reviewer_2`), not done |
| G2 | A deployment-like evaluation set with fixed cameras at several sites (`18` §10 P0.4) | Not started |
| G3 | View-integrity detection (camera moved, blocked or re-aimed), because conflicts need a stable geometry | Built and tested on simulated movements (`21`); physical validation not run (`23A`) — updated 6 November 2026 (M3) |
| G4 | Ground-plane calibration per camera, with reprojection error ≤ 0.3 m in the calibrated area (target from `12`) | Not started |
| G5 | A licensing decision for a commercial detector line; no non-commercial training data (M5 is research-only) | Open |
| G6 | A site safety lead defines the site's traffic rules: vehicle-only aisles, pedestrian walkways, crossing points, speed limits | Needs a partner site |

## 2. What would be detected (definitions to agree with the site)

| Event | Definition (ground plane, metres and seconds) | Taxonomy |
|---|---|---|
| Pedestrian in a vehicle-only aisle | Pedestrian foot point inside a `vehicle_only` zone (debounced, as for zones today) | `VEH.PED_ZONE.ENTRY`: built (raised when a person enters a `vehicle_only` zone), never evaluated |
| Vehicle in a pedestrian-only walkway | Vehicle footprint intersects a `pedestrian_only` zone | to add |
| Close approach | Separation between pedestrian and vehicle footprint below a site-set distance while the vehicle moves | `VEH.PED.CONFLICT` (planned) |
| Imminent conflict | Time to collision below a site-set threshold, from relative positions and velocities | `VEH.PED.CONFLICT` |
| Near miss (after the fact) | Post-encroachment time below a threshold at a crossing point | analytic, not an alert |

Every alert needs the same lifecycle as M2.1:
- one incident per pedestrian–vehicle pair and episode;
- exposure bounded by observation;
- the outcome recorded as unknown when observation is lost;
- bursts batched into one notification;
- identity camera-scoped only, with no cross-camera identity unless a safety need and a privacy assessment justify it.

## 3. Data requirements (planning estimates, to be refined)

| Need | Minimum to start a credible evaluation | Why |
|---|---|---|
| Sites | ≥ 10 independent sites, or areas with different layouts | Clustering: M2's held-out results came from one source group |
| Cameras | Fixed, high-mounted, overlooking aisles and crossings; the deployment resolution and frame rate | Edited or handheld footage breaks geometry and tracking |
| Hours | ≥ 50 monitorable camera-hours across shifts, lighting and traffic densities | False alarms per camera-hour need tens of events for a ±25 % interval |
| Conflict episodes | ≥ 60 labelled conflict episodes per main stratum (vehicle type × layout), so several hundred in total | About 60 events give a ±10-point interval at a recall near 0.8, before clustering |
| Vehicle types | Counterbalance forklifts, reach trucks, pallet trucks (manual and powered), tuggers | Different shapes, speeds and blind spots |
| Ground truth | Per-frame boxes for vehicles and pedestrians on sampled frames; ground-plane positions from calibration; conflict episodes with start, end, minimum separation and identity anchors for both parties | Distances and time to collision cannot be judged from image boxes alone |
| Independent review | Two annotators with adjudication, as in `reports/validation/human_review/`; agreement on distances measured in metres | Same standard as PPE |
| Consent and privacy | DPIA, a worker information notice, retention limits, no face recognition, and evidence redaction before frames leave the site | `10` |
| Licences | Commercially usable training data only. The candidate public sources (logistics-object and forklift datasets, Open Images classes) are listed with licences in `06`; each must be checked before use | M5's licence problem must not repeat |

## 4. Evaluation design

- **Event-level, identity-aware matching**: the M2.1 matcher, extended to pairs. A match needs the right pedestrian and the right vehicle.
- **Distance and time-to-collision accuracy** against calibrated ground truth: median and 90th-percentile error in metres and seconds, broken down by distance from the camera.
- **False alarms per monitorable camera-hour**, by traffic density and lighting; **duplicate rate** and **notifications per hour** as operator-burden measures.
- **Latency** from conflict onset to alert, with its distribution. An advisory alert that arrives after the conflict has passed is counted as late, not as found.
- **Development, held-out and site splits** fixed before labelling. Thresholds are tuned only on development sites.
- **Shadow mode first.** Alerts are recorded but not delivered, with weekly review, before any live notification (`12` M4).

## 5. Risks to manage

- **Geometry.** Calibration drift and camera knocks make distances wrong without anyone noticing (G3, G4).
- **Occlusion.** Racking and loads hide pedestrians exactly where conflicts happen. Coverage maps must show unobservable areas, as the PPE categories do.
- **Alarm fatigue.** Busy aisles produce constant close approaches. The site's rules, not the model, must decide what is a conflict.
- **Liability.** An advisory system must never be presented as a collision-avoidance system, and must not delay or replace engineered controls (barriers, speed limits, vehicle proximity systems).

## 6. What is explicitly not done

No forklift or pallet-truck detector, no vehicle class training, no calibration code and no conflict rules were
written in M2.1. `VEH.PED.CONFLICT` remains marked planned; `VEH.PED_ZONE.ENTRY` works only as a zone rule (any person
in a `vehicle_only` zone) and has no evaluation behind it.
