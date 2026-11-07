# 22 — Industrial data acquisition plan

Milestone M3, 6 November 2026, branch `research/platform-foundations`. **Planning document: no industrial footage has
been obtained, and none may be obtained without the authorisations in §6.** Companion checklist for site visits:
[`22A_SITE_DATA_COLLECTION_CHECKLIST.md`](22A_SITE_DATA_COLLECTION_CHECKLIST.md).

## 1. Why the current footage cannot establish industrial reliability

| What we have | Why it is not enough |
|---|---|
| 15 evaluated recordings, about 26 minutes, 12 source groups (`18` §1) | Every held-out true positive and genuine false alarm comes from one source group (G01, three recordings from one site): the cluster bootstrap is degenerate (`18` §8) |
| 8 PPE episodes (6 held-out), 0.24 monitorable hours | Held-out recall 3 of 6 has a 95 % Wilson interval of 0.19–0.81; 2 false alarms in 0.231 h is 8.7 per hour with a 95 % interval of 1.0–31.3 (`18` §2.1) |
| Zone entry: 4 episodes, 20 s, on demo zones | Measures geometric zone entry on polygons drawn for illustration, not restricted-area violations |
| Public demo footage, much of it handheld or edited | Fixed industrial cameras have no cuts and different geometry; edited footage breaks tracking, view monitoring and zones |
| Labels: an AI first pass, provisional | No ground truth until two humans and an adjudicator finish (`reports/validation/human_review/`) |

Even after verification, these clips remain a development benchmark. Every capability claim needs footage collected
for the purpose, from fixed cameras at real sites, labelled blind.

## 2. Audit of the earlier minimum (10 sites, 50 events, 10 camera-hours)

The minimum proposed in `18` §10 (P0.4) was at least 10 independent sites, at least 50 genuine violation events and at
least 10 monitorable camera-hours. The numbers below were computed with the repository's own interval functions
(`intelligence/event_metrics.py`: Wilson for proportions, Byar's approximation to the exact Poisson interval).

### 2.1 Recall: events

| Episodes (independent) | 95 % interval at recall 0.8 | Width |
|---|---|---|
| 20 | 0.58–0.92 | 0.34 |
| 50 | 0.67–0.89 | 0.22 |
| 100 | 0.71–0.87 | 0.16 |
| 200 | 0.74–0.85 | 0.11 |

Events from one site are correlated (same camera, lighting, PPE colours, workers). With *m* events per site and an
intra-site correlation ρ, the effective sample is n / (1 + (m − 1)ρ):

| Episodes | Sites | ρ = 0.1: effective n | 95 % interval at 0.8 | ρ = 0.2: effective n | 95 % interval at 0.8 |
|---|---|---|---|---|---|
| 50 | 10 | 36 | 0.65–0.90 | 28 | 0.60–0.90 |
| 100 | 10 | 53 | 0.67–0.88 | 36 | 0.65–0.90 |
| 150 | 15 | 79 | 0.70–0.87 | 54 | 0.67–0.88 |
| 200 | 20 | 105 | 0.71–0.87 | 71 | 0.70–0.88 |

ρ is unknown until we have multi-site data; 0.1–0.2 is an assumption, not a measurement. The reported intervals will
use the cluster bootstrap over sites, which needs no assumed ρ but is unstable below about 8–10 sites.

### 2.2 False alarms: monitorable camera-hours

| False alarms observed | 95 % interval as a multiple of the observed rate |
|---|---|
| 0 | 0 to 3.69 per observed hour (upper bound only) |
| 5 | 0.32–2.33 × |
| 10 | 0.48–1.84 × |
| 30 | 0.67–1.43 × |
| 100 | 0.81–1.22 × |

A false-alarm rate an operator can live with is small. A 20-camera site at 0.25 false alarms per camera-hour receives
about 40 nuisance alerts per 8-hour shift. Showing an upper bound below 0.25 per camera-hour needs at least 15 monitorable
camera-hours *with zero false alarms*, and about 120 hours if the true rate is near 0.25 and we want ±40 %. Showing
below 0.1 per hour needs at least 37 hours with zero false alarms.

### 2.3 Verdict on the earlier minimum

| Element | Verdict |
|---|---|
| ≥ 10 independent sites | **Keep as a floor**, and add: no site contributes more than 20 % of a hazard's episodes; at least 3 site types (§3) |
| ≥ 50 violation events | **A floor for a first PPE estimate only**, giving roughly ±11–15 points at recall 0.8 after clustering. Not enough for a lower bound high enough to support a product claim. Target ≥ 100 per hazard, and ≥ 30 per reported stratum (lighting, distance band, headwear type) before a stratum is quoted |
| ≥ 10 monitorable camera-hours | **Too low by an order of magnitude.** It cannot bound a false-alarm rate an operator would accept. Target ≥ 100 monitorable camera-hours per hazard for the operational pilot (Gate C in `23`), spread over shifts, and ≥ 300 hours before any production claim (Gate D) |
| One minimum for every hazard | **Wrong.** Minimums differ by hazard (§2.4) |

### 2.4 Minimums by hazard

Planning targets, to be revised once the first sites give real prevalence and correlation. "Monitorable" excludes
uncertain, unobservable and unusable time (`17` §4).

| Hazard | Sites | Positive episodes | Monitorable camera-hours | Notes |
|---|---|---|---|---|
| Missing head protection (`PPE.HEAD.MISSING`) where a confirmed site rule requires it | ≥ 10 (≥ 15 for Gate D) | ≥ 100 (floor 50 for a first estimate) | ≥ 100 (≥ 300 Gate D) | Positives are plentiful in some sites and nearly absent in compliant ones; both kinds of site are needed, the second for false alarms |
| Restricted-zone entry (`ZONE.ENTRY`) with a **real, documented** restriction | ≥ 10 | ≥ 100 entries, of which ≥ 30 unauthorised if authorisation is recorded | ≥ 100 | Without site documentation of the restriction and of who is authorised, an entry is geometry, not a violation (`17` §8) |
| Pedestrian in a vehicle-only aisle (`VEH.PED_ZONE.ENTRY`) | ≥ 10 | ≥ 60 per layout type | ≥ 200 | Needs site traffic rules; occlusion by racking dominates |
| Forklift–pedestrian conflict / near miss (`VEH.PED.CONFLICT`, research) | ≥ 10 | ≥ 60 per main stratum (vehicle type × layout), several hundred in total (`20` §3) | Several hundred, mostly negative | Genuine near misses are rare; most hours are negative footage. See `24` |
| Camera view interruption (operational, not a safety hazard) | Every pilot camera | Staged per `23A` plus naturally occurring | All pilot hours | Measured as detection of real movement/blockage, and as false view alerts per camera-day |

Positive episodes must be **genuine**. Staged or acted violations may be used for development and for camera
acceptance tests, but are reported separately and never counted toward these minimums.

## 3. Target environments

Priority follows the wedge in `12` §3: fixed indoor cameras where camera analytics are most reliable and the hazards
are high-energy.

| Priority | Environment | Why | Main hazards to collect | Typical difficulty |
|---|---|---|---|---|
| 1 | Warehouses | Fixed high cameras, controlled lighting, frequent vehicle–pedestrian interaction | PPE where required (loading docks), restricted zones (dock edges, racking maintenance), pedestrians in vehicle aisles | Racking occlusion, long aisles (small people far away), mixed lighting at dock doors |
| 2 | Distribution centres | Same as warehouses at higher traffic and shift coverage | As above, plus high worker density and night shifts | Density, motion blur, IR at night |
| 3 | Factory logistics areas (goods-in, line-side supply, internal transport) | Forklifts and tuggers among production workers | Pedestrian–vehicle interaction, PPE in designated areas | Machinery clutter, steam, glare |
| 4 | Manufacturing floors | PPE rules vary by area; machine guarding zones | Zone entry at guarded cells, area-specific PPE | PPE policy complexity, occlusion by machines |
| Later | Construction | Kept for later: moving cameras, weather, distant workers, short project life (`12` §3) | — | — |

Each site should contribute cameras of more than one kind (dock, aisle, crossing, goods-in) and both day and night
shifts where it operates them.

## 4. Footage requirements

| Property | Requirement | Reason |
|---|---|---|
| Source | The site's own fixed CCTV cameras, as they will be used in deployment, recorded from the stream (RTSP) or the site's VMS export without re-encoding where possible | The evaluation must match deployment conditions; re-encoding changes artefacts |
| Resolution | Record at the camera's native stream resolution; 1080p preferred, 720p minimum. Record the resolution actually delivered, not the nominal one | Head size at the model input (`17` A2) depends on it; 8–13 px heads at the model input failed in M2 |
| Frame rate | Native rate, at least 10 FPS; record the delivered rate and frame-time jitter | The runtime analyses at 10–15 FPS; lower rates change confirmation timing |
| Mounting | Fixed mounts only for the evaluation set. Record height, tilt and approximate field of view, and photograph the mount | Geometry, ground-plane calibration (`24`) and view monitoring assume fixed mounts |
| Field of view | Cover areas where the hazards occur (docks, crossings, aisles, guarded cells). Note the distance band of the working area (near < 10 m, mid 10–25 m, far > 25 m) | Far-field heads are the model's weakest case |
| Lighting | Day, night, shift change, dock doors open and closed, IR/night mode where the camera switches. Label the lighting condition per segment | Lighting is a known stratum; IR changes the image completely |
| Occlusion | Natural occlusion by racking, loads and vehicles must be present, not avoided | Real deployments are occluded; unobservable time is part of the measurement |
| Worker density | Quiet and peak periods | Crossings, ID switches and alert bursts appear at density |
| Machinery and vehicle activity | Forklifts, reach trucks, pallet trucks, tuggers in operation, with the vehicle types noted | Required for vehicle-related hazards; also produces false alarms for PPE and zones |
| Recording duration | Continuous segments of at least 30 minutes, sampled across the day and the week; not only "interesting" moments | Event-driven clips inflate prevalence and hide false alarms |
| Representative negatives | At least 70 % of monitorable hours must be ordinary operation with no labelled event | The false-alarm denominator |
| Genuine positives | Collected passively from normal operation. No staging, prompting or tolerating of unsafe behaviour to obtain data | Ethics and validity; staged events are reported separately |
| Camera movement and blockage | Record natural occurrences (bumps, cleaning, PTZ presets, IR switches). Staged tests follow `23A`, on cameras the site authorises for it | View-change detection must be measured on real cameras |
| Clock | Record the camera's timestamp (if overlaid or in the stream) and the recorder's UTC time | Camera clocks drift; cross-camera timing needs offsets |

## 5. Annotation requirements

Labels follow the annotation protocol (`17`), label schema `safesight.labels/1.1`, two independent human reviewers
plus adjudication (`reports/validation/human_review/` is the template), and a lock before any model is run.
**Hazards that cannot be reliably established from video are not annotated as hazards.**

| Label family | What is labelled | What is *not* labelled from video |
|---|---|---|
| PPE compliance | Per worker episode: compliant, violation, uncertain, not observable, not applicable; observability class; head size at native and model-input resolution; the requirement basis from the **site's documented rule** (`confirmed`), never inferred from the scene for site data | Whether a worker was exempt (religious headwear, visitor escorted) unless the site documents it; PPE that is not visible at the camera's resolution (eye, hearing) |
| Restricted-zone entry | Entry and exit of the foot point into a documented restricted area; zone polygon and its documentation reference; authorisation only if recorded by the site (permit, access log) | Authorisation from appearance; intent |
| Worker visibility | Interval states per hazard (monitorable, uncertain, unobservable, unusable, not applicable) | — |
| Worker identity continuity | Identity anchors (normalised point per worker at chosen times, `17` A3); on sampled frames, per-person boxes with a camera-local ID where tracking metrics are needed. Appearance descriptions only, never names or faces | Identity across cameras; real identity |
| Forklift–pedestrian interactions | Vehicle type; pedestrian and vehicle boxes on sampled frames; ground-plane positions via calibration; interaction episodes with start, end, minimum separation (metres, from calibration) and the site rule that applies | Speeds or distances without calibration; whether a driver saw the pedestrian |
| Near misses | Only by a definition fixed before labelling (`24` §6): for example post-encroachment time or minimum separation below a site-set threshold while the vehicle moves, with the measured value, plus an independent "would a safety officer record this?" judgement as a separate field | Intent, attention, fault |
| Camera-view interruptions | Intervals where the view moved, was blocked, switched (IR), or lost focus: labelled `unusable` with a cause, and the time of the physical change if known from the site log | — |

Annotation effort, from M2 (`18` §9): about 6–10 × real time for PPE labelling by an experienced reviewer. 100
monitorable camera-hours therefore costs roughly 600–1,000 reviewer-hours per reviewer for full double annotation.
This is the main cost of the plan. The practical design is:
- full double annotation of every positive candidate segment and of a random 20 % of negative time (the protocol's
  double-labelled share), stratified by site and camera;
- single annotation of the remaining negative time;
- adjudication of every disagreement.

Candidate segments may be found with motion or person-presence filters that do not use the model under evaluation.

## 6. Privacy and legal requirements

SafeSight's design commitments (`10`) apply. Items marked ⚖ need qualified legal review in the site's jurisdiction
before any recording starts.

| Requirement | What it means in practice |
|---|---|
| Site authorisation ⚖ | A written data agreement with the site operator: purpose (evaluation of safety analytics), cameras, period, retention, who may access, deletion, publication rights (none by default), and the signatory's authority |
| Worker transparency ⚖ | Workers and their representatives are informed before recording starts: what is recorded, why, for how long, who sees it, that it is not used for discipline or performance evaluation. Notices at the recorded areas. Works council or union consultation where it applies (`10` §4) |
| Legal basis ⚖ | Determined by the site's counsel: for example legitimate interests or legal obligation (GDPR), the employment ground in DPDP s.7(i) with its limits, or consent where required. Consent is not assumed to be valid in an employment relationship |
| DPIA ⚖ | A data protection impact assessment (or local equivalent) completed by the site before recording |
| Data minimisation | Only the cameras and hours the plan needs; no audio; no face recognition; no identification of individuals; labels describe appearance and position only |
| Retention | Raw footage kept only until labels are adjudicated and locked, plus a fixed audit period agreed in the data agreement (proposed: 90 days after lock); labels and metrics may be kept longer. Deletion is logged |
| Access control | Named reviewers only; access logged; footage never on personal devices; reviewers sign a confidentiality undertaking |
| De-identification | Faces blurred in any image that leaves the secure environment (reports, error-analysis sheets). Raw footage for labelling stays unblurred only inside the secure environment, because blurring hides head protection |
| Secure local storage | Encrypted storage on the site's premises or on a SafeSight-controlled offline machine; no cloud upload; no external annotation service; no external AI service sees the footage |
| Dataset licensing and permissions | The data agreement states whether footage may be used for evaluation only, or also for training a product model, and whether derived labels may be kept. Default: evaluation only, on-site |
| Withdrawal | A process for a worker or the site to request deletion of specific footage |

No real worker footage is obtained without all of the above in place. Public footage is used only within its
licence, and is never presented as industrial validation.

## 7. Acquisition channels

| Channel | Value | Cost and risk |
|---|---|---|
| Supervised pilot sites (Gate B/C in `23`) | Deployment-like footage, real policies and zones, safety-officer review | Slow (agreements, DPIA); needs a partner |
| Own or affiliated facilities with consent (university workshops, logistics partners) | Faster access; useful for development and camera acceptance tests | Not independent industrial sites; reported as development data |
| Licensed footage from camera/VMS vendors or integrators | Variety of cameras | Licence terms; rarely contains genuine violations |
| Public datasets (`06`) | Training and development only | Licences (M5's non-commercial problem); never counted as site validation |

## 8. Data handling pipeline

1. **Before recording:** site survey and checklist (`22A`), data agreement, DPIA, worker notices, camera inventory with
   resolution, frame rate, mount and field of view.
2. **Recording:** on the site's network; files hashed (SHA-256) at write; manifest with camera, site, UTC start, delivered
   resolution and frame rate.
3. **Splits fixed before labelling, by site:** development sites (thresholds, zones, policies may be tuned) and held-out
   sites (scored once, with frozen configuration). Never split one site's cameras across both.
4. **Annotation:** blind, two reviewers, adjudication, lock (`17`, `human_review.py`).
5. **Evaluation:** `run_evaluation.py` on the locked set; identity-aware matching; cluster-aware intervals by site; per
   camera and per clip reports; no threshold change after seeing held-out results.
6. **Retention and deletion** per the agreement, logged.

## 9. What this plan does not claim

- It does not claim that the minimums in §2.4 are sufficient for a production safety claim; Gate D (`23`) requires more,
  plus an independent safety and legal assessment.
- It does not claim that any site has agreed to participate.
- Numbers in §2 are planning calculations, not measurements.
