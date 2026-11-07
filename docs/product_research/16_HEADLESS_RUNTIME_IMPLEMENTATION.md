# 16 — Headless multi-camera runtime: implementation, operation and results

Date: 5 November 2026. Design and concurrency decisions: [15_HEADLESS_RUNTIME_ARCHITECTURE.md](15_HEADLESS_RUNTIME_ARCHITECTURE.md). Practical commands: [docs/runtime_getting_started.md](../runtime_getting_started.md).

## 1. Status in one paragraph

SafeSight now runs as a headless process (`python -m runtime run --config …`) that monitors several configured cameras independently of the Streamlit dashboard. Each camera has its own capture thread, bounded queue, processing thread, tracker, session, health state and SQLite connection; the model is loaded once and shared through a batched inference thread. Through the runtime, the existing pipeline produces **exactly the same incidents** as the original single-camera path on the demo clips, for one camera and for three concurrent cameras (integration tests). **What this does not show:** no RTSP stream was available, so RTSP streaming is implemented but only its failure paths are tested; all "cameras" were video files on one workstation; nothing here is a real-site validation, and the risk policy remains a draft.

| Claim | Evidence | Status |
|---|---|---|
| Starts headless, no browser, no Streamlit imported | CLI subprocess tests; `process.ui_loaded = false` in status; static import check | Verified |
| Several independent cameras, correct camera/site attribution | Scenario B tests (synthetic and real model) | Verified with files |
| Failure of one camera does not affect others | Scenario C: never-opening, missing, corrupt, refused-RTSP and missing-credential cameras alongside a healthy one | Verified |
| Reconnection without duplicate incidents or ID reuse | Scenario D | Verified with a fault-injecting source |
| Bounded memory under backpressure | Scenario E: queue never above its bound; drops counted; DEGRADED reported | Verified |
| Concurrent persistence without loss or duplication | Scenario F: 6 cameras, ~120 concurrent incidents; 8 raw writers × 150 rows; `integrity_check ok` | Verified |
| Graceful shutdown on signal | Scenario G: in-process and CTRL_BREAK on a subprocess; exit 0; sessions closed | Verified |
| Original app and tests unchanged | Full suite (section 13) | Verified |
| RTSP streaming from a real camera | No source available | **Not verified** |
| Real multi-camera site deployment | — | **Not done** |

## 2. Modules

| Module | Responsibility |
|---|---|
| `runtime/__main__.py` | CLI: `run`, `validate`, `status`; signal handling; exit codes |
| `runtime/config.py` | Strict YAML/JSON validation, defaults, path resolution, per-camera pipeline settings |
| `runtime/sources.py` | `FrameSource` interface; `file`, `rtsp`, `synthetic`; credential resolution from environment |
| `runtime/worker.py` | `CameraWorker`: capture thread, `FrameQueue`, processing thread, reconnection, track reset, events, session finalisation |
| `runtime/inference.py` | Backends: `batched` (default), `shared`, `per_camera`, `null` |
| `runtime/health.py` | Camera states, rolling metrics, DEGRADED derivation, process CPU/RAM/GPU metrics |
| `runtime/service.py` | `Runtime`: start, status loop, graceful stop |
| `runtime/logs.py` | Console and rotating file logs; redaction of URL credentials and registered secrets |
| `config/runtime.demo.yaml`, `config/runtime.example.yaml` | Runnable four-clip demo; documented site template |

**Small, backward-compatible changes to existing code** (the dashboard calls everything exactly as before):

| File | Change |
|---|---|
| `inference/detector.py` | `Detector(model=…, predict=…)` to share a model and route its calls; `predict()` and `predict_batch()` |
| `inference/tracker.py` | Imports the detector lazily (the runtime and CI need no PyTorch to import the pipeline); `process(frame, t=None)`; `reset_tracks(t)` with ID continuity; `annotate=False` draws only evidence frames; `finish(source, t=None)`; `evidence_dir` and `listener` passed through |
| `inference/incident_manager.py` | Optional `evidence_dir`; optional `listener` for opened/closed events |
| `database/database.py` | Incident-ID collision retry; `close()`; additive tables `runtime_sessions`, `incident_context`, `camera_outages` and their accessors |
| `.gitignore` | `config/*.local.yaml|yml|json` |
| `pyproject.toml`, `.github/workflows/ci.yml` | `runtime` package in lint and byte-compilation |

## 3. Startup procedure

1. `rconfig.load()` validates the whole configuration (unknown keys, ranges, unique IDs, sites, zones and kinds, source options, RTSP URLs without credentials). Invalid → exit code 2 with the reason.
2. Logging starts (console + `runtime.log`), with redaction.
3. The risk policy is loaded (`runtime.risk_policy`, else `models/risk_policy.json`, else the draft example); a draft policy is logged as a warning on every start.
4. The inference backend loads the model once and warms it up. Missing weights → exit code 3 before any camera starts.
5. Each enabled camera's worker starts; a camera that cannot open retries with back-off and never blocks the others.
6. `status.json` is written immediately and every `status_interval_s`.

## 4. Configuration reference

```yaml
runtime:
  database: logs/runtime/incidents.db     # same schema as the dashboard database
  evidence_dir: logs/runtime/evidence
  status_file: logs/runtime/status.json
  log_file: logs/runtime/runtime.log      # null: console only
  log_level: INFO                         # DEBUG | INFO | WARNING | ERROR
  status_interval_s: 2
  risk_policy: null                       # path to an approved site policy
  pipeline_config: models/runtime_config.json   # thresholds and dashboard zones (read only)
inference:
  backend: batched                        # batched | shared | per_camera | null
  weights: models/best.pt
  imgsz: 640
  device: auto
  max_batch: 8
  batch_wait_ms: 5                        # how long the batcher waits for other cameras' frames
  timeout_s: 30                           # a camera's wait for a result before the frame counts as failed
sites: [{id: plant-01, name: Plant 1}]
defaults:                                 # applied to every camera, overridable per camera
  processing: {max_fps: 10, queue_size: 2, annotate: false}
  reconnect: {max_attempts: 10, initial_delay_s: 1, max_delay_s: 30}   # max_attempts 0: retry forever
  health: {degraded_ratio: 0.8, max_drop_ratio: 0.2, stall_s: 5, window_s: 10, warmup_s: 5}
cameras:
  - id: dock-01                           # unique; letters, digits, '-' and '_'
    name: Loading dock 1
    site: plant-01
    enabled: true
    source: {type: rtsp, url: "rtsp://192.0.2.12:554/stream1", username_env: SAFESIGHT_DOCK01_USER, password_env: SAFESIGHT_DOCK01_PASS}
    zones: [{name: Dock edge, kind: edge, polygon: [[0.1, 0.8], [0.9, 0.8], [0.9, 0.95], [0.1, 0.95]]}]
    # or zones_from_app: <camera view>     reuse zones drawn in the dashboard
    overrides: {cooldown_seconds: 60}     # person_conf, ppe_conf, no_helmet_conf, confirm_seconds, cooldown_seconds, lost_track_seconds
```

Thresholds default to the dashboard's saved settings, so the runtime and the app use the same validated values (no-helmet 0.60). Per-camera overrides are allowed; `validate` flags a no-helmet threshold that differs from the validated one.

## 5. Camera sources

| Type | Options | Behaviour | Verified |
|---|---|---|---|
| `file` | `path`, `loop`, `realtime` (default true) | `realtime: true` replays at the file's frame rate and drops the oldest frame under load (camera simulation); `false` reads as fast as processing allows and blocks instead of dropping (reproducible evaluation). A read error mid-file reopens and resumes at the same position; a loop restart resets tracks | Yes |
| `rtsp` | `url`, `username_env`, `password_env`, `transport` (tcp/udp), `open_timeout_s`, `read_timeout_s` | OpenCV FFmpeg backend with open and read timeouts; credentials read from environment variables at each connect, URL-encoded, registered for redaction; missing variables are a fatal camera error (no pointless retries) | Failure paths only: connection refused, missing credentials. **No live RTSP stream tested** |
| `synthetic` | `fps`, `width`, `height`, `frames`, `pattern`, `period`, `realtime`, `faults` | Deterministic test pattern; fault injection for tests | Yes (tests) |

**Adding a type** (for example ONVIF): subclass `FrameSource`, declare `OPTIONS`/`REQUIRED`, implement `open`, `read` (return `None` at end of stream, raise `SourceError` on failure; `fatal=True` when retrying cannot help), `close`, `describe` (no credentials), and register it in `SOURCE_TYPES`. ONVIF discovery would resolve a device's stream URI and hand it to the RTSP implementation.

## 6. How to add a camera

1. Add an entry under `cameras:` with a new `id`, `name`, `site` and `source`.
2. Draw zones in the dashboard and reference them with `zones_from_app`, or list them with fractions of the frame and a `kind`.
3. For RTSP, set the two environment variables in the service's environment.
4. `python -m runtime validate --config …`, then restart the runtime. (Hot reload is not implemented.)

## 7. Logging

- Console and `runtime.log` (rotating, 5 × 5 MB), one line per event, logger name per camera (`safesight.runtime.camera.<id>`).
- Every incident and escalation is logged at WARNING with camera, hazard code, risk level, zone and the camera-scoped worker reference.
- Redaction is applied to the fully formatted line, including tracebacks: `scheme://user:pass@` becomes `scheme://***@`, and every credential value read from the environment becomes `***`.

## 8. Health monitoring

| State | Meaning | `monitoring` |
|---|---|---|
| `CONNECTING` | First connection attempts | no |
| `STREAMING` | Frames read and processed adequately | yes |
| `DEGRADED` | Streaming but processed rate < 80 % of target, > 20 % of frames dropped, nothing processed for 5 s, or persistence errors | partial |
| `RECONNECTING` | Stream lost; back-off in progress | no |
| `STOPPED` | Shutdown or end of a finite file | no |
| `ERROR` | Retries exhausted, missing credentials, or the pipeline failed 5 frames in a row | no |
| `DISABLED` | `enabled: false` in configuration | no |

`status.json` holds, per camera: state and reason, source/target/read/processed FPS, frames read/processed/skipped/dropped/queued and the queue maximum, inference/processing/end-to-end/incident latency percentiles, reconnects, connection attempts, errors, persistence errors, incidents, escalations, last frame and last processed frame (UTC), uptime, connected time and availability; and for the process: CPU %, RSS, threads, system CPU, GPU utilisation/memory/clock (nvidia-smi), PyTorch CUDA memory, the inference backend's model latency and mean batch size, and the risk policy version and status. `python -m runtime status` prints it and reports a stale file or dead process as **NOT RUNNING**, so a stopped runtime can never look like healthy cameras with zero incidents.

Coverage gaps are also persisted: each outage (open failure or lost stream) is a row in `camera_outages` with UTC start and end.

## 9. Persistence and identity

| Table | Contents |
|---|---|
| `incidents`, `risk_assessments`, `sessions` | Unchanged formats; `sessions.source` is `camera:<id>` for runtime sessions |
| `runtime_sessions` | Camera, name, site, source type, sanitised source, UTC start/end, end reason, frame counters, reconnects, policy version and status |
| `incident_context` | Incident → session, camera, site, worker reference `camera/session/W<n>`, UTC open/close (capture time of the frame), pipeline times |
| `camera_outages` | Coverage gaps per camera and session, UTC |

Worker identity is `(camera_id, session_id, worker_id)`. Raw tracker IDs restart at 1 for every camera (Ultralytics 8.4 behaviour) and are never reused within a session: after a track reset the pipeline offsets new IDs past every ID already issued.

## 10. Frame selection and backpressure

Capture advances through every frame, and keeps frames on a due-time schedule so the analysed rate averages `max_fps` exactly (a "since last kept frame" rule would turn 15 of 50 FPS into 12.5 FPS; fixed after the first smoke run). The keep/skip decision is made before reading, so a skipped frame is only grabbed (`VideoCapture.grab()`, about 0.4 ms for a 720p demo frame) instead of read and converted (about 3.9 ms); a loop restart that falls on a skipped frame is carried to the next analysed frame. Kept frames go to a bounded queue: drop-oldest for live sources, blocking for offline files. Counters satisfy `read = processed + skipped_by_rate + dropped_backpressure + queued` (tested). Dropping happens only before inference; every state change and incident is committed synchronously before the next frame.

## 11. Shutdown

SIGINT, SIGTERM or SIGBREAK (Ctrl+Break on Windows) set a stop flag. Capture threads stop and release their sources; processing threads process what is still queued (at most `queue_size` frames), close open incidents at the last processed time, save the session, end open outages and close their database connections; the inference backend stops; a final `status.json` shows every camera `STOPPED`; the log ends with `shutdown complete`; exit code 0. Threads are joined with a 20 s limit and are daemon threads, so nothing outlives the process. A second signal exits immediately.

## 12. Security

- No credentials in configuration files; URL userinfo and credential-like query parameters are rejected; site configurations go in git-ignored `config/*.local.yaml`.
- Redaction of all log output; sources describe themselves without credentials; `status.json` contains sanitised source descriptions only.
- Video and evidence stay on the machine; the only network connections are to configured cameras; `YOLO_OFFLINE=true` is set by the CLI.
- No output to machinery, PLCs or safety systems exists.
- **Not yet implemented:** file-system permissions on `logs/runtime/` beyond the user profile defaults, encryption of evidence at rest, retention enforcement, authentication for any future status API (roadmap M3).

## 13. Tests

| Scenario | Tests | Data |
|---|---|---|
| A single camera | `test_a_single_camera_end_to_end`; `test_a_single_camera_matches_the_original_pipeline` (real model: identical incidents to `process_video`) | synthetic; demo clip |
| B multiple cameras | `test_b_cameras_are_independent_and_attributed`; `test_b_concurrent_cameras_match_their_single_camera_results[batched, shared]` (real model, three concurrent clips, identical incidents per camera) | synthetic; demo clips |
| C camera failure | `test_c_failed_cameras_do_not_affect_healthy_ones` | never-opening, missing, corrupt, refused RTSP, missing credentials |
| D reconnection | `test_d_reconnection_resets_tracks_without_duplicate_incidents` | fault-injecting realtime source |
| E backpressure | `test_e_backpressure_is_bounded_and_counted`, `test_e_offline_sources_block_instead_of_dropping`, `test_rate_selection_keeps_the_configured_average` | 200 FPS source, 20 ms detector |
| F database concurrency | `test_f_concurrent_cameras_store_every_event_once`, `test_f_parallel_writers_with_separate_connections`, `test_incident_id_collisions_are_retried` | 6 cameras; 8 writers |
| G shutdown | `test_g_shutdown_during_monitoring_is_clean`; `test_g_h_cli_runs_headless_and_stops_on_signal` | in-process; subprocess with CTRL_BREAK |
| H browser independence | `test_g_h_cli_runs_headless_and_stops_on_signal`, `test_h_cli_monitors_demo_cameras_without_a_browser` (real model), `test_runtime_package_never_imports_the_ui` | subprocess |
| I existing functionality | the original 57 tests, unchanged | — |
| Configuration and secrets | 13 invalid-configuration cases, shipped configurations, credential resolution and redaction, exit codes, stale status | — |

Results: see `PROGRESS_LOG.md` (final run) and section 14.

## 14. Performance

**Source:** `reports/runtime/multicamera_benchmark.json` (final run 5 November 2026, 04:07 UTC), produced by `scripts/benchmark/runtime_benchmark.py`. **Machine:** NVIDIA RTX 2000 Ada 16 GB, Intel Xeon w5-2565X (36 logical CPUs), 63.6 GB RAM, Python 3.11.18, PyTorch 2.14.1+cu126, M5 (YOLO26n) at 640 px.

**What these numbers are:** video files replayed on one workstation to **simulate** concurrent cameras (demo clips: 720p at 50, 30, 25 and 24 FPS, looping; cameras 5–8 reuse clips 1–4). Each configuration ran in its own process; rates are measured over a 20 s window after a 6 s warm-up. **No RTSP stream and no physical camera were involved.** Each figure is one 20 s window, not a soak test.

**GPU clock caveat:** the GPU stayed far below its 3,105 MHz maximum (mean SM clock 407–1,789 MHz across runs) and at 25–42 % utilisation; the original single-camera path measured 24.3 to 54.8 FPS across three benchmark sessions on the same day (the lowest value in each session is its first, cold run). Treat differences under about 15 % as noise.

### 14.1 Live simulation (paced at each clip's frame rate, analysis capped at `max_fps`)

| Backend | Cameras × target | Processed FPS per camera (mean, range) | Drops | Inference p50 / p95 (ms) | End-to-end p50 / p95 (ms) | Incident latency max (ms) | Process CPU | RSS | CUDA peak | States |
|---|---|---|---|---|---|---|---|---|---|---|
| batched | 1 × 15 | 15.0 | 0 % | 26.6 / 34.5 | 28.6 / 38.0 | 67 | 79 % | 1.40 GB | 87 MB | STREAMING |
| batched | 2 × 15 | 15.0 (14.94–14.99) | 0 % | 41.8 / 71.9 | 46.6 / 79.1 | 149 | 116 % | 1.51 GB | 102 MB | STREAMING |
| **batched** | **4 × 15** | **15.0 (14.89–14.99)** | **0–0.3 %** | 48.6 / 83.0 | **61.6 / 106.9** | **150** | 162 % | 1.70 GB | 130 MB | **STREAMING** |
| batched | 8 × 15 | 11.6 (10.18–12.88) | 14–32 % | 74.7 / 121.7 | 166.7 / 240.6 | 311 | 248 % | 2.12 GB | 186 MB | **DEGRADED** on the 4 cameras above 20 % drops; STREAMING on the other 4 |
| **batched** | **8 × 10** | **10.0 (9.89–10.09)** | **0–0.5 %** | 75.9 / 117.6 | **88.9 / 177.3** | 348 | 230 % | 2.08 GB | 186 MB | **STREAMING** |
| shared | 1 × 15 | 15.0 | 0 % | 25.5 / 37.7 | 27.2 / 39.5 | 90 | 69 % | 1.41 GB | 87 MB | STREAMING |
| shared | 2 × 15 | 15.0 (14.95–15.0) | 0 % | 29.7 / 54.1 | 32.9 / 58.5 | 133 | 118 % | 1.51 GB | 119 MB | STREAMING |
| shared | 4 × 15 | 14.0 (13.9–14.0) | 6–7 % | 69.4 / 101.0 | 164.0 / 216.8 | 303 | 161 % | 1.69 GB | 183 MB | STREAMING (93 % of target, inside the 80 %/20 % health thresholds) |

"Inference" is what a camera waits for its model result (including the batching wait); "end-to-end" is frame capture to the end of processing; "incident latency" is frame capture to the incident being committed with its assessment and evidence.

### 14.2 Throughput (offline files, every frame processed, as fast as possible)

| Backend | 1 camera | 2 cameras | 4 cameras | 8 cameras |
|---|---|---|---|---|
| batched (aggregate FPS) | 65.6 | 91.8 | **118.1** | 90.3 |
| shared (aggregate FPS) | 65.3 | 63.0 | 62.4 | — |
| per_camera (aggregate FPS) | 63.3 | 56.8 | 68.1 | — |
| CUDA peak, batched / shared / per_camera | 87 / 87 / 87 MB | 102 / 119 / 145 MB | 131 / 183 / 248 MB | 186 MB (batched) |

**Single-camera baseline:** the original path (`process_video`, annotation on every frame, decode in the same thread) ran at 37.0, 54.8 and 54.4 FPS in three runs; the runtime's single camera ran at 63–66 FPS (decode in its own thread, annotation only on evidence frames).

### 14.3 Interpretation

- **Batching works:** 1.4× aggregate throughput at two cameras and 1.8× at four, with a mean batch of 3.9 at four cameras. A shared lock gives no scaling (each extra camera divides the same ~63 FPS); a model per camera adds GPU memory (248 MB at four cameras against 131 MB batched) without scaling.
- **The bottleneck is CPU-side work, not the GPU:** GPU utilisation stayed at 25–42 % with low clocks, while process CPU rose to 160–250 %. Per-frame Python work (pre/post-processing, tracking, zones, incidents) shares one interpreter lock, and every native frame of every camera is demuxed. Eight cameras offline reach less aggregate throughput (90 FPS) than four (118 FPS).
- **Two optimisations were made because of measurements:** annotation only on evidence frames (2.8 ms/frame saved), and grab-only skipping of frames the rate selector drops (3.9 → 0.4 ms per skipped frame). Before grab-only skipping, the same machine gave 8 × 10 FPS at 9.4 FPS per camera with about 10 % drops, and shared 4 × 15 at 9.0 FPS with about 40 % drops; after it, 10.0 FPS with ≤ 0.5 % drops and 14.0 FPS with 6–7 % drops respectively.
- **Health reporting matched reality:** the overloaded 8 × 15 configuration reported DEGRADED; the healthy configurations reported STREAMING.

### 14.4 Acceptance criteria (set from the measured workload on this machine)

A configuration passes when, over a 20 s window after warm-up, **every camera processes ≥ 95 % of its target rate, drops ≤ 2 % of selected frames, has end-to-end p95 ≤ 250 ms and is STREAMING.**

| Configuration | Result |
|---|---|
| batched 1, 2 and 4 cameras × 15 FPS | **Pass** (≥ 14.89 FPS, ≤ 0.3 % drops, p95 ≤ 107 ms) |
| batched 8 cameras × 10 FPS | **Pass** (≥ 9.89 FPS, ≤ 0.5 % drops, p95 177 ms) |
| batched 8 cameras × 15 FPS | Fail (11.6 FPS, 14–32 % drops); the runtime reported DEGRADED where drops exceeded 20 % |
| shared 4 cameras × 15 FPS | Fail (93 % of target, 6–7 % drops) |

**Sizing guidance for this class of workstation (simulation only):** up to 4 cameras at 15 FPS or 8 cameras at 10 FPS with the batched backend. These are not guarantees for real cameras: RTSP decoding, other resolutions and codecs, real scenes with more people, and GPU clock behaviour will change them. A 24-hour soak test and RTSP measurements are still required (roadmap C1).

### 14.5 Next optimisations, if more cameras per box are needed

1. Use camera **substreams** (for example 720p or D1) for analysis; most IP cameras offer one.
2. **TensorRT** export of the model (requires re-validating detections against the current results).
3. **Hardware video decode** through FFmpeg (DXVA/D3D11, NVDEC, VAAPI).
4. **Process-level parallelism** for tracking and pipeline logic (camera groups in separate processes) to escape the interpreter lock, with the backend behind a local socket (`15` §3.2).

## 15. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Exit code 2 | Invalid configuration | Read the message; run `validate` |
| Exit code 3, "weights not found" | `models/best.pt` missing | See `models/README.md`, or use `backend: null` to test cameras only |
| Camera `ERROR`, "environment variable … is not set" | Credentials not in the service's environment | Set the variables for the account that runs the service |
| Camera cycles `RECONNECTING` | Network, camera down, wrong path, RTSP over UDP blocked | Try `transport: tcp`; check the URL in VLC from the same machine; check `camera_outages` |
| Camera `DEGRADED`, "processing … target …" | GPU/CPU cannot keep up | Lower `max_fps`, use the `batched` backend, reduce cameras per machine |
| `status` says NOT RUNNING | Runtime stopped or crashed | Check `runtime.log`; restart; a service manager should restart it automatically |
| Low FPS everywhere, GPU utilisation low | GPU at power-saving clocks (observed during benchmarks) | Check `gpu.sm_clock_mhz` in `status.json`; set the workstation's power plan for performance |

## 16. Known limitations

- **RTSP not verified on a real stream;** only file and synthetic sources processed frames.
- **One process:** a native crash (OpenCV/CUDA) stops every camera; restart by a service manager is required and not yet packaged.
- **No hot reload** of configuration; adding a camera needs a restart.
- **Live-mode confirmation counts frames** at the analysis rate: when processing falls behind, confirmation takes longer in real time (conservative), and exposure is still measured in monotonic time.
- **Offline file mode uses media time,** so its UTC event times are processing times, not recording times.
- **The dashboard does not read `status.json` yet** and shows runtime incidents only if pointed at the same database.
- **Evidence retention, encryption and access control** are not implemented (roadmap M3).
- **Escalations are logged and stored, not notified.**
- **Performance figures** depend strongly on the GPU's clock state, which varied during measurement (section 14).

## 17. Scaling path

See `15` §4. In short: tune `max_fps` and batching per box; export the model to TensorRT for 2–4× faster inference (requires re-validation of detections); package as a Windows service or systemd unit with restart; add a central server that ingests `runtime_sessions`, `incident_context` and outages from each edge box; move the backend behind a local socket when process isolation is needed.
