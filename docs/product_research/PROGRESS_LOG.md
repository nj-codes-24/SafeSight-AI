# Progress log — product research and platform foundations

Research date: **5 November 2026**. Local branch `research/platform-foundations` (created from `main` at `6aa177e`). Nothing is committed or pushed: the maintainer commits and pushes.

## Baseline (before any change)

| Item | Value |
|---|---|
| Git | `main` at `6aa177e`, clean except the untracked `presentation/SafeSight_AI_deck.pdf` (left untouched) |
| Python | 3.11.18 (`.venv`) |
| Tests | `python -m pytest -rs -q`: **32 passed** in 120 s (weights, demo clips and processed data present, so integration tests ran) |
| Lint | `ruff check .`: all checks passed |
| Champion model | `models/best.pt` SHA-256 `E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534` (matches `models/model_config.yaml`) |
| Runtime config | `models/runtime_config.json`: two demo zones; thresholds at defaults (person 0.35, helmet 0.30, no_helmet 0.60) |

## Phase log

| Phase | Status | Notes |
|---|---|---|
| A. Repository audit | Done | Read all runtime modules (`inference/`, `database/`, `app/`), tests, CI, docs, licensing decision, evaluation reports |
| B. Industry, standards, competitor, paper and dataset research | Done | See `14_SOURCE_REGISTER.md` |
| C. Opportunity analysis | Done | `03`, `08`, `13` |
| D. Architecture and decisions | Done | `07`, `11`, `12`; wedge chosen in `00` |
| E. Documents | Done | `00`–`14`, `README.md` |
| F. Engineering | Done | See "Repository changes" |
| G. Final review | Done | See "Tests and results" |

## Important discoveries (short)

1. The existing pipeline is honest and well-engineered for a single camera: UNCERTAIN instead of guessing, debounced zones, video-time cooldowns, broken-track suppression. Its limits are architectural (single process, single camera, hard-coded incident types, no event model), not sloppiness.
2. The champion model cannot be used commercially (SH17 is CC BY-NC-SA 4.0; Ultralytics is AGPL-3.0). Any commercial path needs a retrain on commercially usable data and a decision on the detection framework.
3. Regulatory status that changed recently: India's OSH Code in force since 21 Nov 2025; DPDP Rules notified 13 Nov 2025 (full effect by May 2027); EU AI Act Annex III high-risk obligations deferred to 2 Dec 2027 by the Digital Omnibus (secondary sources); EU Machinery Regulation applies from 20 Jan 2027; ISO 45001 revision at DIS stage, publication expected 2027.
4. Competitors (Intenseye, Protex AI, Voxel, viAct, Spot AI, Visionify, Everguard) all sell "existing CCTV + catalogue of detections + workflow". The open space is not another detector but evidence quality, measured reliability, energy-based risk context and site-owned, offline-capable deployment.

## Open questions (need the maintainer or a third party)

- Commercial intent: AGPL-3.0 code plus Ultralytics dependency is fine for open source; a closed commercial product needs an Ultralytics Enterprise licence or a different detector framework (see `10`).
- Real-site footage: no validation is possible without a partner site; every P1 capability is gated on it.
- Legal review: works-council/union consultation, DPIA and DPDP notices must be written by qualified counsel for a real deployment.

## Research completed (Phase B)

About 60 web searches and fetches on 5 November 2026 covering: US BLS CFOI 2024, OSHA Top 10 (FY2026 preliminary), HSE GB 2024/25, MSHA 2025, NIOSH FOG, ICHCA port data, OSHA emphasis programmes (warehousing, amputations), CSB hot work, EEI/CSRA HECA; EU AI Act (Art. 5, Annex III, Digital Omnibus timing), EU Machinery Regulation, ISO 45001 revision, ISO 10218-2:2025, IEC 61496-4-x, NFPA 72 VISD, ONVIF Profile M, Sparkplug ISO/IEC 20237, GDPR/ICO guidance, India OSH Code and DPDP Rules and s.7(i); competitors (Intenseye, Protex AI, Voxel, viAct, Everguard, Spot AI, Verdantix 2026 report, on-vehicle systems, pricing references); papers (detection, tracking, pose, video, TTC/near miss, construction CV, VLMs, spills, fall benchmarks); dataset licences (SODA, MOCS, LOCO, D-Fire, OmniFall, InHARD, Open Images, Objects365, ConstructionSite 10k). Full list in `14_SOURCE_REGISTER.md`.

## Decisions made

| Decision | Where |
|---|---|
| Wedge: indoor fixed-camera logistics and factory material-handling areas; vehicle–pedestrian conflicts as the headline | `00`, `12` §3 |
| Evolve the architecture (headless edge runtime first), do not rewrite the UI now | `07` §6 |
| Separate research and product model lines; no non-commercial data in the product line | `06` §1, `10` §6 |
| Never build emotion/fatigue/intoxication inference, face recognition or individual productivity scoring | `10` §3, `11` §6 |
| Unknown context never lowers risk; draft policies never apply reductions; confidence sets evidence quality, not risk | `07` §9, `intelligence/risk.py` |
| Unknown zone kinds are rejected rather than silently treated as generic zones | `intelligence/taxonomy.py` |

## Repository changes

All on local branch `research/platform-foundations`, uncommitted (the maintainer commits and pushes).

| Change | Files | Behaviour impact |
|---|---|---|
| Research documents 00–14, README and this log | `docs/product_research/` (new) | None |
| Hazard taxonomy | `intelligence/__init__.py`, `intelligence/taxonomy.py` (new) | None on its own |
| Risk policy engine with a draft default policy | `intelligence/risk.py` (new) | None on its own; optional `models/risk_policy.json` is read if a site creates it (not created) |
| Event-level validation metrics and CLI | `intelligence/event_metrics.py`, `scripts/evaluation/event_metrics.py` (new) | None |
| Optional zone `kind` | `inference/zone_monitor.py` | Zones without `kind` unchanged; unknown kinds raise `ValueError` |
| Assessment per incident, exposure tracking, escalation record | `inference/incident_manager.py`, `inference/tracker.py` | Incidents open/close exactly as before; alerts gain keys `hazard`, `severity`, `risk`, `evidence_quality`; `pedestrian_only`/`keep_clear` zones do not raise person-entry incidents and are not drawn as occupied |
| `risk_assessments` table and accessors | `database/database.py` | Additive table; `incidents`, `sessions`, CSV unchanged |
| Settings zone save keeps extra fields (audit finding D1) | `app/views/settings.py` | Same UI; `kind` survives an edit |
| Tests | `tests/test_intelligence.py` (new, 25 tests) | — |
| CI and lint config include the new package | `.github/workflows/ci.yml`, `pyproject.toml` | — |
| Docs | `docs/architecture.md` §5.1 and storage table, `CHANGELOG.md` (Unreleased), `README.md` docs table | — |

**Not changed:** `LICENSE`, `LICENSING_DECISION.md`, `THIRD_PARTY_NOTICES.md`, `models/best.pt`, `models/model_config.yaml`, `models/runtime_config.json`, detection/tracking/association logic, thresholds, training code, reports, datasets.

## Tests and results (Phase G, 5 November 2026)

| Check | Result |
|---|---|
| Full suite with weights, demo clips and processed data (`pytest -rs -q`) | **57 passed** (the 32 baseline tests, including model-backed integration tests, plus 25 new) |
| New unit tests alone (`tests/test_intelligence.py` + `tests/test_logic.py`) | 41 passed; the one pipeline-level new test skips automatically where Ultralytics is not installed (CI) |
| `ruff check .` | All checks passed |
| `python -m compileall` over all packages (CI step, now including `intelligence`) | Passed |
| `models/best.pt` SHA-256 after all work | `E9B2583D…CC3C7534`, unchanged |
| App in the browser (gallery → Track maintenance clip → Start → finish) | Gallery, player, live overlays, alert card and session view behave as before; no console or server errors. The run raised the same incident as the frozen 2 Nov demo run (W2, "Live rail", 0.48 s) and stored its assessment: `ZONE.ENTRY`, severity 3, exposure 7.5 s, LOW, evidence strong, policy `default-0.1` (draft). This added one demo session to the local `logs/incidents/incidents.db`, as any run does. |
| Throughput, interleaved A/B against `main` in a temporary worktree (`track_work_day.mp4`, 3 runs × 2 rounds each) | `main` warm runs 31.6–48.2 FPS; branch 33.6–46.6 FPS; ranges overlap and vary with GPU clock state, as already documented. `RiskEngine.assess` costs about 3 µs per call. **No measurable regression.** |
| Incidents produced on the demo clip (3 headless runs) | Identical to the frozen baseline: one `ZONE_INTRUSION`, worker 2, "Live rail", 0.48 s |

## Milestone M1: headless multi-camera runtime (5 November 2026)

### Fresh baseline before the milestone

Branch `research/platform-foundations`, uncommitted foundation work present (as listed above); **57 tests passed** (70 s), Ruff clean, `models/best.pt` hash unchanged. Hardware: Intel Xeon w5-2565X (36 logical CPUs), 63.6 GB RAM, NVIDIA RTX 2000 Ada 16 GB. No ffmpeg or RTSP server installed, so no live RTSP source was available.

### Findings from inspection

| Finding | Consequence |
|---|---|
| Ultralytics 8.4.197 gives each `BYTETracker` its own ID sequence starting at 1, and `reset()` restarts it | IDs collide across cameras by design, and a reset would reissue IDs within one camera session → worker identity is `(camera, session, id)` and the pipeline offsets IDs after a reset |
| `Pipeline` time is `frames / fps`; lost-track expiry counts frames | Explicit timestamps for live sources; time-based track reset after gaps |
| Session IDs have one-second resolution; `sessions` uses `INSERT OR REPLACE` | Two cameras starting in the same second would overwrite each other → session IDs include the camera ID and a random suffix |
| Incident IDs: 32 random bits per day | Collision would raise and lose the incident → retry |
| `Pipeline.finish()` closes at `frames / fps` | Optional end time |
| `inference/tracker.py` imported PyTorch at import time | Lazy import, so the runtime and CI need no PyTorch to import the pipeline |
| Profiling: single-frame inference 15.0 ms; batches of 2 and 4 cost 8.0 and 4.8 ms per frame; annotation 2.8 ms/frame | Batched backend by default; annotate only evidence frames |

### Decisions

Recorded in `15_HEADLESS_RUNTIME_ARCHITECTURE.md` §5 (D1–D9): threads in one process with a narrow backend interface; batched inference by default; per-camera tracker, pipeline and SQLite connection; drop-oldest bounded queues for live sources and blocking for offline files; monotonic time for durations and UTC at capture for records; track reset with ID continuity; additive tables and a separate default database; credentials only from environment variables with log redaction; no new dependency.

### Bugs found and fixed during the milestone

| Found by | Problem | Fix |
|---|---|---|
| First smoke run | Rate selection "since last kept frame" analysed 12.5 of a requested 15 FPS on a 50 FPS source | Due-time schedule (exactly 15.0) |
| Runtime tests | Status thread and `start()` wrote the same temporary status file at once | Lock around status writes |
| Benchmark harness | Batcher waited 5 ms for other cameras even with one camera | Wait only while more cameras are registered than frames batched; cameras release on stop |
| Review | `status` command crashed if the risk policy had failed to load | Guarded |
| Review | A file whose container over-reports its frame count would look like a mid-file error at its real end and reconnect forever | A failure on the first read after a reopen is the end of the file (unit test) |
| First benchmark | Every latency was a multiple of ~15.6 ms: `time.monotonic()` resolution on Windows/Python 3.11, also coarsening frame pacing | Runtime clock switched to `time.perf_counter()` (monotonic, high resolution); benchmark re-run |
| First benchmark | Shared backend, 4 cameras: 8.6 of 15 FPS each with 42 % drops was still reported STREAMING (thresholds 50 %/50 %) | DEGRADED below 80 % of target rate or above 20 % drops (configurable) |
| Second benchmark | 8 live cameras limited by CPU-side work, GPU at 28–50 % utilisation; `read()` costs 3.9 ms per 720p demo frame but `grab()` 0.4 ms, and most native frames are skipped by rate selection anyway | Skip decision made before reading; skipped frames are only grabbed (tested: a synthetic source draws only analysed frames; a loop restart on a skipped frame still resets tracks); benchmark re-run |

### Repository changes in M1 (all uncommitted)

| New | Purpose |
|---|---|
| `runtime/` (`__init__`, `__main__`, `config`, `sources`, `worker`, `inference`, `health`, `service`, `logs`) | Headless multi-camera runtime and CLI |
| `config/runtime.demo.yaml`, `config/runtime.example.yaml` | Runnable four-clip demo; documented site template (no credentials) |
| `tests/test_runtime.py` (36 tests), `tests/test_runtime_integration.py` (4 tests, real model) | Scenarios A–I, configuration, secrets, backends, exit codes |
| `scripts/benchmark/runtime_benchmark.py`, `reports/runtime/multicamera_benchmark.json` | Benchmark and its results |
| `docs/product_research/15_…`, `16_…`, `docs/runtime_getting_started.md` | Architecture, implementation reference, commands |

| Modified | Change |
|---|---|
| `inference/detector.py` | Shared model and injectable predict; `predict`, `predict_batch` |
| `inference/tracker.py` | Lazy detector import; frame timestamps; `reset_tracks` with ID continuity; `annotate`; `finish(t)`; evidence dir and listener |
| `inference/incident_manager.py` | Optional evidence dir and opened/closed listener |
| `database/database.py` | ID-collision retry; `close()`; `runtime_sessions`, `incident_context`, `camera_outages` |
| `tests/test_intelligence.py` | Pipeline test no longer needs PyTorch |
| `.gitignore`, `pyproject.toml`, `.github/workflows/ci.yml` | Local site configs ignored; `runtime` in lint and compile |
| `README.md`, `CHANGELOG.md`, `docs/README.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/product_research/README.md`, `07_…`, `12_…` | Pointers, roadmap after M1 |

**Not changed:** model weights and hash, thresholds, `models/runtime_config.json`, risk-policy status (still draft), training code, licence files, the dashboard's views and database.

### Tests and results (final, 5 November 2026)

| Check | Result |
|---|---|
| Full suite with weights, clips and data | **97 passed** in 200 s (original 57 + 36 runtime unit + 4 real-model integration) |
| CI simulation (PyTorch, Ultralytics and Streamlit imports blocked) | 77 passed, 2 integration modules skipped |
| `ruff check .`; byte-compilation incl. `runtime` | Pass; pass |
| `models/best.pt` SHA-256 | `E9B2583D…CC3C7534`, unchanged |
| Real-model equivalence | Runtime incidents identical to `process_video` for one camera and for three concurrent cameras (batched and shared) |
| Dashboard in the browser | Gallery and player render; recorded session, incidents and analytics shown; no server errors (no monitoring run, so the dashboard database was not touched) |
| Benchmark | `16` §14: 4 cameras × 15 FPS and 8 × 10 FPS pass the acceptance criteria on this machine (file simulation); 8 × 15 FPS does not and is reported DEGRADED |

## Milestone M2: real-world validation and ground-truth evaluation (5 November 2026)

Full results: [`18_VALIDATION_RESULTS.md`](18_VALIDATION_RESULTS.md). Protocol: [`17_ANNOTATION_PROTOCOL.md`](17_ANNOTATION_PROTOCOL.md).

### Baseline before the milestone

Ruff clean, `models/best.pt` `E9B2583D…CC3C7534`. The full-suite baseline run had 1 failure out of 97, in `test_g_h_cli_runs_headless_and_stops_on_signal`, while the footage-decode job was running. That test passed on 3 of 3 reruns, one of them under 12 CPU-load processes. The cause: the test asserted STREAMING, but under load a camera can legitimately fall below 80 % of its target rate and report DEGRADED. **Flaky test found and fixed:** the assertion now accepts {STREAMING, DEGRADED}.

### Findings

| Finding | Consequence |
|---|---|
| 20 footage files are 15 recordings from 12 source groups. The 5 demo files are copies of candidate recordings (dHash overlap 1.0; 0.77 for helmet_put_on). c00–c02 share a site, as do c09 and c10 | Each recording is scored once, and confidence intervals are clustered by source group |
| 5 recordings were used in earlier tuning (development); 10 are held out | Results are reported per split, never pooled without saying so |
| All files decode. c11 decodes 2579 of 2599 reported frames; c07 has 20 dark seconds | Recorded in `clip_manifest.csv` |
| The earlier unseen-footage "ground truth" was clip-level counts. It describes c11 as a meeting; the footage is forklift training | Not usable for event scoring; used only as a cross-check (violator counts agree on 9 clips) |
| Phase 1 audit: the false-alarm denominator was clip duration; there were no ignore or context regions, and no optional episodes; the tolerance ignored annotation uncertainty; matching could prefer the wrong episode; intervals assumed independence | All fixed in `intelligence/event_metrics.py`, backward compatible (`18` §7) |
| No human annotator was available in this session | Labels are an AI first pass marked `provisional`. Formal scoring is paused as the brief requires, and the human verification plan is `18` §9 |

### Decisions

- Labels were locked before the model was run.
- v1 is the primary result. Post-hoc corrections go into a new version (v1.1) reported beside it.
- Judgement calls are left to human reviewers.
- `ZONE.ENTRY` is scored only where zones exist, and those are demo zones.
- The requirement basis (evident or assumed) is a reported variant.
- No threshold, model or policy change.
- The benchmark used a separate clip set and changed no power settings.

### Results (provisional)

| Measure | Value |
|---|---|
| PPE held-out | 6 episodes: TP 3, FN 3, FP 2, 7 context alerts; precision 0.60 (0.23–0.88), recall 0.50 (0.19–0.81), 8.7 false alarms per monitorable h (1.0–31.3) in 0.231 h; **insufficient sample** |
| PPE development | 2 of 2, no false alarm, 0.013 h |
| Zone entry (development, demo zones) | 4 of 4, no false alarm, 20 s of footage; insufficient |
| Alert precision (PPE) | 5 of 15 scorable alerts were real violations |
| Latency | Median 0.53 s; held-out PPE 0.53, 5.9 and 10.8 s |
| Top failures | Rule fires where PPE is not required (8); look-alike headwear (dark hard hats, soft caps and hoods); heads of 8–13 px at the model input; incidents close after 1–4 s of 17–29 s violations |
| Runtime | 15 clips, 46,002 frames, no stuck camera. The evaluation-workload benchmark keeps 4 × 15 FPS and 8 × 10 FPS clean; 8 × 15 FPS passed only at higher GPU clocks |
| **Decision** | **Next capability phase not earned.** The next milestone is PPE reliability and verified measurement (`12`) |

### Bugs found and fixed during the milestone

| Found by | Problem | Fix |
|---|---|---|
| Baseline run | CLI test flaky under CPU load (above) | The assertion accepts DEGRADED |
| Error analysis (helmet_put_on duration) | The same-worker merge joined an `uncertain` event onto a violation | Merge only the same kind; test |
| Scoring v1 after locking v1.1 | `Path.with_suffix` turned `m2-provisional-v1.1` into `m2-provisional-v1.lock.json`, overwriting v1's lock | `lock_path()` uses the full name; verification checks the set name; test. v1 relocked with its original note: the combined hash matched the pre-run value `5FA81F00…` exactly, so no label file had changed |
| Error analysis (c01, roadworks_night) | Matching ignores worker identity, so latency and duration are swapped between workers | **Open (P0.2)**; counts unaffected here |
| Benchmark with `--clips` | The single-camera baseline step assumed demo `.mp4` names | Skipped with `--clips` (the reference stays in the earlier benchmark) |

### Repository changes in M2 (all uncommitted)

| New | Purpose |
|---|---|
| `intelligence/annotations.py` | Label format, validation, lock and verification, scoring inputs |
| `scripts/validation/` (`inventory.py`, `review_frames.py`, `annotator.py`, `labels_m2_provisional_v1.py`, `labels_m2_provisional_v1_1.py`, `run_evaluation.py`, `render_failures.py`, `probe_detections.py`) | Inventory, review, labelling, evaluation and error analysis |
| `tests/test_validation.py` (18 tests) | Label rules, scoring categories, locks, annotator smoke test |
| `reports/validation/` | Manifest, labels and locks, evaluation manifest, metrics, analyses, summary (images local only) |
| `reports/runtime/multicamera_benchmark_eval.json` | The evaluation-workload benchmark |
| `docs/product_research/17_…`, `18_…` | Protocol and results |

| Modified | Change |
|---|---|
| `intelligence/event_metrics.py` | Ignore and context regions, optional episodes, uncertainty-widened tolerance, monitorable-hour denominator, late detections, duration error, alert precision, cluster bootstrap; existing calls unchanged |
| `scripts/benchmark/runtime_benchmark.py` | `--clips`, `--out`, `--batched-only` |
| `tests/test_runtime.py` | CLI test accepts DEGRADED under load |
| `docs/product_research/README.md`, `12_…`, `CHANGELOG.md`, this log | Index, gate decision, changes |

**Not changed:** model weights and hash, thresholds, `models/runtime_config.json`, tracker configuration, risk-policy status (still draft), the dashboard and its database (`logs/incidents/incidents.db`).

### Tests and results (final, 5 November 2026)

| Check | Result |
|---|---|
| Full suite with weights, clips and data | **115 passed** in 194 s (the original 97 + 18 in `test_validation.py`) |
| CI simulation (PyTorch, Ultralytics and Streamlit blocked; whole `tests/` as in CI) | 99 passed, 3 skipped: the two integration modules, and the annotator smoke test without Streamlit |
| `ruff check .`; byte-compilation as in CI | Pass; pass |
| `models/best.pt` SHA-256 | `E9B2583D…CC3C7534`, unchanged |
| Dashboard database `logs/incidents/incidents.db` | Not written by M2; M2 used `reports/validation/eval_runs/*/eval.db`. **Corrected in M2.1:** this row first said "last written 2 November", from the main file's date alone. Its write-ahead log was last modified on 5 November at 09:54, before M2's evaluation run. It holds 151 incidents (the latest written at 05:48 that day) and the empty M1 runtime tables. So it was opened by M1-era code earlier that day, most likely when the dashboard or a run started, and it was not left untouched since 2 November |
| Label locks | v1 `5FA81F00…` verified after the lock-path fix; v1.1 `0BC85D6F…` |

## Milestone M2.1: safety reliability engineering and measurement integrity (5 November 2026)

Full record: [`19_SAFETY_RELIABILITY_ENGINEERING.md`](19_SAFETY_RELIABILITY_ENGINEERING.md). Future capability requirements: [`20`](20_FORKLIFT_PEDESTRIAN_REQUIREMENTS.md).

### Method

Before changing anything, the frozen model's per-frame tracker and head output was recorded for all 15 clips
(`record_traces.py`, 46,002 frames). The M2 post-detector code was copied unchanged into `scripts/validation/legacy_m2/`;
its hashes equal those in the M2 evaluation manifest. Replaying it on the traces reproduces M2's incident open times
exactly on 12 of 15 clips; the other three differ by fractions of a second (batched against single-frame numerics).
Every incident's closing path was then traced (`19` §1).

### Findings

| Finding | Consequence |
|---|---|
| Incidents closed on the first COMPLIANT vote; ambiguous headwear flips the vote (helmet votes from 0.30, no-helmet from 0.60) | Resolution now needs compliance held for `resolve_seconds` |
| The cooldown ran from closure: 302 VIOLATION frames of one worker in the 30 s after closure raised nothing | No cooldown after a confirmed resolution; re-observations after unknown ends are recorded |
| Exposure from timestamps: 15.3 s for 1 s of evidence (c02); the lost-track wait was added | Exposure bounded by observations; unobserved time reported |
| c00 false alarm: head box at y = 0 in every frame | Edge rule for heads |
| `close_incident` overwrote an operator's REVIEWED or FALSE_ALARM status | Fixed in the database layer |
| The old pipeline annotated a full frame on every violation frame | The new logic annotates only when an incident may open: post-detector cost 0.13–0.15 ms/frame against 0.33 ms (c01 replay) |
| Crossing a zone boundary briefly made the requirement ambiguous, so one entry raised a review and then a violation | Transient ambiguity waits for the debounced decision (found by a new test) |
| A lost assessment flag: re-assessment at closure reset `requires_review` | The assessor receives the incident id (found by a new test) |
| Linking after an unknown-outcome end had no time limit (linked an incident to a group ended 145 s earlier) | Linking only within the cooldown or while a re-observation continues (found in replay) |

### Decisions

D1–D11 in `19` §11. In short:
- the new logic is a layer above `IncidentManager`, whose API stays;
- an incident ends at its last observation;
- camera interruption ends incidents (the existing reconnection test encodes this);
- an unconfigured requirement is a review item;
- bursts batch notifications, never incidents;
- identity is excluded when inconsistent and falls back to time when unknown;
- lifecycle defaults were fixed before any diagnostic ran and not changed afterwards.

The soft-cap "resolution" seen on held-out data (`19` §12) is recorded as a hypothesis, not acted on.

### Results (diagnostic, provisional labels)

Detection is unchanged by design: 3 of 6 held-out, 2 false alarms. Median duration error falls from 7.38 s to 0.60 s
(the matcher) and 0.70 s (with the new logic). The worst case is now the soft-cap worker, at 29.1 s (classifier, not
lifecycle). The c01 white-suited worker's incident is 27.8 s against 29.4 s labelled; before it was 4.0 s. The
frame-edge false alarm is gone. 22 incidents give 15 notifications. With no PPE policy there are zero confirmed
violations. Per-variant tables are in `19` §8 and `reports/validation/m2_1_diagnostics/`.

### Repository changes in M2.1 (all uncommitted)

| New | Purpose |
|---|---|
| `inference/incident_lifecycle.py`, `intelligence/ppe_policy.py`, `intelligence/agreement.py` | Lifecycle, PPE requirements, inter-annotator agreement |
| `config/ppe_policy.example.json` | Documented example policy (draft, provisional entries) |
| `scripts/validation/record_traces.py`, `replay.py`, `legacy_m2/`, `m2_1_diagnostics.py`, `anchor_sheet.py`, `human_review.py`, `labels_m2_provisional_v1_2.py` | Traces, replay, frozen M2 logic, diagnostics, anchor frames, review workflow, v1.2 labels |
| `tests/test_lifecycle.py` (29), `tests/test_identity_matching.py` (11), `tests/test_human_review.py` (11) | New tests |
| `reports/validation/annotations/m2-provisional-v1.2/` + lock, `reports/validation/human_review/`, `reports/validation/m2_1_diagnostics/` | Anchored labels, review packages, diagnostics |
| `docs/product_research/19_…`, `20_…` | Engineering record; forklift–pedestrian requirements |

| Modified | Change |
|---|---|
| `inference/tracker.py`, `incident_manager.py`, `ppe_association.py`, `zone_monitor.py`, `config.py` | Lifecycle wiring, additive manager hooks, visibility, `crossing()`, four settings |
| `intelligence/event_metrics.py`, `annotations.py`, `taxonomy.py` | Identity-aware matching, schema 1.1, `work_area` zone kind |
| `database/database.py` | Five additive tables; operator status preserved |
| `runtime/config.py`, `service.py`, `worker.py`, `config/runtime.example.yaml` | `runtime.ppe_policy`, status, notification logging |
| `scripts/validation/annotator.py`, `run_evaluation.py` | Reviewer mode, anchors, zoom; `--identity`, no overwriting of results, worker paths |
| `app/theme.py` | Review alerts labelled |
| `.gitignore` | `reports/validation/traces/` |
| `docs/product_research/README.md`, `12_…`, `17_…`, `CHANGELOG.md`, this log | Index, roadmap status, protocol A3, changes |

**Not changed:**
- model weights and hash, thresholds, `models/runtime_config.json`;
- the risk-policy status (still draft);
- label sets v1 and v1.1 and their locks (byte-identical);
- M2 result files;
- the dashboard's database.

### Tests and results (final, 5 November 2026)

| Check | Result |
|---|---|
| Full suite with weights, clips and data | **166 passed** in 205 s: the original 115, unchanged, plus 51 new (29 lifecycle and policy, 11 identity matching, 11 review and agreement) |
| CI simulation (PyTorch, Ultralytics and Streamlit blocked; whole `tests/`) | 149 passed, 4 skipped (two integration modules, two Streamlit app tests) |
| `ruff check .`; byte-compilation as in CI | Pass; pass |
| `models/best.pt` SHA-256 | `E9B2583D…CC3C7534`, unchanged |
| Label locks | v1 `5FA81F00…` and v1.1 `0BC85D6F…` verify, with lock files byte-identical to before; v1.2 `34F4633D…` new |
| End-to-end runtime run (15 clips, new logic, no PPE policy) | 46,002 frames, no stuck camera; lifecycle tables populated; 0 confirmed helmet violations, 12 review notifications (`19` §8) |
| Dashboard | Starts (integration test); renders without exceptions in-process against a temporary database; review alerts labelled. Not opened in a browser, because that would add the new tables to the original database |
| Original database `logs/incidents/incidents.db` | Not written by M2.1: file times unchanged (main file 2 November; write-ahead log 5 November 09:54, before M2), and none of the new tables present |

## Camera view-change detection (5–6 November 2026)

Engineering record: [`21_CAMERA_VIEW_CHANGE_DETECTION.md`](21_CAMERA_VIEW_CHANGE_DETECTION.md). Same branch, uncommitted.
**Every camera movement in the tests is simulated; no physical camera was tested.**

### What was built

- `inference/view_monitor.py`: per-camera view checks (ORB + RANSAC similarity against a temporal-median reference;
  contrast-normalised blockage tests) and the view state machine (`INITIALIZING`, `VIEW_STABLE`,
  `VIEW_CHANGE_SUSPECTED`, `VIEW_CHANGED`, `BLOCKED`, `RECOVERING`, `VIEW_UNVERIFIED`) with 5 s confirmation and 3 s
  recovery.
- `runtime/view.py`: the per-camera guard: reference revisions, view events with snapshots, incident interruption,
  operator commands (`python -m runtime view list|accept|verify-zones|acknowledge`), status.
- Incidents end at the last reliable observation with `camera_view_changed`, `camera_scene_switched`, `camera_blocked`
  or `camera_view_unverified` (unknown outcome, never resolved, never position-linked afterwards); tracks reset.
- Zones of an untrusted or unverified view raise nothing; zone-dependent PPE requirements become review items.
- Connection and view health reported separately; dashboard Results › "Runtime cameras" reads `status.json`.

### Decisions

| Decision | Why |
|---|---|
| Geometry against a temporal-median reference, not frame differences | Moving workers and vehicles are not in the reference, so they cannot move the fit |
| No automatic reference update; operator `accept` only | A silent update would legitimise a wrong view |
| No automatic zone compensation (transform stored, not applied) | A similarity fitted on background features does not model the floor plane |
| Checks inline in the processing thread every 0.5 s | 5–16 ms twice a second; a separate thread was not justified |
| Before any reference: std ≥ 12 and ≥ 40 features to seed one | An obstructed image must never become the reference (see the fixed failure below) |
| After a startup blockage, nothing is analysed until a reference exists | Bootstrap trust only applies when nothing has gone wrong |
| A suspicion starting at a reconnect or loop restart is untrusted | The stream may have come back on another view |
| Fixed-camera demo kept at default thresholds; hand-held clips moved to `config/runtime.demo_handheld.yaml` (blockage only, no zones, monitoring "partial") | The detector is not weakened for unsuitable footage; an earlier 0.06 relaxation was withdrawn |
| Document renumbered 21 | `20` was the forklift requirements document |

### Problems found and fixed during the milestone

| Problem | Fix |
|---|---|
| A camera covered from the first frame recorded no view event: before a reference existed only "uniform image" counted as blocked, so a covered lens with a light leak looked observable (it escaped becoming the reference only because it had too few features to fit) | Absolute floors before a reference (std ≥ 12 and ≥ 40 features); the first visible check starts the reference window; no analysis until the reference exists |
| An incident raised on obstructed startup frames had no cap (no reliable observation at all) | Capped at its own opening (exposure = confirmation time) |
| Evidence streaks carried across state changes (a stale pre-blockage streak could confirm an immediate change) | Every transition starts a fresh streak |
| A reconnect to another view was analysed for up to 5 s | Suspicion at a stream gap is untrusted |
| Repeated check failures ended incidents without a view event | Recorded as `camera_view_unverified`, closed when checks work again |
| A camera that never settles kept using its zones | Zones off while unsettled |
| `dx`/`dy` signs inverted | Fixed and tested |
| "database is locked" when several cameras opened a new database at once (pre-existing) | `PRAGMA journal_mode=WAL` retried briefly |
| The first overhead benchmark compared different workloads (hand-held clips were suspended) | Re-run on the fixed-view clip only; runs rejected unless every camera stayed `VIEW_STABLE` |

### Results

| Check | Result |
|---|---|
| Full suite | **211 passed** (166 before + 45 new), 0 skipped |
| CI simulation | 193 passed, 5 skipped |
| View tests, three consecutive runs | 45/45 each time |
| Ruff, byte-compilation | Pass |
| Paired benchmark (1/4/8 cameras, live and throughput, 2 repeats) | All 24 runs clean (all cameras `VIEW_STABLE`, 0 frames withheld). Overhead within run-to-run noise except 8 cameras saturated: −1.9 % and −1.7 % throughput; ~+100 MB RSS fixed; GPU clock varied 210–2130 MHz (power management, not changed) |
| `models/best.pt` | `E9B2583D…CC3C7534`, unchanged |
| Original database, evaluation artifacts, zones (`models/runtime_config.json`) | Unchanged |

### Changed files

New: `inference/view_monitor.py`, `runtime/view.py`, `config/runtime.demo_handheld.yaml`,
`scripts/benchmark/view_monitor_benchmark.py`, `reports/runtime/view_monitor_benchmark.json`,
`tests/test_view_monitor.py`, `tests/test_view_monitor_footage.py`, `tests/view_scenes.py`,
`docs/product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md`.
Modified: `inference/incident_lifecycle.py`, `inference/tracker.py`, `database/database.py`, `runtime/config.py`,
`runtime/worker.py`, `runtime/health.py`, `runtime/__main__.py`, `app/views/insights.py`, `config/runtime.demo.yaml`,
`config/runtime.example.yaml`, `README.md`, `CHANGELOG.md`, `docs/architecture.md`, `docs/runtime_getting_started.md`,
`docs/product_research/README.md`, `12_ROADMAP_AND_PRIORITIZATION.md`, this log.

## Milestone M3: verified safety validation and industrial pilot readiness (6 November 2026)

Documents: [`22`](22_INDUSTRIAL_DATA_ACQUISITION_PLAN.md), [`22A`](22A_SITE_DATA_COLLECTION_CHECKLIST.md),
[`23`](23_INDUSTRIAL_PILOT_READINESS.md) (status matrix, policy review, evaluation audit, gates),
[`23A`](23A_PHYSICAL_CAMERA_ACCEPTANCE_TEST_PLAN.md), [`24`](24_FORKLIFT_PEDESTRIAN_RESEARCH.md),
[`25`](25_M3_EXECUTIVE_DECISION_REPORT.md). Same branch, uncommitted. No model retrained, no threshold changed, no GPU
experiment, no dataset downloaded.

### Baseline (frozen before any M3 change)

`reports/validation/m3_baseline/baseline_record.json` (written by `scripts/validation/freeze_baseline.py record`):
- HEAD `6aa177e`; the uncommitted M1–M2.1 and view-change work listed above;
- `models/best.pt` `E9B2583D…CC3C7534` (matches `model_config.yaml`);
- 264 protected files hashed (`reports/validation`, `reports/runtime`, model and runtime config);
- label locks v1 `5FA81F00…`, v1.1 `0BC85D6F…`, v1.2 `34F4633D…`, all verifying;
- database DDL hash `05713046…` (14 tables; versioning is additive DDL only, no `user_version`);
- dashboard database files: sizes and times only, never opened;
- risk policy `default-0.1` draft; no PPE policy in use;
- benchmark hashes.

Tests: **211 passed** in 338 s (`tests_baseline.txt`).

### Findings

| Finding | Consequence |
|---|---|
| Most of the M2.1 list was genuinely implemented and tested (lifecycle, policy engine, identity-aware matching, grouping, visibility) | Status matrix in `23` §1 records it per item, with what is missing |
| A **provisional** PPE entry produced `confirmed_violation` incidents | Fixed: review item, category `requirement_not_confirmed` |
| The time-only matcher ignored camera and session | Fixed; tests for pooled multi-camera input |
| Operator decisions had no record of who, when or why | Additive `incident_reviews` audit; CLI for headless sites |
| The protocol let independent reviewers see the first pass (§2) | Amendment A6: independent reviews start empty |
| Treating every non-"resolved" end as censored would have dropped 7 of 9 valid matches (the protocol also ends episodes when a worker leaves view) | Duration error kept over all matches, broken down by end outcome; **premature resolutions** counted instead. It flags the known soft-cap case (c01-E03) on the stored M2.1 run |
| The earlier 10 monitorable camera-hour minimum cannot bound an acceptable false-alarm rate | Per-hazard minimums in `22` §2.4 (≥ 100 h and ≥ 100 episodes per hazard for Gate C) |
| Running the existing test suite writes evidence JPEGs into `logs/incidents/evidence/` (folders `S20261106-…` appeared during the baseline run): some pre-existing tests use a temporary database but the default evidence folder | Pre-existing behaviour, not changed in M3 (recorded as a follow-up). The dashboard database files keep their 2 and 5 November sizes and times (verified) |

### Decisions

| Decision | Why |
|---|---|
| Keep `reviewer_A/B` (never started) unchanged; new packages `reviewer_1/2` | No overwriting; separately identifiable packages |
| Only `confirmed` PPE entries create violations; document status still reported | Draft rules must never look like approved policy; site pilots can confirm entries before the document is formally approved |
| Historical summaries get only marked notes (`<!-- M3 note … -->`), verified to strip back to the original bytes | The brief asked for updated summaries; the record must stay intact |
| No threshold, lifecycle or matcher setting changed after seeing any score | The labels remain the held-out evaluation set |
| Forklift–pedestrian: specification only | Gate not met (`24` §11) |

### Repository changes in M3 (all uncommitted)

| New | Purpose |
|---|---|
| `docs/product_research/22`, `22A`, `23`, `23A`, `24`, `25` | Plans, readiness, research, decision report |
| `reports/validation/human_review/reviewer_1/`, `reviewer_2/`, `M3_REVIEW_WORKFLOW.md`, `ADJUDICATION_M3.md`, `review_progress.csv` | Review packages and workflow |
| `reports/validation/m3_baseline/`, `reports/validation/M3_VALIDATION_STATUS.md` | Baseline record and status |
| `scripts/validation/freeze_baseline.py`, `scripts/validation/camera_acceptance.py` | Baseline verifier; camera acceptance harness |
| `tests/test_evaluation_integrity.py` (22), `tests/test_policy_safety.py` (9), `tests/test_camera_acceptance.py` (5), `tests/test_baseline_record.py` (2) | New tests |

| Modified | Change |
|---|---|
| `intelligence/event_metrics.py` | Scope in both matchers; end outcomes; premature resolutions; same-group duplicates; `summarise()` |
| `intelligence/agreement.py` | Hazard category, zone, event kind, confidence, per-clip, clip bootstrap |
| `intelligence/annotations.py` | Optional `confidence` validated |
| `intelligence/ppe_policy.py` | Docstring: provisional entries give review items |
| `inference/tracker.py` | `requirement_not_confirmed`; violations only from confirmed entries |
| `database/database.py` | `incident_reviews`; `set_status(reviewer, note, source)`; `reviews()` |
| `runtime/__main__.py` | `incident list|review` |
| `app/views/insights.py` | Optional reviewer and reason; review history |
| `scripts/validation/human_review.py` | Packages 1/2, manifests, instructions, `check`, `export`, extended worksheet |
| `scripts/validation/annotator.py` | Confidence field; notes for the adjudicator |
| `scripts/validation/run_evaluation.py` | Uses `summarise()`; per-camera/site tables; end outcomes; group ids |
| `scripts/validation/m2_1_diagnostics.py` | Comment only (variant C semantics since M3) |
| `tests/test_human_review.py` | Package names A/B → 1/2 in existing tests (the tool's packages were renamed); 9 new tests |
| `docs/product_research/12`, `17` (A6), `20` (gate status), `README.md`, this log; `docs/architecture.md`, `docs/runtime_getting_started.md`, `CHANGELOG.md` | Documentation |
| `reports/validation/validation_summary.md`, `reports/validation/human_review/README.md` | Marked M3 notes only |

**Not changed:** model weights and hash; thresholds; `models/runtime_config.json`; tracker configuration; risk policy
(draft); label sets v1, v1.1 and v1.2 and their locks; every M2 and M2.1 result file; benchmarks; the dashboard database.

### Tests and results (final, 6 November 2026)

| Check | Result |
|---|---|
| Full suite with weights, clips and data | **258 passed** in 361 s: the 211 baseline tests plus 47 new (22 evaluation integrity, 9 policy and audit, 5 camera harness, 9 human review, 2 baseline verifier). The 4 existing human-review tests that named the old packages were updated from `reviewer_A/B` to `reviewer_1/2` |
| CI simulation (PyTorch, Ultralytics and Streamlit blocked; whole `tests/`) | 239 passed, 6 skipped (two integration modules, four Streamlit tests) |
| `ruff check .`; byte-compilation of all packages | Pass; pass |
| Re-scoring the stored M2 run and the M2.1 runtime run with the M3 scorer (scratch output) | Every previously reported metric identical; only new fields added |
| `freeze_baseline.py verify` | `ok: true` — model `E9B2583D…CC3C7534` unchanged; label locks unchanged and verifying; no protected file changed or missing; 2 files with marked M3 notes only (strip back to the original bytes); 48 files added; dashboard database files unchanged |
| Dashboard incident review | Exercised in-process against a temporary database (new test); the dashboard was not opened in a browser, because that would add the new table to the original database |
| Physical cameras, human reviewers | None available: **BLOCKED**, not simulated |

## What is not verified

- **Ground truth:** the M2 labels are a provisional AI first pass with no independent human review, so every M2 number is provisional (`18` §9 lists the verification needed).
- **M2.1:** every before/after figure is diagnostic, on the same provisional labels. The human review is prepared but not done. No real PPE policy exists. Re-association by position and the lifecycle defaults have not been tested on deployment footage.
- Typed zone kinds other than `restricted` have been exercised only with scripted detections in tests, not on real footage.
- Escalations are recorded in the database but not shown in the UI or delivered as notifications (M3).
- CI on GitHub has not run on this branch (nothing pushed).
- **Runtime:** RTSP streaming against a real camera; physical multi-camera deployment; long soak tests (runs lasted seconds to minutes); a native crash (OpenCV/CUDA) would stop all cameras and needs a service manager to restart the process; the dashboard reads `status.json` (Results › "Runtime cameras") but not the runtime databases.
- **M3:** the review packages have not been opened by any reviewer; the camera acceptance harness has run only on a
  generated file (its self-test); the pilot gates, data minimums and forklift–pedestrian specification are plans; the
  incident review audit records a self-declared reviewer name (no authentication).
- **Camera view-change detection:** no physical camera was moved, covered, zoomed or re-aimed; no RTSP stream, IR day/night switch, rain, condensation or real vibration was tested; thresholds were set on simulations and demo clips only. The overhead was measured on one workstation whose GPU clock varied widely.

## M3 re-audit (6 November 2026, later the same day)

The M3 brief was issued again. Instead of redoing the milestone, its claims were checked against the code and data.

| Claim | Check | Result |
|---|---|---|
| Baseline intact | `freeze_baseline.py verify`; `Get-FileHash models/best.pt` | `ok: true`; `E9B2583D…CC3C7534`; locks verify; incidents database last written 2 Nov |
| Review packages empty and blinded | Read `reviewer_1` labels and `package.json` | No events, intervals, annotators or model output; `review_complete: false` |
| Provisional rules never confirm a violation | `inference/tracker.py` `classify` | Holds: entry status other than `confirmed` gives `requirement_not_confirmed` |
| No physical-camera results claimed | Search for `camera_acceptance` result folders | None exist |
| Different cameras never match | `intelligence/event_metrics.py` `_scope_ok` | **Gap:** a missing `camera`/`session` was a wildcard even in pooled multi-camera input, so an unnamed prediction could match another camera's episode. The docstring said pooled inputs "must" carry `camera`, but nothing enforced it |

**Fix:** `_check_pooled_scope` in both matchers refuses inputs that name more than one camera (or session) when any item
omits it. Single-camera per-clip scoring, the documented fallback, is unchanged. Tests:
`test_pooled_inputs_with_an_unnamed_item_are_refused` (4 cases), `test_one_camera_with_unnamed_labels_still_uses_the_fallback` (2).

**Results:** full suite **264 passed** (258 + 6); `ruff` clean on changed files. Re-scoring the stored M2 run
(time-only) and the M2.1 runtime run (identity-aware) into a scratch folder reproduced every stored metric; only
`scored_utc` and scoring-code hashes differ. No stored result, label set or lock was touched.

**Status unchanged:** Gate A met; Gate B BLOCKED (two reviewers + adjudicator, partner site, physical cameras, site
safety lead, licensing decision). Forklift–pedestrian: specification only.
