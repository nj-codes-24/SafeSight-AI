# Demonstration guide

A reproducible demonstration of about 4 minutes. The expected results are what the application produced in browser tests on 2 November 2026; they repeated on every rerun ([REDESIGN_QA.md](design/REDESIGN_QA.md)).

## Prerequisites

- M5 weights at `models\best.pt`; check with `python scripts\verify_installation.py`.
- The five demo clips in `data\demo\` ([data/README.md](../data/README.md)).
- One browser tab. A second tab cannot start a run while one is active, and shows **Busy**.

## Before you start

```powershell
python launch.py
```

Open http://localhost:8501. **Warm up** by opening any clip and pressing play once. The first run loads the model (about 8 s); later runs start in about 1 s. Processing is faster than real time, so short events pass quickly, but alerts, incident cards and charts keep everything.

## Running order

| # | Where | Action | Expected result | Point to make |
|---|---|---|---|---|
| 1 | Sources | Hover a card | The card lifts; it shows the real frame, duration, resolution and last run | Sources are demo clips, uploads or a webcam; nothing runs until play |
| 2 | Sources | Open **Worker puts helmet on** | Player with the poster frame and a play button | Model and threshold in the corner chip: `M5 · no-helmet 0.60` |
| 3 | Player | **Play** | W1 VIOLATION (red), then **W1 COMPLIANT** (green) once the helmet is on; the LIVE pill becomes Finished | Same temporary ID throughout; the incident closes itself |
| 4 | Below the player | Scroll | Session: Compliant 1, Violation 0, 1 incident. Compliance chart: violation band, then 100% from about 2.4 s. | Live figures are workers in view; final figures are confirmed tracks; neither is a headcount |
| 5 | Incidents | Click the **No helmet · W1** card | Inspector: evidence frame (W1 VIOLATION, confidence 0.814), start and end about 1 s apart, status Closed | No face recognition; IDs are temporary |
| 6 | Top | **All sources**, then **Jackhammer crew, night**, then **Play** | Zone alerts W1, W2, W3 in *Breaking area*; passer-by **W8 · No helmet** near the end; 4 incidents; 6 confirmed tracks of 8 IDs | Zones use the worker's foot point; helmeted workers stay green |
| 7 | Player | **Gear** | Settings: Detection, Safety alerts, Restricted zones, Model | Model tab shows a **Verified** checksum and no-helmet 0.60 |
| 8 | Results | Click **Results** in the top bar, or the **Results** tab in Sources | All-session totals, trends, incident log | Every figure comes from the database |
| 9 | Results › Incident log | **Export CSV** | `safesight_incidents.csv`, one row per incident | Ready for a safety officer's records |

**Optional false-alert control:** play **Ballast train, moving camera** (about 14 s). The expected result is 0 incidents: helmeted workers are not flagged.

## Automated version

`scripts\qa\qa_flow.py` drives the same flow in headless Microsoft Edge and writes screenshots and a log to `.qa\`. It also covers upload, webcam and the second-tab lock.

```powershell
python launch.py            # in one terminal
python scripts\qa\qa_flow.py
```

Note that `qa_flow.py` uploads a copy of one demo clip into `data\demo\uploads\`. Delete it afterwards if you don't want it listed.
