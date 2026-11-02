# v3 redesign: QA record

All checks ran against the real app, started with `launch.py`, using the frozen M5 weights at no-helmet 0.60 and the real incident database.

- **Browser automation:** headless Edge driven through the DevTools protocol, with real mouse and keyboard events (`design/qa_flow.py`, `design/responsive_check.py`).
- **Manual checks:** in the in-app browser.

The logs are `design/qa_log_1440x900.txt` and `design/responsive_log.txt`, and the screenshots are in `design/BEFORE_AFTER/final/` and `.../responsive/`.

## End-to-end flow at 1440×900 (final run, 17:16–17:18)

| # | Step | Result | Status |
|---|---|---|---|
| 1 | Open the gallery | 5 cards, 5 real thumbnails loaded, no horizontal overflow | PASS |
| 2 | Select the Jackhammer crew card | Player opens at `?source=demo:roadworks_night.mp4` with the poster frame; no processing starts | PASS |
| 3 | Settings gear in the player | Detection, Safety alerts, Restricted zones and Model tabs. Model shows M5, YOLO26n, m5_sh17_ft, the SHA-256 marked **Verified**, and no-helmet 0.60. | PASS |
| 4 | Press play | First processed frame after 8.7 s (model load); about 1 s once the model is loaded. Back is disabled during the run. | PASS |
| 5 | Detection overlays | Worker boxes with W IDs, COMPLIANT and UNCERTAIN labels, the "Breaking area" polygon; progress and FPS in the control bar | PASS |
| 6 | Controls fade | The control bar and top overlay hide after 2.6 s without mouse movement and return on movement | PASS |
| 7 | PPE alert and zone alerts | 4 incidents (W8 no helmet at 11.18 s, conf 0.776; W1, W2, W3 in Breaking area), the same as every earlier run of this clip | PASS |
| 8 | Violation → compliant (helmet clip, run manually) | W1 UNCERTAIN, then a violation, then **W1 COMPLIANT**. The compliance-over-time chart shows the violation band, then 100% from about 2.4 s. | PASS |
| 9 | Session figures | Active tracks 4, Confirmed 6 of 8 IDs, Compliant 5, Violation 1, Uncertain 0, Compliance 83.3%, Incidents 4, about 40 FPS | PASS |
| 10 | Incident cards and inspector | 4 cards with evidence thumbnails. Clicking one opens a dialog with the evidence frame, badges, details and the review status. | PASS |
| 11 | Session analytics | Worker states, compliance during the run, incident timeline, zone intrusions by zone | PASS |
| 12 | History | 68 sessions, 51 PPE and 87 zone incidents (138 total), matching the database at that moment (68, 138) | PASS |
| 13 | CSV export | `safesight_incidents.csv` with 138 rows, equal to the database | PASS |
| 14 | Change a harmless setting | Cooldown 30 → 35 s in the player menu, then Save. A toast confirmed it and `runtime_config.json` contained 35.0. The file was then restored byte for byte. | PASS |
| 15 | Back to the gallery | Returns to the gallery | PASS |
| 16 | Upload video | The real `st.file_uploader` took a file, saved it to `data/demo/uploads`, opened it in the player and ran it to the end (2 no-helmet incidents) | PASS |
| 17 | Webcam | The real `cv2.VideoCapture(0)` path ran. No camera is attached to this workstation, so the player shows "No webcam is available on this computer" and the lock is released. | PASS (no camera to stream from) |
| 18 | Second tab during a run | Tab B: play disabled, player state **Busy**, top bar "Monitoring track_work_day". After tab A finished, tab B's play was enabled again. | PASS |
| 19 | Streamlit exceptions | 0 on both tabs | PASS |

## Responsive (no runs)

| Viewport | Gallery columns | Player ratio | Horizontal overflow |
|---|---|---|---|
| 1920×1080 | 3 | 1.82 | none |
| 1440×900 | 3 | 1.82 | none |
| 1366×768 | 3 | 1.83; control bar on screen | none |
| 1024×768 | 2 | 1.83 | none |
| 768×1024 | 2 | 1.84 | none |

## Integrity

- **Tests:** `pytest tests`: 32 passed.
- **Freeze manifest:** every entry outside `app/` is unchanged, including all models, `inference/`, `database/`, `training/`, `watchdog_svc/`, `reports/` and `data/` files, and `models/runtime_config.json`.
- **Weights:** `models/best.pt` is `E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534`.
- **Network:** every browser request goes to localhost; there are no external fonts or CDNs.
- **Data:** no incidents, sessions or evidence were deleted. The database grew through real runs, to 70 sessions and 141 incidents at the end of QA.

**Full SHA-256 of the v3 UI files:**

```
356C9CF175A8878CB6CCB6DF47BA870FF0C2C90E598883A4B16A0B546C8D6797  app/main.py
5EB1FD3AF8A5674BB4CD6BD9E5925E2DA0E812D333C92BB71D339E21D30E6EEA  app/theme.py
6D4DA3A825B79A316EF17B12DF512E73B747F6517882AF2EDCA04A39A0C2CA03  app/sources.py
CB883908E68B4619879CC2CB3914E507FE4169AAC83EDA4A14D0307C68649B04  app/runlock.py
7B89795F1E5234FCBC0066B78F9DD63E2708784D53DFB79FDDA8E5DFAC88AB02  app/views/gallery.py
B3ED311E2014EAC8112065778E9E34F90F29C813F18B47D6E0EFF7A70965136D  app/views/player.py
D68F23708568E80393C0E8308ABB33D525AB07299E23160E04695FCDB304077D  app/views/insights.py
96E0087CB6A6B886C365E9C9E1009EA30B2F6E5E2AC94CF7639DD37D2352024B  app/views/settings.py
06A6296A0E1143CC08A7C096262D367AA086C92C9FFDC1F1DA7FF402A036EF3B  .streamlit/config.toml
```

## Known limitations

- **Processing speed varies with the machine's state.** Today it ranged from 20–29 FPS in throughput (the GPU often idled at 210 MHz between runs) to about 40–60 FPS earlier. The interleaved A/B test in `design/perf_check/` showed the UI is not the cause. Check the FPS in the control bar before presenting.
- **The ballast-train thumbnail shows the train and gravel**, because that is the first clear frame of the clip. No model runs to choose a "better" frame.
- **Not seekable, no pause, no volume.** The progress bar shows position only; pause would require restarting the tracker; there is no audio.
- **Fullscreen and the control fade** use a small script embedded with `st.html`. Without it, the app still works, just without those two effects.
- **`demo_audit/cdp_demo.py` targets the previous UI.**
