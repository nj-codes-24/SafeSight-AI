# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

**Version policy.** 0.x releases are research prototypes. A 1.0 release would need validation on real site cameras, which has not been done.

## [Unreleased]

### Added
- **Product research** in `docs/product_research/`: repository audit, industry research, hazard catalogue, competitors, papers, datasets, architecture, industry packages, validation framework, compliance, requirements, roadmap, differentiation and source register.
- **Hazard taxonomy** (`intelligence/taxonomy.py`): stable hazard codes with energy source, default severity, sensing mode and implementation status; the existing incident types map onto it.
- **Risk policy engine** (`intelligence/risk.py`): severity × exposure matrix, site and zone overrides, context rules that never lower risk when the context is unknown, evidence quality kept separate from risk, and the policy version and approval status on every assessment. The shipped policy is a draft example, not validated for any site; an optional site policy can be placed at `models/risk_policy.json`.
- **Typed zones:** an optional `kind` per zone (`restricted` by default, plus `machine_exclusion`, `suspended_load`, `electrical`, `confined_space`, `hot_work`, `vehicle_only`, `excavation`, `edge`, `pedestrian_only`, `keep_clear`). Unknown kinds are rejected.
- **Risk assessments per incident** in a new `risk_assessments` table, updated as exposure grows and when the incident closes; escalations are recorded (not yet notified).
- **Event-level validation** (`intelligence/event_metrics.py`, `scripts/evaluation/event_metrics.py`): event precision and recall with Wilson intervals, false alarms per camera-hour with Poisson intervals, latency, duplicates and missed critical hazards, against labelled episodes.

- **Headless multi-camera runtime** (`runtime/`, `python -m runtime run|validate|status`): several cameras monitored in one background process without a browser; file, RTSP and synthetic sources; per-camera capture and processing threads with bounded queues, reconnection with back-off, track reset with camera-scoped IDs, health states (CONNECTING, STREAMING, DEGRADED, RECONNECTING, STOPPED, ERROR) in `status.json`; one model shared through a batched inference thread; credential redaction; graceful shutdown on SIGINT, SIGTERM and Ctrl+Break. Example configurations in `config/`. RTSP has not been tested against a real camera stream.
- **Database:** additive tables `runtime_sessions`, `incident_context` (camera, site, camera-scoped worker, UTC times) and `camera_outages`; incident-ID collisions are retried instead of failing.
- **Benchmark** (`scripts/benchmark/runtime_benchmark.py`) and runtime tests (`tests/test_runtime.py`, `tests/test_runtime_integration.py`).

- **Validation milestone M2** (`docs/product_research/17_ANNOTATION_PROTOCOL.md`, `18_VALIDATION_RESULTS.md`, `reports/validation/`):
  - a footage inventory with hashes, decode checks, duplicate detection and source groups;
  - an annotation protocol and versioned label format (`intelligence/annotations.py`, `safesight.labels/1.0`) with locking and hashing;
  - a local labelling app (`scripts/validation/annotator.py`) that never shows model output;
  - a frozen-model evaluation through the headless runtime (`scripts/validation/run_evaluation.py`);
  - error-analysis tools (`render_failures.py`, `probe_detections.py`);
  - a benchmark of the evaluation workload (`--clips`).

  The labels are a provisional AI first pass, so the results are provisional and not ground truth.
- **Event metrics:**
  - ignore regions (uncertain, unobservable and unusable time);
  - alerts where the rule does not apply ("context"), counted separately;
  - optional episodes;
  - a tolerance widened by annotation uncertainty;
  - false alarms per *monitorable* hour;
  - late detections, duration error, alert precision;
  - a cluster bootstrap by source group.

  The existing API is unchanged.

- **Incident lifecycle (M2.1)** (`inference/incident_lifecycle.py`). Incidents:
  - stay open while the violation is observed;
  - survive short gaps (`grace_seconds`) and re-associate fragmented tracks by position;
  - resolve only on sustained positive evidence (`resolve_seconds`), a zone exit, or leaving the area where PPE is required;
  - otherwise end with an explicit unknown outcome (observation lost, camera interrupted, session end).

  An incident ends at its last observation. Exposure never extends past the evidence, and unobserved time is reported. A confirmed resolution clears the cooldown, so a new violation is never suppressed. Incidents form alert groups; notifications are batched per burst. Every decision is written to an append-only audit table.
- **PPE requirement policy** (`intelligence/ppe_policy.py`, `config/ppe_policy.example.json`, `runtime.ppe_policy`):
  - explicit, versioned requirements per site, camera and zone, with confirmed or provisional status and effective times;
  - without a policy, missing head protection is a review item, never a confirmed violation;
  - reports carry six PPE categories (confirmed violation, confirmed compliance, uncertain, not applicable, not observable, requirement not configured);
  - new zone kind `work_area`.
- **Visibility.** A "no helmet" detection on a head cut off by the image border is not evidence of a missing helmet. Workers with no usable head evidence are reported as not observable.
- **Database.** Additive tables `incident_lifecycle`, `incident_events`, `alert_groups`, `notifications`, `ppe_observations`.
- **Evaluation.**
  - Identity-aware event matching (`evaluate(identity=True)`) with label schema `safesight.labels/1.1` identity anchors.
  - Inter-annotator agreement measures (`intelligence/agreement.py`).
  - A blinded human review workflow (`scripts/validation/human_review.py`, `reports/validation/human_review/`) and an annotator reviewer mode with native-resolution zoom.
  - Model traces and deterministic replay of the frozen M2 logic for before/after diagnostics (`scripts/validation/record_traces.py`, `replay.py`, `legacy_m2/`, `m2_1_diagnostics.py`).
  - Label set `m2-provisional-v1.2` (identity anchors only).
  - The scorer refuses to overwrite existing results.

- **Camera view-change detection** (`inference/view_monitor.py`, `runtime/view.py`; `docs/product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md`). The headless runtime checks twice a second that each camera still shows its registered reference view (ORB features and a RANSAC similarity fit against a temporal-median reference; contrast-normalised blockage checks):
  - camera movement (pan, tilt, rotation, zoom), scene cuts and blockage are confirmed after 5 s of persistent evidence; workers, vehicles, brief occlusions and lighting changes are not view changes;
  - a separate view state (`INITIALIZING`, `VIEW_STABLE`, `VIEW_CHANGE_SUSPECTED`, `VIEW_CHANGED`, `BLOCKED`, `RECOVERING`, `VIEW_UNVERIFIED`) reported beside the connection state; an untrusted view means monitoring "no";
  - open incidents end at the last reliable observation with `camera_view_changed`, `camera_scene_switched`, `camera_blocked` or `camera_view_unverified` (unknown outcome, never "resolved"), recording the view event and the risk level before the interruption; tracks reset with new IDs; analysis stops until the registered view returns for 3 s or an operator accepts a new view;
  - reference views are versioned per camera; zones of an unverified view raise no zone alerts until an operator verifies them (`python -m runtime view list|accept|verify-zones|acknowledge`);
  - vibration, repeated changes and focus loss are warnings only; `view_monitor:` settings per camera (on for file and RTSP sources); `geometry: false` for cameras meant to move (no zones allowed).
  
  All movements in the tests are simulated; no physical camera was tested.
- **Demo configurations:** `config/runtime.demo.yaml` is now a fixed-camera demo (the only fixed-view demo scene, two cameras, full view monitoring at default thresholds); the four hand-held/moving clips moved to `config/runtime.demo_handheld.yaml` with blockage-only view monitoring, no zones, monitoring reported as "partial" (camera position not validated), and their own output folder.
- **Database:** additive tables `camera_view_revisions`, `camera_view_events`, `camera_view_commands`.
- **Dashboard:** Results › "Runtime cameras" shows the headless runtime's connection and view health side by side (reads `status.json` only).
- **Benchmark** `scripts/benchmark/view_monitor_benchmark.py` (view monitoring off vs on, 1/4/8 cameras) and tests `tests/test_view_monitor.py`, `tests/test_view_monitor_footage.py`.

- **Milestone M3: verified validation and pilot readiness** (`docs/product_research/22`–`25`):
  - independent human review packages `reports/validation/human_review/reviewer_1` and `reviewer_2` (empty, blinded, separately identified), with per-package instructions, clip manifests, completion and blinding checks, exports (`human_review.py check|export`); the M2.1 `reviewer_A/B` packages are kept unchanged and superseded;
  - agreement analysis extended: hazard category, zone assignment, event kind (uncertainty), annotation confidence (weighted kappa), per-clip values and clip-level bootstrap intervals;
  - optional annotation `confidence` and per-clip `reviewer_notes` (protocol amendment A6); the annotator records them;
  - scorer: end outcomes per match (`resolved` / `unknown`), premature resolutions, duplicates in the same alert group, per-camera and per-site tables, unscorable alerts by label state; pooling moved to `intelligence.event_metrics.summarise()`;
  - incident review audit table `incident_reviews` (who, when, previous status, reason) written by the dashboard and by `python -m runtime incident list|review`; the dashboard asks for an optional reviewer and reason and shows the history;
  - engineering baseline record and verifier (`scripts/validation/freeze_baseline.py`, `reports/validation/m3_baseline/`);
  - physical camera acceptance harness (`scripts/validation/camera_acceptance.py`), not yet run on a camera;
  - tests `tests/test_evaluation_integrity.py`, `tests/test_policy_safety.py`, `tests/test_camera_acceptance.py`, `tests/test_baseline_record.py`, more in `tests/test_human_review.py`.

### Changed
- The pipeline uses the incident lifecycle. The `IncidentManager` API and its cooldown behaviour for direct callers are unchanged. The session summary counts incidents raised instead of distinct cooldown keys.
- Zones without a `kind`, the incidents table, CSV export and the alert feed behave exactly as before; alerts carry four extra keys (`hazard`, `severity`, `risk`, `evidence_quality`), and with the lifecycle also `classification`, `group_id`, `requirement`, `requirement_status`, `relation`.
- The dashboard labels review alerts "review (no PPE rule configured)".
- `Detector` can share a model and route its model call; `Pipeline` accepts frame timestamps, resets tracks without reusing IDs, can annotate only evidence frames, and imports the detector lazily (so it imports without PyTorch). Defaults are unchanged for the dashboard.
- Saving an edited zone in the settings menu keeps fields the editor does not show (such as `kind`).
- The runtime CLI test accepts DEGRADED as well as STREAMING, because a loaded test machine can legitimately fall below 80 % of the target rate. This was a flaky failure seen once while another CPU-heavy job ran.

### Fixed
- Several cameras opening a new runtime database at the same moment could stop one of them with "database is locked" (switching to WAL ignores the busy timeout). The switch is now retried briefly.
- Label scoring merged an `uncertain` stretch into the adjacent violation of the same worker. Only episodes of the same kind are merged now.
- Locking a label set whose name contains a dot (`…-v1.1`) overwrote the lock of `…-v1`. Lock files now use the full folder name, and verification checks the set name.
- Incidents closed on the first compliant vote, and the cooldown then hid the continuing violation for 30 s; exposure counted uncertain frames and the lost-track wait. Fixed by the lifecycle above.
- Closing an incident overwrote an operator's REVIEWED or FALSE_ALARM status set while it was open. Detector closure now changes only open, unreviewed incidents.
- A PPE policy entry with status `provisional` (not confirmed by a responsible person) produced confirmed violations. It now gives review items and the category `requirement_not_confirmed`; only `confirmed` entries can make a confirmed violation (M3).
- The time-only event matcher ignored camera and session; it now applies the same scope rule as the identity-aware matcher (M3).
- `IncidentDB.set_status` now raises `KeyError` for an unknown incident instead of silently doing nothing.

## [0.1.0] - 2026-11-02

First public release of the academic research prototype. The source code is licensed under **AGPL-3.0-only**; trained model weights are **not** included ([LICENSING_DECISION.md](LICENSING_DECISION.md)).

### Added
- **Detection:** M5 detector (YOLO26n; `person`, `helmet`, `no_helmet`), selected after experiments B0 and M1–M5. Weights are recorded by SHA-256 but not distributed.
- **Runtime pipeline:** YOLO26n detection, then ByteTrack on person boxes, head-to-worker association and a multi-frame helmet vote (COMPLIANT / VIOLATION / UNCERTAIN).
- **Zones and incidents:** restricted zones (normalised polygons, foot-point test, debounced entry and exit), and an incident manager with video-time cooldown, broken-track duplicate suppression and evidence frames.
- **Storage:** SQLite store for sessions and incidents, review statuses and CSV export.
- **Monitoring app:** source gallery (demo clips, uploads, webcam), cinematic player with overlay controls, in-player settings menu, session figures and analytics, incident inspector, history; single-run lock across browser tabs.
- **Training:** training entry point with heartbeat and atomic verified checkpoints; independent watchdog with health checks, a recovery ladder and a keeper task.
- **Data:** data preparation with leakage removal (near-duplicate clustering), pose-teacher pseudo-labels and audited SH17 label derivation.
- **Evaluation:** common and SH17 validation, PR-curve threshold rule, held-out test (run once), unseen-footage comparison, runtime measurements.
- **Tests:** unit tests, watchdog failure drills, and integration tests that skip without weights or data.
- **Repository:** documentation (architecture, model card, datasets and licensing, evaluation, training, installation, deployment, limitations, troubleshooting, demo guide), CI workflow for lint and CPU tests, contribution and security policies, third-party notices.

### Known limitations
- No validation on real site cameras.
- Distant or small workers are missed.
- Trained weights are not distributed (SH17 CC BY-NC-SA 4.0 and AGPL-3.0 considerations); the code is AGPL-3.0-only.

See [docs/limitations.md](docs/limitations.md).

[Unreleased]: https://github.com/nj-codes-24/SafeSight-AI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nj-codes-24/SafeSight-AI/releases/tag/v0.1.0
