# SafeSight AI: final project report

SafeSight AI watches worksite video, finds workers, decides whether each wears a hard hat, detects entry into restricted zones, and records incidents with evidence. It runs fully offline on one workstation. This is a research prototype, not a certified safety system.

## Result in brief

**Model.** M5, a YOLO26n with 2.39M parameters when fused. It was fine-tuned in two steps from the day-1 model M2, on:

- Construction-PPE with full-head boxes
- Mendeley PPE v6
- an audited 1,819-image subset of SH17

**Validation.** M5 finds about twice the bare heads M2 found on the fully labelled SH17 validation set, at higher precision:

| no_helmet on SH17 val | Recall | Precision |
|---|---|---|
| M2 at conf 0.3 | 0.36 | 0.86 |
| M5 at conf 0.6 | 0.62 | 0.98 |

**Worksite footage.** At the application threshold of 0.60, M5 raises all 4 true no-helmet incidents on five demo clips and no false ones. On five helmeted clips not used for tuning it raises no false incidents.

**Weakness.** M5 scores lower than M2 on the Construction-PPE test (mAP50 0.427 vs 0.583). Validation shows that set draws boxes differently from M5's full-head boxes. Its no_helmet labels are also mostly not worksite people.

**Licence.** M5 is trained partly on SH17 (CC BY-NC-SA 4.0), so it is non-commercial.

**Fallback.** M2 is kept, read-only, at `models/candidates/m2_fallback.pt`.

**Final comparison.** A last controlled comparison of M2, M3 and M5 used thresholds fixed from validation and unseen worksite footage. It kept M5. M3 raised false alarms on hard hats, and M2 missed a real violator.

## Thresholds used in this report

There are two different no_helmet thresholds for M5. They answer different questions.

| Threshold | Value for M5 | How it was set | Used for |
|---|---|---|---|
| **Comparison threshold** | 0.50 | A fixed rule applied to SH17 validation only: the lowest confidence at which no_helmet precision reaches 0.95. The same rule gave M2 0.65 and M3 0.50. | Comparing M2, M3 and M5 fairly, each at its own rule-derived setting. |
| **Application threshold** | 0.60 | Chosen earlier, before the comparison, from validation data and the five demo clips. At 0.50, M5 raised two false alarms on those clips. At 0.60 it raised none. | The running app (`models/model_config.yaml`, Configuration page) and every application result. |

The comparison threshold was not adopted by the app. The application threshold was not re-tuned after the comparison. M5 at 0.60 was also run on the unseen footage as a separate, labelled configuration, fixed before that footage was seen.

Other settings:

- M2's application threshold was 0.30. It is used wherever "M2 at 0.3" appears.
- Validation tables report AP over all confidences. Their P and R are taken at the evaluator's best-F1 confidence, not at an app threshold, unless a row names a confidence.
- The person threshold (0.35) and the helmet threshold (0.30) are the same everywhere.

| Result | M2 | M3 | M5 |
|---|---|---|---|
| Validation and test tables (AP; P/R at best F1) | none | none | none |
| Common val TP/FN/FP row | 0.30 | — | 0.30 |
| Operating-point table | 0.30 | — | 0.60 |
| Demo clips, full pipeline | 0.30 | — | 0.30 and 0.60, each labelled |
| Earlier holdout check (`reports/holdout_worksite/`) | 0.30 | — | 0.60 |
| PR-curve threshold table | 0.65 | 0.50 | 0.50 |
| Final unseen-footage comparison | 0.65 | 0.50 | 0.50 and 0.60, in separate columns |
| Application checks, tracking section, dashboard, demo | — | — | 0.60 |

## Hardware and software

Windows 11, Xeon w5-2565X, 64 GB RAM, RTX 2000 Ada 16 GB, Python 3.11, PyTorch 2.14.1+cu126, Ultralytics 8.4.197.

## Data

See [DATASETS.md](../DATASETS.md) for sources, licences, leakage cleaning, SH17 label derivation and class distributions.

## Day 1: B0 to M3

All models were trained from COCO YOLO26n at 640 px with seed 42.

| Model | Data | Common val mAP50 | no_helmet P / R / AP50 | Person AP50 |
|---|---|---|---|---|
| B0 | Construction-PPE, leakage cleaned | 0.450 | 0.278 / 0.114 / 0.133 | 0.811 |
| M1 | + Mendeley | 0.509 | 0.501 / 0.711 / 0.611 | 0.235 |
| M2 | + pose-teacher persons, masked unlabelled heads | 0.703 | 0.556 / 0.695 / 0.579 | 0.939 |
| M3 | + SHWD | 0.665 | 0.462 / 0.674 / 0.545 | 0.953 |

M2 was selected and frozen.

## Day 2: diagnosis of M2

All diagnosis used validation data only (`reports/diagnostics/`).

1. **The two sources define the head box differently.** Construction-PPE boxes cover only the helmet or the top of the head (median width/height 1.15 to 1.29). Mendeley boxes cover the whole head (about 0.6). Both were trained as one class.
2. **Box style explains only part of the Construction-PPE misses.** Relaxing the overlap needed for a match from 0.5 to 0.1 lifted no_helmet hits only from 12 to 17 of 45. Most misses are formal portraits and events, where M2 did not fire at all.
3. **Common-val precision is understated.** In crop review, most no_helmet and helmet "false positives" were real heads that nobody labelled. Validation precision is a lower bound.
4. **Mendeley recall was already high** at every head size.

## Day 2: experiments

Each experiment answered one question. Both ran under the watchdog and both completed. A first attempt at each failed at start-up because of a file-encoding error in the configs. The watchdog stopped retrying after 5 attempts as designed; the configs were fixed and the experiments resubmitted.

- **M4:** fine-tune M2 with Construction-PPE training boxes extended to full heads. This isolates the box-style fix.
- **M5:** fine-tune M4 with the audited SH17 subset added. This isolates SH17's contribution.

Settings for both: AdamW, lr0 0.0005, up to 40 epochs, patience 15. Training stopped early at epoch 29 for M4 and epoch 19 for M5.

### Same validation sets for every candidate

No app threshold applies to this table. AP covers all confidences, P and R are at the evaluator's best-F1 confidence, and the TP/FN/FP row uses conf 0.3 for every model.

| Metric | M2 | M4 | M5 |
|---|---|---|---|
| Common val mAP50 / mAP50-95 | **0.703 / 0.489** | 0.652 / 0.449 | 0.656 / 0.449 |
| Common val person AP50 | 0.939 | 0.931 | **0.942** |
| Common val no_helmet P / R / AP50 | **0.556** / 0.695 / **0.579** | 0.519 / 0.680 / 0.551 | 0.507 / 0.687 / 0.545 |
| Common val no_helmet TP / FN / FP at conf 0.3 | 123 / 46 / 100 | 123 / 48 / 115 | 131 / 39 / 161 |
| Construction-PPE slice mAP50 (shell-style labels) | **0.630** | 0.425 | 0.438 |
| Construction-PPE slice mAP50 (labels extended to full heads) | 0.406 | **0.702** | 0.649 |
| Mendeley slice mAP50 | 0.741 | 0.739 | **0.744** |
| Mendeley no_helmet recall | 0.800 | 0.838 | **0.877** |
| SH17 val mAP50 / mAP50-95 | 0.596 / 0.311 | 0.588 / 0.329 | **0.770 / 0.526** |
| SH17 val person AP50 | 0.790 | 0.779 | **0.859** |
| SH17 val no_helmet P / R / AP50 | 0.740 / 0.408 / 0.513 | 0.589 / 0.373 / 0.439 | **0.944 / 0.704 / 0.827** |
| Inference per image | about 3 ms | about 3 ms | about 3 ms |

The full-head Construction-PPE labels were made with the same rule used to train M4 and M5, so that row favours them. It shows the size of the box-style effect, not a neutral score.

### Operating point

M5 was shown at its raw threshold on footage and raised false alarms: it flagged helmets seen from behind, or on bent heads, as no_helmet. The no_helmet threshold was therefore set at 0.6 using validation data and the five demo clips. This is the **application threshold**. It was chosen before the comparison rule existed.

| no_helmet operating point | Common val R / P | Mendeley R / P | SH17 val R / P |
|---|---|---|---|
| M2 at 0.3 | 0.703 / 0.552 | 0.854 / 0.555 | 0.364 / 0.855 |
| M5 at 0.6 | 0.623 / 0.542 | 0.808 / 0.583 | 0.615 / 0.981 |

### Worksite footage, full pipeline

True incidents were counted by eye: 1 bare-headed passer-by in roadworks_night, 1 in helmet_put_on, 2 in framing_bare_head, and none in the other two clips.

| Setting | True incidents raised | False incidents | Workers left UNCERTAIN |
|---|---|---|---|
| M2 at 0.3 | 4 / 4 | 0 | 5 |
| M5 at 0.3 | 4 / 4 | 3 | 2 |
| M5 at 0.6 | 4 / 4 | 0 | 3 |

M5 was also run at 0.4 and 0.5 (`reports/worksite_compare.json`). At 0.5, the later comparison threshold, it raised the same 4 true incidents and 2 false ones: roadworks_night ID 3 and ballast_train ID 1.

**Footage not used for tuning:** 10 other Commons clips, up to 1,500 frames each (`reports/holdout_worksite/`). M2 ran at 0.30 and M5 at 0.60.

- **Helmeted clips (c02, c03):** neither model raised a false incident.
- **c01 (concrete pour):** both models flagged a worker in a soft cap. M5 correctly marked a distant white hard hat as helmet, which M2 left unmarked.
- **c11 (archive film of a meeting):** both models raised incidents on people who genuinely have no helmet. They are not on a worksite, which shows the system has no notion of context.

### Decision

- **M5 at 0.6 was selected**, and SH17 was not the only reason:
  - It is level with or better than M2 on Mendeley.
  - It is much better when Construction-PPE labels use M5's box style.
  - At 0.60 it catches every true incident on the demo footage with no false ones, and leaves fewer workers undecided than at 0.30.
  - It is no worse on footage it was not tuned on.
- **Against M5:**
  - Common-val mAP50 is lower (0.656 against 0.703), mostly from the Construction-PPE slice.
  - At conf 0.3 it makes more single-frame mistakes on helmets seen from behind, which the 0.6 threshold and multi-frame voting absorb.
- **Experimenting stopped after M5.** The remaining gap is label style and domain, not something another short experiment would fix reliably.

## Final controlled comparison: M2, M3, M5

This was run because SH17 suggested M3 had been rejected too quickly. No model was retrained and the test set was not used.

### Validation, same configuration for all three (`reports/common_val.json`)

No app threshold applies to this table. AP covers all confidences, and P and R are at the evaluator's best-F1 confidence.

| Set | Model | mAP50 / mAP50-95 | person P / R / AP50 / AP50-95 | helmet P / R / AP50 / AP50-95 | no_helmet P / R / AP50 / AP50-95 |
|---|---|---|---|---|---|
| Common val | M2 | **0.703 / 0.489** | 0.906 / 0.887 / 0.939 / 0.721 | 0.531 / 0.844 / **0.590 / 0.360** | **0.556 / 0.695 / 0.579 / 0.384** |
| Common val | M3 | 0.665 / 0.477 | 0.922 / 0.890 / **0.953 / 0.752** | 0.428 / 0.873 / 0.497 / 0.310 | 0.462 / 0.674 / 0.545 / 0.368 |
| Common val | M5 | 0.656 / 0.449 | 0.925 / 0.844 / 0.942 / 0.706 | 0.475 / 0.679 / 0.482 / 0.278 | 0.507 / 0.687 / 0.545 / 0.362 |
| Mendeley slice | M2 | 0.741 / 0.563 | 0.950 / 0.849 / 0.954 / 0.787 | 0.484 / 0.801 / 0.609 / 0.427 | 0.611 / 0.800 / 0.659 / 0.474 |
| Mendeley slice | M3 | 0.727 / 0.558 | 0.974 / 0.831 / 0.970 / 0.828 | 0.382 / 0.836 / 0.562 / 0.383 | 0.523 / 0.800 / 0.648 / 0.464 |
| Mendeley slice | M5 | **0.744** / 0.560 | 0.938 / 0.852 / 0.957 / 0.779 | 0.486 / 0.876 / 0.605 / 0.425 | 0.566 / **0.877 / 0.669 / 0.477** |
| SH17 val (complete labels) | M2 | 0.596 / 0.311 | 0.831 / 0.762 / 0.790 / 0.429 | 0.304 / 0.673 / 0.484 / 0.297 | 0.740 / 0.408 / 0.513 / 0.207 |
| SH17 val (complete labels) | M3 | 0.698 / 0.433 | 0.868 / 0.802 / 0.833 / 0.574 | 0.297 / 0.776 / 0.536 / 0.312 | 0.912 / 0.540 / 0.723 / 0.413 |
| SH17 val (complete labels) | M5 | **0.770 / 0.526** | 0.891 / 0.779 / **0.859 / 0.610** | 0.543 / 0.664 / **0.623 / 0.404** | **0.944 / 0.704 / 0.827 / 0.566** |

The Construction-PPE slice (M2 0.630, M3 0.588, M5 0.438 mAP50) is not repeated here. It is dominated by the box-style difference described earlier.

### no_helmet precision-recall and thresholds, validation only

The rule was fixed before results were seen: the lowest confidence at which SH17-val no_helmet precision reaches 0.95. Curves are in `reports/pr_curves_no_helmet.png`, numbers in `reports/pr_curves.json`.

These are the **comparison thresholds**. They are not the application threshold.

| Model | Comparison threshold | SH17 val P / R | Mendeley R | Common val R |
|---|---|---|---|---|
| M2 | 0.65 | 0.950 / 0.115 | 0.746 | 0.566 |
| M3 | 0.50 | 0.956 / 0.419 | 0.854 | 0.640 |
| M5 | 0.50 | 0.951 / 0.667 | 0.846 | 0.657 |

M5's curve lies above the others across the whole SH17 range. On the partially labelled sets the three curves are close, and their precision there is a lower bound.

For reference, M5 at the application threshold of 0.60 gives SH17 val P 0.981 and R 0.615 (`reports/operating_points.json`). That setting was also run on the unseen footage, as a fourth configuration fixed before the footage was seen. The model comparison itself is between the three rule-derived columns. The 0.60 column shows what the deployed app does.

### Unseen footage, full pipeline (`reports/unseen_compare/`)

Ten Commons clips, up to 1,500 frames each. Ground truth was written by eye from raw frames before any run (`reports/unseen_gt/ground_truth.json`). No threshold was tuned on them. Every incident screenshot was reviewed.

Each column header gives the no_helmet threshold used. The first three are comparison thresholds; M5 (0.60) is the application threshold.

**Worksite clips (c00, c01, c02, c03, c09, c10, c12):**

| Measure | M2 (0.65) | M3 (0.50) | M5 (0.50) | M5 (0.60), app |
|---|---|---|---|---|
| True no-helmet alerts | 0 | 1 | 2 (one worker in a soft cap, two camera shots) | 2 (same) |
| False safety alerts | 0 | 2–3 (white and dark hard hats called bare) | 0 | 0 |
| Missed violators: c01 capped worker | Missed | Caught | Caught | Caught |
| Missed violators: c09/c10, about 5–7 distant bare-headed workers | All missed | All missed | All missed | All missed |
| False no_helmet detections per 100 frames, helmet-only c02 | 0.2 | 10.1 | 0.9 | 0.1 |
| False helmet detections per 100 frames, no-hard-hat c09 / c10 | 0.0 / 0.3 | 18.2 / 5.7 | 0.8 / 0.2 | 0.8 / 0.2 |

**Non-worksite clips:**

- **c11 (archive film):** every configuration flags the bare-headed people: M2 (0.65) 4 incidents, M3 (0.50) 4, M5 (0.50) 7, M5 (0.60) 6. That is correct detection with no worksite context.
- **c07 (interview):** M5 at 0.50 flags the speaker; M5 at 0.60 does not.

**Tracking and speed, all ten clips:**

| Measure | M2 (0.65) | M3 (0.50) | M5 (0.50) | M5 (0.60), app |
|---|---|---|---|---|
| Track IDs issued | 50 | 59 | 47 | 47 |
| IDs lasting under 1 s | 12 | 14 | 5 | 5 |
| FPS, mean (minimum) | 62 (45) | 60 (46) | 58 (41) | 58 (43) |
| Peak GPU allocation, as logged | 60 MB | 69 MB | 78 MB | 88 MB |

Tracking follows person detections only, so the no_helmet threshold does not change track IDs.

The GPU row is not a fair model comparison. All four ran in one process, and each figure includes the models loaded before it, which adds roughly 9 MB per earlier run. The architectures are identical. Run alone, M5 peaks at 55 MB (tracking section below).

### Benchmark versus worksite performance

- **M3 shows the gap most clearly.** It is second-best on SH17 and best at person AP on common val, yet on site footage it raised the only false alarms. It called white and dark hard hats bare, and saw helmets where there were none. SH17 has few helmets (152 in val), so it measures bare-head precision well but says little about helmet mistakes. That is exactly M3's weakness, because SHWD trained it on many helmets of a different style.
- **M2 looks safe only because it rarely fires.** At a threshold that meets the precision target it misses the real violator in c01.
- **Neither benchmark contains very distant, low-quality workers like c09/c10.** All three models fail there. Even person detection barely works at that size, so no threshold change would help.
- **Benchmarks score single images.** The app adds multi-frame confirmation, which removes most single-frame mistakes. That is why M5's 0.9 false detections per 100 frames on c02 at 0.50 produced no alert. At 0.60 the rate is 0.1.

### Decision

**M5 is retained, at the application threshold of 0.60.** The model was chosen at the comparison thresholds; the operating setting was then kept at 0.60.

- **It catches real violations.** At its comparison threshold of 0.50, it was the only model with true alerts and no false alerts on unseen worksite footage. At 0.60 the result is the same.
- **It is the most stable.** It has the fewest IDs and short-lived IDs, at about 58 FPS, at both thresholds.
- **It detects people well.** Person AP50 is 0.942 on common val and the best on SH17. No threshold applies to this figure.
- **Why the app keeps 0.60, not the comparison's 0.50:**
  - On unseen worksite clips both gave the same alerts. Frame-level false no_helmet detections on c02 were 0.1 per 100 frames at 0.60, against 0.9 at 0.50.
  - On the demo clips, 0.50 raised 2 false alarms and 0.60 none.
  - On non-worksite clips, 0.50 also flags the interviewee in c07.
  - The cost is lower SH17-val recall: 0.615 against 0.667.
- **The others are preserved, read-only:** M2 at `models/candidates/m2_fallback.pt` and M3 at `models/candidates/m3_shwd.pt`.

After the decision, the frozen M5 passed `pytest tests` (32 passed) and ran end to end on all demo clips with the same 8 incidents. A live dashboard run matched the database: 7 sessions, 27 confirmed tracks, 5 PPE and 5 zone incidents, compliance 85.7%.

## Held-out test (run once for M5, after selection)

No app threshold applies to this table. AP covers all confidences, and P and R are at the evaluator's best-F1 confidence.

| Test set | M5 mAP50 / mAP50-95 | M2 mAP50 / mAP50-95 | M5 no_helmet P / R / AP50 | M2 no_helmet P / R / AP50 |
|---|---|---|---|---|
| Construction-PPE official (141 images) | 0.427 / 0.177 | 0.583 / 0.278 | 0.209 / 0.125 / 0.134 | 0.404 / 0.175 / 0.155 |
| Mendeley (360 images, helmet and no_helmet only) | 0.671 / 0.478 | 0.667 / 0.482 | 0.531 / 0.858 / 0.704 | 0.529 / 0.832 / 0.693 |

On the Construction-PPE test, M5's helmet AP50 fell from 0.818 to 0.334, while person AP50 was 0.813 against 0.776. This matches the box-style difference measured on validation. That cause was not checked on the test set, because the test labels were not changed. Its 40 no_helmet labels are mostly portraits, children and sport.

Precision on both test sets is a lower bound because of unlabelled heads.

## Tracking (M5 at the application threshold of 0.60, five demo clips)

Tracker settings were swept on the demo clips (`reports/tracking_sweep/`).

- **New-track confidence 0.6 and match threshold 0.9** cut IDs issued across the five clips from 33 to 23, while tracked person-frames fell by 2.3%.
- **Position-only stitching of broken tracks** made 2 joins in all five clips, so it was left out of the app.

| Clip | IDs issued | Confirmed tracks (seen at least 1 s) | Most people in one frame | Detect + track FPS |
|---|---|---|---|---|
| track_work_day | 8 | 7 | 5 | 45 |
| roadworks_night | 8 | 6 | 5 | 76 |
| ballast_train | 4 | 3 | 4 | 72 |
| helmet_put_on | 1 | 1 | 1 | 73 |
| framing_bare_head | 2 | 2 | 2 | 68 |

The app now shows active tracks and confirmed tracks, never a headcount, because one person can still receive two IDs.

A broken track cannot raise a duplicate incident. A new ID that alerts within one box height of a vanished track's incident, inside the cooldown, is suppressed, while two visible workers side by side both alert. Both behaviours have tests.

Peak PyTorch GPU allocation is 55 MB.

## Application checks (M5, real weights, application threshold 0.60)

- **Helmet transitions** on helmet_put_on: UNCERTAIN, then VIOLATION at 0.46 s, then COMPLIANT at 2.42 s. The incident closed. The same sequence was seen live in the browser at 50.9 FPS.
- **Zones:** 4 zone incidents (3 roadworks_night, 1 track_work_day).
- **Evidence:** all 9 incidents have screenshots on disk.
- **Database and dashboard:** Overview totals match the database exactly: 6 sessions, 20 confirmed tracks, 5 PPE and 4 zone incidents, compliance 82.4% (14 of 17).
- **CSV:** exported from the browser, header plus one row per incident.
- **Configuration:** the new no-helmet threshold slider loads at 0.60.
- **No mock values:** a source scan found no illustrative numbers in the app.
- **Bug found and fixed:** the Live page crashed on the new statistics because an edit had not applied and a "·" character was corrupted. A one-frame session left by that crash was removed from the database.
- **Tests:** `pytest tests` gives 32 passed.

## Watchdog

- **Day 1:** a real kill drill resumed from a verified checkpoint, and the keeper task restarted a killed watchdog.
- **Day 2:** the watchdog supervised M4 and M5. It correctly gave up after 5 failed starts when the configs were broken, preserving everything.
- **Current state:** still running (PID 28476), with no training queued.
- **Not tested:** recovery after a Windows reboot. The keeper only runs while a user is logged in.

## Limitations

- Not validated on any real site's cameras. All footage is public.
- The no-helmet threshold of 0.6 was chosen on a small amount of footage. A site should re-tune it.
- The model cannot tell a worksite from an office or a film. It flags any bare head.
- Small, distant or bent-over heads often stay UNCERTAIN, so the system does not decide. On distant, low-quality footage (c09/c10), every model missed all 5–7 bare-headed workers.
- Unique-worker counts are not available. Track counts can overstate people.
- SH17 labels still hold a small share of wrong no_helmet boxes (about 1 in 66 in a random sample).
- No fairness analysis by skin tone, hair or headwear type.
- **Licences:** SH17 makes the model non-commercial; Ultralytics and Construction-PPE carry AGPL-3.0; Mixkit clips must be fetched, not shipped.

## Ethics and privacy

- No face recognition or identity tracking. IDs are temporary track numbers.
- Everything runs locally.
- Evidence screenshots show identifiable people, so a real deployment needs consent, a privacy notice and a retention policy.
