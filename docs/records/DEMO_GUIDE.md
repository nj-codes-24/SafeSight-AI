# SafeSight AI demo guide

About 10 minutes. Everything runs offline.

## Before you present

1. Plug the laptop in and close other GPU-heavy apps.
2. Start the dashboard:

   ```bash
   .venv\Scripts\python.exe launch.py
   ```

3. Open http://localhost:8501 and check that **Overview** shows recorded sessions (7 at freeze; each demo run adds one).
4. If the Mixkit clips are missing from the clip list, run `.venv\Scripts\python.exe training\fetch_mixkit.py` once. It needs internet.

## Running order

| Step | Page | Do | Point out |
|---|---|---|---|
| 1 | Overview | Nothing | Totals come from the database, not mock data. "Confirmed tracks" are tracks seen for at least 1 s, not a headcount. |
| 2 | Live monitoring | Clip **Worker puts helmet on**, press Start | The worker starts as VIOLATION, an alert appears, then COMPLIANT once the helmet is on. Same ID throughout. |
| 3 | Live monitoring | Clip **Jackhammer crew, night** | Workers entering the shaded "Breaking area" raise zone alerts. A bare-headed passer-by raises a no-helmet alert. One bent-over worker stays UNCERTAIN, because the system will not guess. |
| 4 | Live monitoring | Clip **Track maintenance, day** | Several workers, a zone over the live rail, helmets correctly left alone. |
| 5 | Incidents | Pick an incident | The evidence screenshot, worker temporary ID, time and confidence. Press **Export CSV**. |
| 6 | Analytics | Scroll | Incident types, compliance by session, timeline. All computed from records. |
| 7 | Configuration | Show the sliders and a zone | The no-helmet threshold (0.6) and zones are editable. |
| 8 | Terminal (optional) | Run the command below | The watchdog is alive and reports health. |

Watchdog command for step 8:

```bash
.venv\Scripts\python.exe watchdog_svc\supervisor.py status
```

## Numbers worth knowing

| Measure | Value |
|---|---|
| Model | YOLO26n, about 3 ms per image; about 50 FPS for the whole pipeline on this laptop |
| SH17 validation, no_helmet at the app threshold | 0.98 precision, 0.62 recall; previous model 0.86 and 0.36 |
| Mendeley test, no_helmet | Recall 0.86, AP50 0.70 |
| Demo clips, at the app threshold of 0.60 | 4 of 4 real no-helmet incidents caught, 0 false alarms |
| Construction-PPE test | mAP50 0.43, lower than the previous model's 0.58, mainly because that dataset draws helmet boxes differently |

## Honest answers to likely questions

- **Is it production-ready?** No. It has never seen a real site's cameras, and the threshold was set on little footage.
- **Does it identify people?** No. IDs are temporary track numbers, and there is no face recognition.
- **Why do some workers show UNCERTAIN?** No clear view of the head, so it declines to decide rather than raise a false alarm.
- **Why is the worker count not a headcount?** One person can get two track IDs after an occlusion.
- **Why is one test score lower than the old model?** Label style, measured on validation. The old model is kept as a fallback.
- **Why this model and not the one with better benchmark scores?** In a final comparison on unseen site footage, it was the only model that caught a real violator without raising false alarms. M3 scored well on a benchmark but called hard hats bare.
- **Which threshold was that comparison run at?**
  - Each model had its own threshold from one rule on validation data only: M2 0.65, M3 0.50, M5 0.50.
  - The app runs M5 at 0.60, set earlier from validation and the demo clips. That setting was also tested on the unseen footage, as its own column, with the same alerts.
  - The app keeps 0.60 because 0.50 raised 2 false alarms on the demo clips.
- **What does it miss?** Workers far from the camera. On a distant rooftop clip, no model found the bare-headed crew.
- **Can it be sold?** Not as is. SH17 is non-commercial, and Ultralytics is AGPL-3.0.

## If something goes wrong

| Problem | Fix |
|---|---|
| Page blank | Wait 10 s, since the model loads on first use, then refresh. |
| Port busy | Run `launch.py` again; if it still fails, restart the laptop. |
| Clip list short | Run `training\fetch_mixkit.py`. |
| Need the previous model | Copy `models\candidates\m2_fallback.pt` over `models\best.pt` and set no-helmet confidence to 0.30 on the Configuration page. |
