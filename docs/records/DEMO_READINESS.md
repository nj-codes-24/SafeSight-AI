# SafeSight AI: demo-readiness audit

> **Update, later the same day:** the dashboard UI was redesigned (see `design/REDESIGN_CHANGELOG.md`). The full demo sequence was rerun on the new UI with identical incidents, IDs, times and confidences. The "Zone nan" glitch below is fixed. Screenshots in `demo_audit/screenshots/` and `demo_audit/demo_recording.mp4` now show the new UI; the pre-redesign versions are in `demo_audit/pre_redesign/`.

2 November 2026, 15:18 to 15:30. These checks were run against the real app, started with `.venv\Scripts\python.exe launch.py`. They used the frozen M5 weights, the application threshold of 0.60, and the five demo clips.

- Nothing was trained, and no weights, thresholds or project code were changed.
- No incidents, databases or evidence were deleted.
- The incident database was backed up first, to `demo_audit/backup/incidents_pre_audit.db`, and all 10 earlier incidents are still present.

**How the browser was driven.** The browser tests used a headless Microsoft Edge, controlled through the DevTools protocol (`demo_audit/cdp_demo.py`). Its clicks are real mouse events on the real page. The first run used the in-app browser pane.

## Result

| Feature | Tested | Actual result | Status |
|---|---|---|---|
| Worker detection | Night jackhammer, track maintenance, ballast train | Boxes and temporary IDs drawn on every worker in view. Night clip: 8 track IDs, 6 confirmed, up to 5 in one frame. Track clip: 8 IDs, 7 confirmed. | PASS |
| Helmet violation | helmet_put_on, roadworks_night, framing_bare_head | Alert **No helmet - W1** at 0.46 s, confidence 0.814. The night passer-by is flagged as W8 at 11.18 s. framing_bare_head gave 2 no-helmet incidents (measurement run). | PASS |
| Compliance transition | helmet_put_on | W1: VIOLATION, then COMPLIANT, with the same ID. The incident opened at 15:24:51 and closed at 15:24:52, with status CLOSED. The session's final state is 1 compliant and 0 violation. | PASS |
| Worker tracking | All demo clips; active and confirmed counts | Counts show live, for example "Active tracks 4 · Confirmed tracks 6 of 8 IDs". IDs can split after occlusion (8 IDs for 6 confirmed tracks), so counts are tracks, not people. **Two browser tabs running at once share one tracker** (see Findings). | PARTIAL |
| Zone intrusion | roadworks_night (Breaking area), track_work_day (Live rail) | 3 zone incidents (W1, W2, W3) at 0.43–0.67 s, and 1 on Live rail (W2) at 0.48 s. Each has a start and end time and an evidence image. | PASS |
| Incident recording | Database before and after each run | Every alert on screen has a matching database row. The run sequence was identical on two separate full runs. | PASS |
| Evidence screenshots | Opened in the Incidents page | Zone and no-helmet evidence images render in the browser. All 34 incidents have their evidence file on disk. The no-helmet detail panel shows "Zone nan" instead of "-", a display glitch. | PASS (cosmetic glitch) |
| Analytics | Page loaded and inspected | Five charts, all from records: incident types 15 no-helmet and 19 zone, matching the database. No exceptions. | PASS |
| CSV export | Export CSV pressed in the browser | `safesight_incidents.csv` downloaded: header plus 34 rows, equal to the database. | PASS |
| Fresh application launch | `launch.py` started on a free port at 15:18 | The app served on localhost:8501. History from earlier sessions persisted across the restart, and the model loaded on first Start. | PASS |
| False-alert control | ballast_train (all helmeted); track_work_day | 0 no-helmet incidents on both. On ballast_train: 2 compliant, 1 uncertain, 0 violation. | PASS |
| Configuration | Page loaded; nothing saved | Sliders read worker 0.35, helmet 0.30 and **no-helmet 0.60**. The zones are present. | PASS |
| Page switching | 10 switches across all five pages, idle | 0 exceptions | PASS |
| Dashboard against database | Overview after the runs | Overview showed 24 sessions, 93 confirmed tracks, 15 no-helmet and 19 zone incidents, and 89.0% compliance. A direct database query gives exactly the same. | PASS |

## Frozen model and settings in use

- **Weights:** `models/best.pt` has SHA-256 `E9B2583D…CC3C7534`, the same as the freeze manifest, and is read-only. The app loads exactly this file (`app/components/shared.py`, `inference/detector.py`).
- **Thresholds:** `models/runtime_config.json` holds only zones, so the defaults apply: person 0.35, helmet 0.30, no-helmet **0.60**. The Configuration page showed the same values.
- **Demo clips:** all five are present in `data/demo/`. Licences are recorded in `data/demo/demo_clips.json` and `DATASETS.md`.
  - The three Wikimedia Commons clips are CC BY-SA.
  - The two Mixkit clips are under the Mixkit free licence, with standalone redistribution unconfirmed. Fetch them; do not ship them.

## Performance, measured in this audit

| Measure | Value | How |
|---|---|---|
| Full pipeline in the app, browser attached | 41–60 FPS. Clean runs: helmet_put_on 60.1, roadworks_night 40.9, track_work_day 44.0, ballast_train 48.2. | Session `avg_fps` recorded by the app during the browser runs |
| Full pipeline without the UI | 52–82 FPS: helmet_put_on 72–82, framing_bare_head 66–74, roadworks_night 59–69, track_work_day 60–61, ballast_train 52–56 | `demo_audit/measure_performance.py`, 3 repeats per clip |
| Detection and tracking per frame | Median 10.6–17.0 ms | Same script |
| Model inference, 1280×720 frames at 640 px | About 9.5–10 ms, plus 0.8–1.2 ms preprocessing and about 1.25 ms postprocessing | Ultralytics speed figures (`demo_audit/model_latency.json`) |
| Peak GPU memory, PyTorch | 64 MB allocated, 76 MB reserved | `torch.cuda` in the measurement process |
| Stability | All 5 clips gave identical incidents and final states on 3 repeats. Two full browser demo runs gave the same incidents with the same IDs, times and confidences. | `demo_audit/performance.json`, `demo_execution_log.txt` |

The earlier "about 3 ms per image" in `DEMO_GUIDE.md` was batched validation throughput, not single-frame latency. For the presentation, use the 10 ms per frame measured here.

## Findings

1. **Two clients running at once interfere.** This was observed, not fixed.
   - Every browser session shares one cached detector and its ByteTrack tracker (`app/components/shared.py`; `Pipeline` calls `det.reset()`). A run started in a second tab resets the tracker under the first.
   - During this audit an Edge window, open since 13:14, was connected and ran 8 sessions between 15:19 and 15:22.
   - The in-app pane's first run in that period showed W5 instead of W1 and only 21.6 FPS. Clean runs afterwards showed W1 at 44–60 FPS.
   - **For the demo, use one tab only.** A code fix would give each run its own tracker. It is small, but it changes frozen code, so I did not make it.
2. **"Zone nan" display glitch.** In the Incidents detail panel, an incident with no zone shows "Zone nan" instead of "-". It is cosmetic only, and I did not fix it.
3. **Faster than real time.** Processing outruns the footage, so the 2-second violation phase in helmet_put_on is on screen for under a second. The alert card and incident record stay, so point at those.
4. **Session counts grew.** The database went from 7 sessions to 24: 9 from this audit and 8 from the Edge window. All of them are real runs. The pre-audit copy is kept.

## Saved evidence

| Item | Location |
|---|---|
| Demo execution log, with page text and database rows per run | `demo_audit/demo_execution_log.txt`, `demo_audit/runs.json` |
| Screenshots (19) | `demo_audit/screenshots/` |
| Incident evidence copies (12) | `demo_audit/evidence/` |
| Exported CSV | `demo_audit/download/safesight_incidents.csv` |
| Screen recording, 116 s, unedited, real-time | `demo_audit/demo_recording.mp4`. It contains Mixkit footage, so keep it local. |
| Performance data | `demo_audit/performance.json`, `demo_audit/model_latency.json` |
| Operator guide | `DEMO_OPERATOR_GUIDE.md` |
| Database backup before the audit | `demo_audit/backup/incidents_pre_audit.db` |

The recording comes from the headless browser's own frames, sampled at 10 per second against real time, with no cuts or speed changes. It runs the sequence in the operator guide plus the Track maintenance clip, then switches through all five pages.
