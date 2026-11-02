# SafeSight AI: project status

Updated 2026-11-02. **Tested** means run and checked with the final model. **Partial** means it works, with stated gaps.

- **Final model:** `models/best.pt`, which is M5 (YOLO26n, sha256 `E9B2583D...CC3C7534`), with no_helmet confidence 0.6.
- **Fallback:** M2 at `models/candidates/m2_fallback.pt`, read-only, used with no_helmet confidence 0.3.
- **Two thresholds, not one.**
  - The **comparison threshold** came from a fixed rule on SH17 validation: the lowest confidence with no_helmet precision of at least 0.95. It gave M2 0.65, M3 0.50 and M5 0.50, and was used only to compare models.
  - The **application threshold** for M5 is 0.60. It was set earlier from validation and the demo clips, and is what the app runs.
  - The final report has a table of which threshold every result used.
- **Final controlled comparison of M2, M3 and M5:** run at the comparison thresholds, plus M5 at 0.60 as a separate column. Ten unseen Commons clips were labelled by eye before any run. M5 kept; details in the final report.
  - On worksite clips, M5 raised 2 true alerts and 0 false at both 0.50 and 0.60. M3 (0.50) raised 1 true and 2–3 false on hard hats. M2 (0.65) raised none and missed the c01 violator.
  - All three models missed every worker on the distant c09/c10 site.
- **Preserved, read-only:** `models/candidates/m3_shwd.pt`, `models/candidates/m5_final.pt` and `models/best.pt`.
- **Project frozen.** No further training or experiments.
  - `FREEZE_MANIFEST.txt` holds SHA-256 checksums of the weights, configs, code, documents and presentation assets.
  - Documents, reports, models and presentation files are read-only.
  - Presentation assets are in `presentation/` (see its README).

| Component | Status | Actual evidence |
|---|---|---|
| Model training | Tested | B0, leaky control, M1 to M5 completed; history in `runs/control/history.json`. The first M4 and M5 starts failed on a config encoding error, were stopped by the watchdog, fixed and rerun. All verified checkpoints are kept. |
| Model evaluation | Tested | Every candidate scored on the same common val, with Construction-PPE, Mendeley and SH17 breakdowns (`reports/common_val.json`). Test set run once for M5 after selection: Construction-PPE mAP50 0.427, Mendeley mAP50 0.671 (`reports/eval/final_m5_*`). |
| Worker detection | Tested | Person AP50 0.942 on common val, 0.859 on SH17 val, 0.813 on Construction-PPE test. |
| PPE monitoring | Partial | At the application threshold of 0.60: demo clips 4 of 4 true no-helmet incidents, 0 false; unseen worksite clips 2 true, 0 false, but all 5–7 distant bare-headed workers on c09/c10 were missed (`reports/unseen_compare/`). Cannot tell a worksite from an office or film. |
| Tracking | Partial | 23 IDs across the five clips, down from 33, for 19 confirmed tracks (`reports/tracking_metrics.json`). IDs can still split on occlusion, so counts are tracks, not people. |
| Zone intrusion | Tested | 4 zone incidents on 2 clips, foot point used. Polygons were drawn for the demo. |
| Incident management | Tested | 9 incidents in `logs/incidents/incidents.db`, all closed, all with evidence. CSV export works in the browser. Duplicate suppression for broken tracks is tested. |
| Watchdog | Partial | Supervised all training on both days. Drills pass, a real kill drill resumed, and the keeper restarted a killed watchdog. Not tested: Windows reboot. The keeper needs a logged-in user. |
| Dashboard | Tested | All five pages used in the browser with M5. Live runs at 42.7 to 50.9 FPS, with the correct violation-to-compliant change. Overview totals match the database (7 sessions, 27 confirmed tracks, 10 incidents, 85.7%). The no-helmet threshold slider was added. |
| End-to-end demo | Tested | Five clips from video to evidence and dashboard. `pytest tests`: 32 passed. |

## Acceptance checks

- [x] Custom-trained detector on person, helmet, no_helmet
- [x] Test set kept out of training and selection
- [x] Leakage found, cleaned and measured
- [x] Worker tracking with anonymous IDs and confirmed-track counting
- [x] COMPLIANT, VIOLATION and UNCERTAIN with multi-frame confirmation
- [x] Polygon zones with foot-point logic
- [x] Incidents: SQLite, CSV, evidence, cooldown, broken-track suppression
- [x] Independent watchdog with reports, bounded retries and drills
- [x] Five-page dark dashboard on real data only
- [x] Offline demo launched by one command
- [x] Requirements, README, report, attribution, demo guide
- [ ] Validation on a real site's cameras
- [ ] Reboot recovery of the watchdog
- [ ] Ground-truth ID-switch measurement

## Known problems

1. **Lower common-val and Construction-PPE test scores than M2.** These are mostly the full-head versus shell box-style difference, measured on validation.
2. **No-helmet threshold.** The application threshold of 0.6 is set from little footage. On the demo clips, M5 raised false alarms on helmets seen from behind at 0.3 (3 false) and at 0.5 (2 false), which is also the comparison threshold.
3. **No sense of context.** People in offices or films are flagged if bare-headed.
4. **Licence.** SH17 makes the final model non-commercial.
5. **M3 revisited and still rejected.** It scores well on SH17 (no_helmet AP50 0.723), but on unseen worksite footage at its comparison threshold of 0.50 it called white and dark hard hats bare, raising 2–3 false alerts, and made 10 false no_helmet detections per 100 frames on a helmeted clip.
6. **Distant workers are missed.** On distant, low-quality footage, no model detects bare-headed workers.

## Changes outside the code

- The watchdog and the `SafeSightWatchdogKeeper` scheduled task are still running, with no training queued.
- Old incident databases are archived in `logs/incidents/archive_b0/` and `archive_m2/`. Nothing was deleted except a one-frame session left by the Live-page crash.
- SH17 is downloaded to `data/raw/sh17` (14 GB) and is not redistributable.
