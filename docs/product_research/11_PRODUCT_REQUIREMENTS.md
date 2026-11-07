# 11 — Product requirements

Date: 5 November 2026. Scope: SafeSight Logistics/Manufacturing (the wedge, `00`) on the common core. Priority: **P0** foundation · **P1** first pilot · **P2** industry extension · **P3** research. Status: **Built** (this repository or this branch) · **Partial** · **Open**.

## 1. Users and their jobs

| Role | Primary job | What they must see | What they must do |
|---|---|---|---|
| **Site operator / control room** | Watch many cameras, respond fast | Active alerts by risk, live view with overlays, camera health | Acknowledge, call a supervisor, mark false alarm |
| **Shift supervisor** | Fix unsafe situations on the floor now | Alerts in their area, near-miss clips from the shift | Acknowledge, intervene, add a note, hand over to next shift |
| **Safety officer** | Investigate, coach, remove root causes | Incident timeline, evidence, recurring patterns, open actions | Confirm/dismiss, investigate, assign corrective actions, export |
| **EHS manager** | Programme performance across sites | Exposure and near-miss trends, leading indicators, validation status | Approve policies, set targets, report to management |
| **Plant / site manager** | Operational trade-offs | Top recurring risks, cost of downtime vs. risk, action status | Fund layout changes, accept residual risk formally |
| **Maintenance** | Fix physical controls | Work orders from corrective actions, machine-zone events during maintenance | Close work orders, record LOTO context |
| **Administrator** | Keep it running and secure | Device health, users, audit log, model and policy versions | Configure cameras, zones, roles, retention, integrations |
| **Auditor / works council (read-only)** | Verify proper use | Policy, retention, access logs, validation reports | Read only |

## 2. Information architecture

```
Sites (multi-site overview)
└─ Site
   ├─ Live            camera wall · alert rail · camera health
   ├─ Alerts          active queue by risk · review queue (weak evidence)
   ├─ Incidents       list · incident detail (timeline, evidence, assessment, actions, audit)
   ├─ Insights        exposure & near-miss trends · heatmaps · recurring patterns · PPE observed/non-observed
   ├─ Reports         shift · weekly · monthly · validation report
   ├─ Configuration   cameras & calibration · zones (typed, scheduled) · policies (draft/approved) · integrations
   └─ Administration  users & roles · retention · audit log · models & versions
```

**Today's app maps onto this as:** Sources gallery → *Live* (single camera); player + incident cards → *Alerts/Incidents*; Results tab and analytics → *Insights*; settings gear → *Configuration*.

## 3. Functional requirements

### 3.1 Ingestion and devices
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-ING-1 | Process video files and a local webcam | P0 | Built |
| F-ING-2 | RTSP streams with reconnection (≤ 10 s) and frame-drop accounting | P1 | Open |
| F-ING-3 | ONVIF discovery (Profile S/T) | P2 | Open |
| F-ING-4 | Per-camera health: FPS, drop rate, last-frame age, blur/obstruction, view-shift score | P1 | Open |
| F-ING-5 | Ground-plane calibration per camera (four floor points; reprojection error displayed) | P1 | Open |
| F-ING-6 | Headless monitoring service independent of browser sessions; multiple cameras per node | P1 | Open |

### 3.2 Perception and tracking
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-PER-1 | Person detection and anonymous tracking | P0 | Built |
| F-PER-2 | Hard-hat state with UNCERTAIN when unobservable | P0 | Built |
| F-PER-3 | Hi-vis state with the same observed/unobservable logic | P1 | Open |
| F-PER-4 | Forklift/pallet-truck/tugger detection and tracking | P1 | Open |
| F-PER-5 | Product-line detector trained only on commercially usable data | P1 | Open |
| F-PER-6 | Pose keypoints for person-down and reach-in (opt-in per camera) | P2 | Open |

### 3.3 Zones, temporal logic and risk
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-ZON-1 | Polygon zones per camera, foot-point, debounced | P0 | Built |
| F-ZON-2 | Typed zones (`kind`) with backward-compatible default | P0 | **Built (this branch)** |
| F-ZON-3 | Zone schedules and temporary validity windows | P1 | Open |
| F-ZON-4 | `keep_clear` zones (static-object dwell) for exits and emergency equipment | P1 | Open |
| F-ZON-5 | Dynamic zones attached to tracked vehicles or telemetry | P2 | Open |
| F-RSK-1 | Hazard taxonomy with stable codes and implementation status | P0 | **Built (this branch)** |
| F-RSK-2 | Versioned risk policy with approval metadata; schema validation | P0 | **Built (this branch)** |
| F-RSK-3 | Assessment per incident: severity, exposure band, risk level, evidence quality, factors, recommended actions, policy version/status | P0 | **Built (this branch)** |
| F-RSK-4 | Exposure-based escalation while an incident is open | P0 | **Built (this branch, recorded; not yet notified)** |
| F-RSK-5 | Context inputs (machine state, permit, load present) with "unknown never lowers risk" | P1 | Engine supports it; no live sources yet |
| F-RSK-6 | Vehicle–pedestrian conflict metrics: separation, closing speed, TTC, PET | P1 | Open |
| F-RSK-7 | Recurring-pattern detection (same zone/route/shift) | P1 | Open |

### 3.4 Incidents, notification and reporting
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-INC-1 | One incident per episode, cooldown, lost-track dedup, evidence frame | P0 | Built |
| F-INC-2 | Lifecycle: detected → confirmed → acknowledged → investigating → resolved / dismissed, with user and timestamp | P1 | Partial (statuses only) |
| F-INC-3 | Evidence clip (pre/post seconds), hashed at write | P1 | Open |
| F-INC-4 | Corrective actions with owner, due date, link to incident | P1 | Open |
| F-INC-5 | Event time recorded from the video/camera clock, not processing time | P1 | Open (audit D2) |
| F-NOT-1 | Notifications by risk level and area: on-screen, e-mail, webhook | P1 | Open |
| F-NOT-2 | Escalation on no acknowledgement within policy window | P1 | Open |
| F-REP-1 | CSV export | P0 | Built |
| F-REP-2 | Shift/weekly reports; validation report per camera | P1 | Validation metrics built (CLI); report UI open |

### 3.5 Validation and models
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-VAL-1 | Event-level metrics against labelled episodes (precision, recall with intervals, FA per camera-hour, latency, duplicates, missed critical) | P0 | **Built (this branch)** |
| F-VAL-2 | Shadow mode per camera/hazard (assess and store, no alert delivery) | P1 | Open |
| F-VAL-3 | Operator review outcomes feed per-camera false-alarm trend (drift) | P1 | Open |
| F-MOD-1 | Model registry with hash, data lineage, licence line, validation record | P1 | Partial (hash check exists) |

### 3.6 Privacy and security
| ID | Requirement | Pri | Status |
|---|---|---|---|
| F-PRV-1 | No identification of people; anonymous per-camera track IDs | P0 | Built |
| F-PRV-2 | Redaction of faces/bodies in stored evidence by default (subject box may stay visible) | P1 | Open |
| F-PRV-3 | Retention enforcement and legal hold | P1 | Open |
| F-PRV-4 | Worker notice, DPIA and works-council information templates | P1 | Open |
| F-SEC-1 | Authentication and roles | P1 | Open |
| F-SEC-2 | Append-only audit log of views and changes | P1 | Open |
| F-SEC-3 | Encrypted evidence at rest | P1 | Open |

## 4. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NF-1 | Alert latency (real-time hazards) | p90 ≤ confirmation time + 2 s |
| NF-2 | Throughput per edge GPU | ≥ 8 cameras at ≥ 8 analysed FPS each (to be measured in M1) |
| NF-3 | Availability of monitoring per camera | ≥ 99 % during operating hours; degraded state visible within 30 s |
| NF-4 | Offline operation | All detection, alerting and local UI work with no WAN for ≥ 72 h; store-and-forward |
| NF-5 | Reproducibility | Same input + frozen config → same incidents (already true offline; must hold for the service) |
| NF-6 | Explainability | Every assessment lists its factors and policy version |
| NF-7 | Security | No default credentials; TLS for all remote access; IEC 62443-aligned network design |
| NF-8 | Privacy | Data leaves the site only as configured; retention enforced |
| NF-9 | Backward compatibility | Existing configs, databases and CSV exports keep working |
| NF-10 | Testability | Unit tests for every rule; event-level regression tests on frozen clips in local CI |

## 5. UX direction

- **Calm control room.** Dark theme by default for control rooms, matched light theme for offices; one accent for risk, not decoration. The existing design system (`docs/design/DESIGN_SYSTEM.md`) already follows this restraint.
- **Risk first, then evidence.** An alert card shows: hazard name, zone, risk level, exposure time, evidence quality, and a thumbnail; one click to the clip and the assessment factors.
- **Uncertainty is visible.** "Not observable" and "weak evidence" are distinct visual states, never hidden in a percentage.
- **Policy status is always visible.** A header chip shows the active policy version and whether it is approved.
- **No vanity charts.** Every chart answers a question a role in §1 asks (for example "Which crossings produce the most near misses on night shift?").
- **Fast review.** Keyboard-driven review queue for safety officers (confirm / dismiss / not observable / next).

## 6. Explicit non-goals

- Identifying individuals (face recognition, gait recognition, re-identification across days).
- Inferring emotions, fatigue, intoxication or health.
- Acting as a machine safety function or fire detection system.
- Individual productivity or performance scoring.
