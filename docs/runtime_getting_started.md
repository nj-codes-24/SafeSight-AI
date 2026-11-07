# Headless runtime: getting started

The headless runtime monitors several cameras in one background process, without a browser. The Streamlit dashboard keeps working as before and does not need the runtime. Design: [docs/product_research/15_HEADLESS_RUNTIME_ARCHITECTURE.md](product_research/15_HEADLESS_RUNTIME_ARCHITECTURE.md); full reference and measurements: [docs/product_research/16_HEADLESS_RUNTIME_IMPLEMENTATION.md](product_research/16_HEADLESS_RUNTIME_IMPLEMENTATION.md).

> SafeSight is an additional monitoring layer and a research prototype. It never controls machinery, and an absence of incidents is not evidence that an area is safe. The risk policy is a draft until a competent person approves a site policy.

## 1. Prerequisites

- The installation in [docs/installation.md](installation.md) (Python 3.11, `.venv`, `requirements.txt`).
- Model weights at `models\best.pt` for real detection. Without them, use `backend: null` (cameras and health only, no detection).
- For the demo: the clips in `data\demo\` ([data/README.md](../data/README.md)).

All commands run from the project folder in PowerShell:

```powershell
cd D:\safesight-AI
.venv\Scripts\Activate.ps1
```

## 2. Run the demos

There are two demo configurations. Both replay demo clips at their own frame rate, in a loop, as stand-ins for cameras, and never write to the dashboard's database.

- `config/runtime.demo.yaml`, the **fixed-camera demo**: two cameras showing the only demo scene filmed from a fixed camera, with full camera view monitoring at its default thresholds. Writes to `logs\runtime\`.
- `config/runtime.demo_handheld.yaml`, the **hand-held footage demo**: the four other clips, which were filmed hand-held or from a moving vehicle and are not suitable for fixed-camera view validation. View monitoring checks blockage only, the cameras have no zones, and every camera reports monitoring `partial` ("camera position not validated"). Writes to `logs\runtime_handheld\`. Use the same commands below with this file.

```powershell
python -m runtime validate --config config/runtime.demo.yaml
```

```powershell
python -m runtime run --config config/runtime.demo.yaml
```

Stop with **Ctrl+C**. Open incidents are closed, sessions are saved and the process exits with code 0. A second Ctrl+C exits immediately.

While it runs, check health from a second terminal:

```powershell
python -m runtime status --config config/runtime.demo.yaml
```

To run for a fixed time (useful for checks): `python -m runtime run --config config/runtime.demo.yaml --duration 60`.

## 3. Monitor your own cameras

1. Copy the template; `*.local.yaml` files are ignored by git:

   ```powershell
   Copy-Item config/runtime.example.yaml config/plant01.local.yaml
   ```

2. Edit cameras: `id`, `name`, `site`, `source` (`file` or `rtsp`), zones (same format as the dashboard, plus an optional `kind`), and `enabled`.
3. Put RTSP credentials in environment variables, never in the file. For the current PowerShell session:

   ```powershell
   $env:SAFESIGHT_DOCK01_USER = "viewer"
   $env:SAFESIGHT_DOCK01_PASS = "your-password"
   ```

4. Validate, then run:

   ```powershell
   python -m runtime validate --config config/plant01.local.yaml
   ```

   ```powershell
   python -m runtime run --config config/plant01.local.yaml
   ```

## 4. Camera view monitoring

Each file or RTSP camera's view is checked twice a second against a reference view stored in the runtime database
([details](product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md)). The first steady view becomes revision 1; later
starts verify it for 2 s before analysing. If the camera is moved, re-aimed, zoomed, switched to another scene or
covered for 5 s, its open incidents end at the last reliable observation (reason `camera_view_changed`,
`camera_scene_switched` or `camera_blocked`) and the camera stops analysing: `status` shows the connection (for example
`STREAMING`) and the view (for example `BLOCKED`) separately, with monitoring `no`. It resumes by itself when the
registered view returns for 3 s. A camera moved on purpose needs an operator:

```powershell
python -m runtime view list --config config/plant01.local.yaml
```

```powershell
python -m runtime view accept --config config/plant01.local.yaml --camera dock-01 --revision 2 --by "Your name"
```

```powershell
python -m runtime view verify-zones --config config/plant01.local.yaml --camera dock-01 --by "Your name"
```

`view list` shows the candidate revision and grey snapshots of the change. Until `verify-zones` (or `accept
--zones-reviewed`), the accepted view raises no zone alerts. `acknowledge --event VE-...` records that someone saw an
event. Settings go under `view_monitor:` (see `config/runtime.example.yaml`); `geometry: false` checks blockage only,
for a camera that is meant to move and has no zones.

### Reviewing incidents without the dashboard

A safety officer records a decision on an incident with their name and a reason; each decision is appended to the
`incident_reviews` table (who, when, previous status, reason), and the dashboard's review control writes the same
record:

```powershell
python -m runtime incident list --config config/plant01.local.yaml
```

```powershell
python -m runtime incident review --config config/plant01.local.yaml --incident INC-20261106-1A2B3C4D --status FALSE_ALARM --by "SL" --note "dark hard hat"
```

### Physical camera acceptance

Before a camera is used in a pilot, run the acceptance procedure in
[`23A`](product_research/23A_PHYSICAL_CAMERA_ACCEPTANCE_TEST_PLAN.md) with `scripts/validation/camera_acceptance.py`.
It has not yet been run on a physical camera.

## 5. Where things go

| What | Default location |
|---|---|
| Incidents, assessments, sessions, outages, view revisions and events | `logs\runtime\incidents.db` (same schema as the dashboard) |
| Evidence frames | `logs\runtime\evidence\<session>\<incident>.jpg`; view-event snapshots in `logs\runtime\evidence\view\<camera>\` |
| Live health | `logs\runtime\status.json` (rewritten every 2 s) |
| Log | `logs\runtime\runtime.log` (rotating, credentials redacted) |

To let the dashboard's Results tab and CSV export include runtime incidents, set `runtime.database: logs/incidents/incidents.db` in your configuration. The schema is the same; runtime sessions appear with the source `camera:<id>`.

## 6. Exit codes

| Code | Meaning |
|---|---|
| 0 | Clean shutdown |
| 1 | Unexpected failure, or a camera did not stop in time |
| 2 | Invalid configuration (the message names the problem) |
| 3 | Startup failure, for example missing weights |

## 7. Run the tests and the benchmark

```powershell
python -m pytest tests/test_runtime.py tests/test_runtime_integration.py -q
```

```powershell
python scripts/benchmark/runtime_benchmark.py
```

The benchmark takes about 12 minutes and writes `reports/runtime/multicamera_benchmark.json`.
