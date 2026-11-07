# Architecture

SafeSight AI has four parts that meet only through files:

| Part | Folders | When it runs |
|---|---|---|
| **Offline training** | `training/`, `watchdog_svc/` | On a GPU workstation, once per experiment |
| **Runtime inference** | `inference/` | For every frame of a monitored video |
| **Monitoring application** | `app/`, `launch.py` | A local Streamlit server, viewed in a browser |
| **Persistent storage** | `database/`, `logs/incidents/`, `models/` | SQLite, evidence images, weights and runtime configuration |

## 1. System overview

```mermaid
flowchart TB
    subgraph TRAIN["Offline training"]
        direction LR
        RAW[("data/raw<br/>downloaded datasets")] --> PREP["training/prepare_data.py<br/>add_sh17.py · pseudo_label.py"]
        PREP --> PROC[("data/processed<br/>leak-free splits")]
        PROC --> TR["training/train.py"]
        WD["watchdog_svc/watchdog.py"] -. supervises .-> TR
        TR --> CK[("runs/&lt;exp&gt;/checkpoints<br/>last_good.pt · best_good.pt")]
        CK --> SEL["evaluation and selection<br/>training/common_val.py · pr_curves.py"]
    end

    SEL -->|frozen copy| W[("models/best.pt<br/>+ model_config.yaml")]

    subgraph APP["Monitoring application"]
        direction LR
        UI["app/main.py<br/>gallery · player · settings · analytics"] --> PIPE["inference/tracker.py<br/>Pipeline"]
        LOCK["app/runlock.py<br/>one run per server"] --- PIPE
    end

    W --> PIPE
    CFG[("models/runtime_config.json")] <--> UI
    CFG --> PIPE
    PIPE --> DB[("logs/incidents/incidents.db")]
    PIPE --> EV[("logs/incidents/evidence/&lt;session&gt;/&lt;incident&gt;.jpg")]
    DB --> UI
    EV --> UI
```

**What each part does:**
- **Training** produces checkpoints. One checkpoint is copied, frozen and recorded with its SHA-256 as `models/best.pt`.
- **The app** never trains. It loads the frozen weights once per server process (`st.cache_resource`) and only when a run starts, so the gallery opens without importing PyTorch.
- **The app and the pipeline share two files:** the runtime configuration, and the SQLite database with its evidence folder.

## 2. Computer-vision pipeline (per frame)

```mermaid
flowchart LR
    F["Frame<br/>(OpenCV VideoCapture)"] --> Y["YOLO26n predict<br/>640 px, conf ≥ 0.10"]
    Y -->|person boxes| BT["ByteTrack update<br/>high 0.35 · new track 0.6"]
    Y -->|helmet ≥ 0.30<br/>no_helmet ≥ 0.60| H["Head detections"]
    BT --> A["assign_heads<br/>greedy one-to-one"]
    H --> A
    A --> V["HelmetStateTracker<br/>vote per track"]
    BT --> Z["ZoneMonitor<br/>foot point in polygon"]
    V --> I["IncidentManager"]
    Z --> I
    I --> O["Annotated frame<br/>+ alerts"]
```

**Detection** (`inference/detector.py`). One `YOLO.predict` call per frame at 640 px, with a low floor confidence (0.10) so that ByteTrack can use low-score boxes to keep tracks alive.
- **Person boxes** go to the tracker.
- **Head boxes** are kept when they reach the class-specific threshold: helmet 0.30, no_helmet 0.60.

**Tracking** (`inference/bytetrack_safesight.yaml`). ByteTrack runs on person boxes only.

| Setting | Value |
|---|---|
| `track_high_thresh` | 0.35 at runtime (the person threshold) |
| `track_low_thresh` | 0.10 |
| `new_track_thresh` | 0.6 |
| `match_thresh` | 0.9 |
| `track_buffer` | 60 frames |

These were swept on the demo clips. They cut the IDs issued across five clips from 33 to 23, while tracked person-frames fell by 2.3%.

**PPE association** (`inference/ppe_association.py`):
- A head can belong to a worker only if its centre lies within the worker box widened by 10% and in its **top 40%**.
- Candidate pairs are scored by how well the head sits at the top-centre, weighted by confidence. They are matched greedily, best first.
- Each head serves **at most one worker**, so one helmet cannot make two overlapping workers compliant.

## 3. Safety-state machine

Each track keeps a rolling window of head evidence:
- **Window:** `max(3 × confirm, 15)` frames.
- **confirm:** `max(2, confirm_seconds × fps)`. With the default 0.5 s at 30 fps, that is 15 frames.

A state needs at least `confirm` head observations, and at least **70%** of them must agree.

```mermaid
stateDiagram-v2
    [*] --> UNCERTAIN
    UNCERTAIN --> VIOLATION: ≥ confirm head votes and ≥ 70% no_helmet
    UNCERTAIN --> COMPLIANT: ≥ confirm head votes and ≥ 70% helmet
    VIOLATION --> COMPLIANT: window turns ≥ 70% helmet
    COMPLIANT --> VIOLATION: window turns ≥ 70% no_helmet
    VIOLATION --> UNCERTAIN: votes mixed or too few
    COMPLIANT --> UNCERTAIN: votes mixed or too few
    UNCERTAIN --> [*]: track lost for 2 s
    VIOLATION --> [*]: track lost for 2 s
    COMPLIANT --> [*]: track lost for 2 s
```

**Missing evidence never produces a violation.** A worker whose head is not visible stays UNCERTAIN, and no alert is raised.

## 4. Restricted zones

- **Zones are stored per camera view,** as polygons with normalised (0–1) coordinates, in `models/runtime_config.json`. They therefore survive a change of resolution.
- **The test point is the foot point,** the bottom-centre of the worker box, checked with `cv2.pointPolygonTest`. Using the feet rather than the box centre avoids false entries when a worker merely stands in front of a zone.
- **Entry and exit are debounced:** entry needs `confirm` consecutive frames inside, and exit needs `2 × confirm` frames outside.
- **Validation** (`validate_polygon`): at least 3 points, coordinates within 0–1, and a non-zero area.

## 5. Incident lifecycle

```mermaid
sequenceDiagram
    participant P as Pipeline (per frame)
    participant M as IncidentManager
    participant D as SQLite
    participant E as Evidence folder
    participant U as App

    P->>M: state VIOLATION, or zone "enter"
    M->>M: already open for (type, track, zone)? then skip
    M->>M: inside cooldown (30 s video time)? then skip
    M->>M: new ID close to a lost track's incident? then suppress
    M->>D: INSERT incident (OPEN, confidence, video time)
    M->>E: write annotated frame <incident>.jpg
    M->>D: UPDATE evidence_path
    M-->>U: alert (drained on the next UI update)
    P->>M: state COMPLIANT, or zone "exit", or track lost for 2 s, or end of run
    M->>D: UPDATE status CLOSED, ended_at
    Note over U,D: Reviewers can set OPEN · CLOSED · REVIEWED · FALSE_ALARM
```

- **Cooldown** is measured in **video time**, so results do not depend on processing speed. It restarts when an incident closes.
- **Broken-track suppression.** If a track that is no longer visible raised the same type of incident within the cooldown, and the new ID is within one box height of it, the new alert is treated as the same worker under a new ID.
- **Evidence** is the annotated frame at the moment of confirmation, so it shows the boxes, IDs and zone that led to the decision.

### 5.1 Hazard typing and risk assessment (`intelligence/`)

Every incident is also typed and risk-assessed. This does not change when incidents open or close.

```mermaid
flowchart LR
    I["Incident raised<br/>NO_HELMET · ZONE_INTRUSION"] --> H["Hazard code<br/>taxonomy + zone kind"]
    H --> R["RiskEngine.assess<br/>severity × exposure band"]
    P[("Policy<br/>models/risk_policy.json<br/>or the draft default")] --> R
    R --> A[("risk_assessments<br/>level, factors, policy version")]
    T["Every frame: exposure grows"] --> R
```

- **Hazard code.** `NO_HELMET` maps to `PPE.HEAD.MISSING`. `ZONE_INTRUSION` maps by the zone's optional `kind`: `restricted` (the default) to `ZONE.ENTRY`, `machine_exclusion` to `MACH.ZONE.ENTRY`, and so on (`intelligence/taxonomy.py`). Zones of kind `pedestrian_only` and `keep_clear` do not raise person-entry incidents.
- **Risk level** is read from the policy's severity × exposure matrix. Exposure starts at the confirmation time and grows while the incident is open; a rise in level is recorded as an escalation.
- **Model confidence never lowers risk.** It only sets the evidence quality (strong, moderate, weak), and weak evidence is marked for human review.
- **Unknown context never lowers risk,** and a draft policy never applies reductions. The shipped policy is a draft example; a competent person must approve a site policy.
- **Validation** of incidents against labelled episodes: `scripts/evaluation/event_metrics.py` (see `docs/product_research/09_SAFETY_VALIDATION_FRAMEWORK.md`).

### 5.2 Headless multi-camera runtime (`runtime/`)

The same pipeline can also run without the dashboard, for several cameras at once (`python -m runtime run --config …`). Each camera has a capture thread, a bounded frame queue and a processing thread with its own `Pipeline`, tracker and database connection; one model is shared through a batched inference thread. Design: [product_research/15](product_research/15_HEADLESS_RUNTIME_ARCHITECTURE.md); operation and measurements: [product_research/16](product_research/16_HEADLESS_RUNTIME_IMPLEMENTATION.md); commands: [runtime_getting_started.md](runtime_getting_started.md).

**Camera view monitoring.** Before a frame reaches the pipeline, the camera's view guard (`runtime/view.py`, using `inference/view_monitor.py`) checks every 0.5 s that the camera still shows its registered reference view. A confirmed move, cut or blockage ends open incidents at the last reliable observation (`camera_view_changed`, `camera_scene_switched`, `camera_blocked`), resets tracks and suspends analysis until the registered view returns or an operator accepts a new one; zones of an unverified view raise nothing. The view state is reported beside the connection state. Details: [product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md](product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md).

## 6. Storage

| Store | Location | Contents |
|---|---|---|
| Incidents database | `logs/incidents/incidents.db` (SQLite, WAL) | `sessions`: id, time, source, frames, confirmed tracks, final compliant/violation/uncertain counts, average FPS. `incidents`: id, start and end, type, worker ID, confidence, camera, session, zone, video time, evidence path, status. `risk_assessments`: one row per incident with hazard code, severity, exposure, risk level, evidence quality, factors, actions, policy version and status, escalation time. `incident_reviews` (milestone M3): append-only operator decisions, one row per status change, with the previous status, reviewer, reason, source (dashboard or runtime CLI) and UTC time. |
| Evidence | `logs/incidents/evidence/<session>/<incident>.jpg` | One annotated frame per incident; never overwritten |
| Runtime configuration | `models/runtime_config.json` | Zones, plus thresholds and alert timing once saved. Defaults live in `inference/config.py`. |
| Model record | `models/model_config.yaml` | Frozen model identity, checksum, thresholds, licence note |
| Thumbnails | `data/cache/thumbnails/` | Gallery frames extracted once with OpenCV |

**Confirmed tracks** (tracks seen for at least 1 s) are what the `sessions` table counts. The final state of each confirmed track is what feeds the compliance figures. **Track counts are not headcounts:** one person can receive two IDs after an occlusion.

## 7. Monitoring application

```mermaid
flowchart LR
    G["Source gallery<br/>(default view)"] -->|select a card<br/>?source=…| P["Player<br/>poster · play"]
    P -->|play| R["Run<br/>live frames · alerts · figures"]
    R -->|finished or stopped| S["Session view<br/>incidents · analytics · history"]
    S -->|All sources| G
    P -. gear .-> C["Settings menu<br/>detection · alerts · zones · model"]
```

- **One page, two views.** The query parameter `source` selects the view, so reloading the page keeps you on the same source.
- **The run loop is the pipeline loop.** About 12 times a second, the latest annotated frame and changed figures are pushed to the browser. Panels whose HTML is unchanged are not resent.
- **Single-run lock** (`app/runlock.py`). All browser sessions share one cached detector and tracker, so only one run may be active per server. Other tabs show *Busy*. The lock carries a heartbeat and frees itself 4 s after a tab disappears.
- **Navigation and settings are disabled during a run,** so a click cannot interrupt the tracker by accident. Stop ends the run cleanly: open incidents are closed and the session is saved.

## 8. Training watchdog and checkpoint recovery

```mermaid
flowchart TB
    Q[("runs/control/queue.json")] --> WD["watchdog.py<br/>(own process)"]
    WD -->|launch| T["train.py"]
    T -->|every 15 s| HB[("heartbeat.json<br/>epoch · batch · loss · non-finite count")]
    T -->|on save, atomic copy| LG[("last_good.pt · best_good.pt<br/>+ snapshots")]
    WD -->|every poll| CHK{"process alive?<br/>heartbeat fresh?<br/>loss finite?<br/>disk · RAM · GPU ok?"}
    HB --> CHK
    CHK -->|yes| WD
    CHK -->|no| REC["recover: kill tree, then resume from last_good.pt"]
    REC --> LAD{"ladder step<br/>1: same · 2: same · 3: batch ÷2<br/>4: batch ÷2, 2 workers · 5: batch ÷4, 0 workers"}
    LAD -->|retries left| T
    LAD -->|exhausted| STOP["job marked failed; report written"]
    WD -->|every 2 h| AUD["full audit: load checkpoint, test prediction"]
    KEEP["supervisor.py ensure<br/>(scheduled every 5 min)"] -. restarts if dead .-> WD
```

- **The trainer and the watchdog are separate processes,** and either can die without taking the other with it. The watchdog's state lives in `runs/control/state.json`, so a restarted watchdog re-adopts a trainer that is still running.
- **Checkpoints are copied atomically and verified,** so recovery always starts from a loadable `last_good.pt`.
- **Drills** (`tests/test_watchdog_drills.py`) run a real watchdog against a dummy trainer in a temporary directory and check that each failure mode is detected and recovered.
