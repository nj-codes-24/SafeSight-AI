# 09 — Safety validation framework

Date: 5 November 2026. Purpose: define how SafeSight proves, per hazard and per camera, that it does what it claims, and what it is allowed to claim at each stage. Tooling for the event-level metrics is built in this branch (`intelligence/event_metrics.py`, `scripts/evaluation/event_metrics.py`).

## 1. Why mAP is not enough

mAP measures single-image box quality. A safety team experiences **events**: was a real exposure caught, how quickly, and how many alerts were noise? The existing evaluation already shows the gap: M5 has lower common-val mAP than M2 yet was the only model that caught the real violator without false alarms on unseen footage (`docs/evaluation.md` §5–7). Validation therefore has three levels:

| Level | Unit | Examples |
|---|---|---|
| Model | box / keypoint | AP per class, precision/recall at the operating threshold |
| Tracking | track | HOTA, IDF1, ID switches per 100 track-minutes |
| **Event** (decisive) | episode | event recall, false alarms per camera-hour, latency, duplicates, exposure-time error |

## 2. Metric definitions

| Metric | Definition | Implemented |
|---|---|---|
| **Episode** | A labelled interval `[start, end]` during which a hazard condition is true (for example a person inside zone Z), with hazard type and zone | Format below |
| **True positive** | A predicted event of the same hazard (and zone, if given) whose time falls within `[start − tol, end + tol]` of an unmatched episode | Yes |
| **Duplicate** | A further prediction matching an already-matched episode | Yes |
| **False alarm** | A prediction matching no episode | Yes |
| **Missed episode** | An episode with no matching prediction | Yes |
| **Event precision / recall** | TP / (TP + FA) and TP / (TP + missed); duplicates reported separately | Yes |
| **False alarms per camera-hour** | FA / (observed footage hours) | Yes |
| **Detection latency** | predicted time − episode start, for matched episodes (median, p90, max) | Yes |
| **Missed critical hazards** | Missed episodes whose hazard severity ≥ 4 | Yes (severity from taxonomy) |
| Time to confirm / acknowledge / resolve | From the incident lifecycle (operational) | P1 with lifecycle |
| Zone-entry reliability | Event recall restricted to zone hazards | Via filtering |
| Exposure-time error | Predicted exposure − labelled exposure | P1 |
| ID switches | From tracking ground truth | P1 tooling |
| Robustness slices | All event metrics by day/night, weather, camera, distance band, occlusion level | By running per slice |
| Drift | Weekly false-alarm rate per camera from operator reviews; score distribution shift | P1 |
| System | Inference latency p50/p95, FPS per camera, frame-drop rate, GPU utilisation, uptime | P1 health service |

**Ground-truth episode format** (JSON, one file per clip or camera):

```json
{"source": "dock_cam_07_2026-11-03.mp4", "duration_s": 3600,
 "episodes": [{"hazard": "ZONE_INTRUSION", "zone": "Aisle 4", "start_s": 812.4, "end_s": 829.0, "note": "picker crossing"}]}
```

## 3. Statistical honesty

- Report counts with **confidence intervals** (Wilson interval for proportions; Poisson interval for false alarms per hour). With 4 of 4 caught, recall's 95 % Wilson interval is roughly 0.51–1.00: that is what "4/4" actually supports.
- **Minimum evidence** before a claim: for a recall claim at a lower 95 % bound of 0.9, roughly 35+ consecutive caught episodes with no misses are needed; plan labelling accordingly.
- Never pool sites to hide a bad camera; report per camera and pooled.

## 4. Evaluation design and leakage rules

1. **Split by site and camera, not by frame.** Test cameras must be unseen in training and threshold tuning.
2. **Split by time** for the same camera when site data must be reused: train on weeks 1–2, test on week 4.
3. **Freeze before testing.** Thresholds, zones and policies are frozen before the test footage is scored (as M5's test set was).
4. **Label before running** the model, as done for the unseen-clip study, to avoid confirmation bias.
5. **Cover the operating envelope:** day/night, shift changes, weather (outdoor), seasonal clothing, peak and quiet periods, maintenance activities, new PPE colours.
6. **No fabricated or synthetic test results.** Synthetic data may train; it never validates.

## 5. Acceptance criteria by stage

Numbers are **starting targets** to be agreed with the customer's safety lead per hazard; they are not achieved results.

| Stage | Purpose | Data | Criteria | What may be claimed |
|---|---|---|---|---|
| **1. Research experiment** | Is a capability feasible? | Public datasets + a few clips | Model-level metrics on leak-free splits; failure analysis written | "Experimental; not validated" |
| **2. Controlled demonstration** | Show the workflow end to end | Curated clips with labelled episodes | All labelled demo episodes detected; zero false alarms on the demo set; latency < confirmation time + 1 s; results reproducible from frozen config | "Demonstrated on curated footage" (today's status) |
| **3. Pilot site (shadow mode)** | Measure on real cameras without alerting workers | ≥ 2 weeks per camera, ≥ 20 h labelled episodes per hazard, covering shifts and lighting | Event recall ≥ 0.80 (lower 95 % bound reported) for severity ≥ 4 hazards; false alarms ≤ 1 per camera per 8-hour shift; latency p90 ≤ 3 s for real-time hazards; camera uptime ≥ 99 %; all misses reviewed with root cause | "Validated in shadow mode on cameras X–Y for hazards H with these figures" |
| **4. Production** | Alerting with human response | Continuous | Pilot criteria sustained for 4 weeks of live use; operator-reviewed false-alarm rate tracked weekly; drift alarm when the rate doubles; re-validation after camera moves, model or policy changes | Per-camera, per-hazard performance statement with dates; never "the site is safe" |

## 6. Required documentation per validated deployment

- Validation report per camera and hazard (metrics, intervals, slices, misses with images).
- Frozen configuration hash (model, tracker, policy version, zones, thresholds).
- Policy approval record (competent person, date, scope).
- Known limitations specific to the site (for example "camera 7 cannot see feet behind rack row C").
- Re-validation triggers.

## 7. Using the tooling

```powershell
python scripts\evaluation\event_metrics.py --truth gt\dock_cam_07.json --db logs\incidents\incidents.db --session S20261103-080000 --tolerance 2.0
```

Outputs a JSON report with TP, FA, duplicates, misses, precision, recall (with Wilson intervals), false alarms per camera-hour (with a Poisson interval), latency statistics, and per-hazard breakdowns. Predictions can also be supplied as a JSON list instead of a database session.

**Current state:** there is no episode-level ground truth for the repository's demo or unseen clips (`reports/unseen_gt/ground_truth.json` records violator counts, not time intervals). Creating it for the five demo clips is the first M1 task; no event-level numbers are reported until then.
