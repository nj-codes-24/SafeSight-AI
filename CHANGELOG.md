# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

**Version policy.** 0.x releases are research prototypes. A 1.0 release would need validation on real site cameras, which has not been done.

## [Unreleased]

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
