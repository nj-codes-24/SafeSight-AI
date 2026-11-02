# SafeSight AI: operator guide for the live demo

About 4 minutes, using the gallery-and-player interface (v3). The expected results below are what the app produced in browser tests on 2 November 2026, and they repeated on every rerun.

## Before the teacher arrives

1. Start the app and leave the terminal open:

   ```bash
   .venv\Scripts\python.exe launch.py
   ```

2. Open http://localhost:8501. The **Sources** gallery appears.
3. **Warm-up:** open any clip and press play once. The first run loads the model (about 8 s); after that, runs start within about 1 s.
4. Use one browser tab. A second tab can't start a run while one is active: it shows **Busy**.

The app processes video faster than real time, so short events pass quickly. The alert list, incident cards and compliance chart keep everything.

## Running order

| # | Where | Do | What should happen | Point out to the teacher |
|---|---|---|---|---|
| 1 | Sources | Hover a card | The card lifts and a play disc appears. Each card shows a real frame, duration, resolution and last run. | These are the available sources: demo clips, uploads and webcam. Nothing is processed until play is pressed. |
| 2 | Sources | Click **Worker puts helmet on** | The monitor opens with the clip's frame and a large play button | Cinematic player; the model and threshold appear in the corner chip (M5 · no-helmet 0.60). |
| 3 | Player | Press **play** | In the first seconds W1 is VIOLATION (red), then **W1 COMPLIANT** (green) once the helmet is on. The LIVE pill becomes **Finished**. | The same temporary ID goes from violation to compliant. Move the mouse: the controls fade while still and return on movement. |
| 4 | Scroll down | — | The **Session** row ends at Compliant 1, Violation 0, 1 incident. The compliance chart shows the violation band, then 100% from about 2.4 s. | Live figures are workers in view. Final figures are the end state of confirmed tracks. Neither is a headcount. |
| 5 | Incidents | Click the **No helmet · W1** card | The inspector shows the evidence frame (W1 VIOLATION, 0.814), with start and end about 1 s apart and status Closed | The incident closed itself when the helmet went on. No face recognition; IDs are temporary. |
| 6 | Top | **All sources**, then **Jackhammer crew, night**, then **play** | About 10 s. Zone alerts for W1, W2 and W3 in **Breaking area**, and a passer-by **W8 · No helmet** near the end. 4 incidents, 6 confirmed tracks of 8 IDs. | Zone alerts use the worker's foot point inside the polygon. Helmeted workers stay green. |
| 7 | Player | Click the **gear** | The settings menu opens inside the player: Detection, Safety alerts, Restricted zones, Model. | Model tab: M5 with a **Verified** checksum and no-helmet 0.60. Zones tab: the Breaking area polygon on the camera view. Don't press Save. |
| 8 | Scroll to **History** (or click History in the top bar) | — | All sessions: totals, compliance trend, incidents by source, incident log | Everything comes from the incident database, and nothing is mock data. |
| 9 | History › Incident log | **Export CSV** | `safesight_incidents.csv` downloads, one row per incident | Ready for a safety officer's records. |

The optional false-alert control is **Ballast train, moving camera**: about 14 s, 0 incidents, helmeted workers not flagged.

## If something goes wrong

| Problem | Do this |
|---|---|
| Play stays on "Starting" for a few seconds | The first run loads the model. Wait about 10 s. |
| Play button is greyed out and the player says **Busy** | Another tab is monitoring. Stop it there, or wait for it to finish. |
| All sources / Sources is greyed out | A run is in progress. Press stop (■) in the control bar first. |
| FPS looks low | The machine may be in a power-saving state; let it run once. Results are the same, only slower. |
| Port busy | Close the old terminal and run `launch.py` again. |
| A clip is missing | The Mixkit clips must be fetched once: `.venv\Scripts\python.exe training\fetch_mixkit.py` (needs internet). |

## Backup material

- **Screenshots of this interface:** `design/BEFORE_AFTER/final/`.
- **Older dashboard recording:** `demo_audit/demo_recording.mp4` shows the previous dashboard design, unedited. It contains Mixkit footage, so keep it local.
- **What was tested:** `design/REDESIGN_QA.md` and `DEMO_READINESS.md`.
