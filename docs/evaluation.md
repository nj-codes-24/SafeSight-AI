# Evaluation

**Sources.** Everything here is taken from the frozen result files in [`reports/`](../reports/), mainly [`reports/final_report.md`](../reports/final_report.md), [`reports/common_val.json`](../reports/common_val.json), [`reports/pr_curves.json`](../reports/pr_curves.json), [`reports/operating_points.json`](../reports/operating_points.json), [`reports/unseen_compare/summary.json`](../reports/unseen_compare/summary.json) and [`reports/eval/`](../reports/eval/).

**Conventions:**
- **AP** is averaged over all confidences, so it is threshold-free.
- **P and R** in validation and test tables are taken at the evaluator's best-F1 confidence unless a threshold is named.
- **Precision is not accuracy.**

## 1. Data separation

| Split | Contents | Used for |
|---|---|---|
| Train | Construction-PPE 670, Mendeley 1,711 (+ SH17 subset for M5) | Fitting |
| Validation, "common val" | 308 images: Construction-PPE 96, Mendeley 212. Labels are **partial**. | Model selection, thresholds |
| SH17 val | 1,618 images, **complete** labels: person 2,721, helmet 152, no_helmet 2,291 | A fully labelled check, chiefly for bare heads |
| Test | 501 images: Construction-PPE official 141 (verbatim), Mendeley 360 | **Run once, after M5 was selected** |
| Unseen footage | 10 Wikimedia Commons clips not used for any tuning | Full-pipeline behaviour |

**Leakage.**
- **Construction-PPE's official splits contained 989 train-to-test near-duplicate pairs** (ResNet18 embeddings, cosine above 0.93), frames from the same videos. 449 train and 47 val images linked to test were dropped, plus 13 train images linked to val. The test set was not altered.
- **A leakage control,** B0 trained on the official leaky splits, scored mAP50 0.629 on the official test set, against 0.670 for B0 on the cleaned splits ([`reports/eval/`](../reports/eval/)).
- **Mendeley** was split 75/10/15 by near-duplicate cluster.
- **SH17 images** were checked at cosine 0.90 against every train, val and test image: 200 train and 2 val images were removed.

**Label problems** that shape every number below:
- **Construction-PPE draws helmet-only (shell) boxes.** Mendeley and SH17 draw full-head boxes.
- **Construction-PPE's no_helmet instances are mostly non-industrial,** such as portraits, children and sport.
- **Mendeley has no person class** and labels only some heads per image.
- **Consequence:** precision on common val is a **lower bound**. In crop reviews, most "false positives" were real heads nobody had labelled.

## 2. Experiments

All models are YOLO26n at 640 px with seed 42. Each experiment answered one question.

| Model | Change | Common val mAP50 | Common val no_helmet AP50 | Common val person AP50 | SH17 val no_helmet AP50 | Outcome |
|---|---|---:|---:|---:|---:|---|
| B0 | Construction-PPE only, leak-free | 0.450 | 0.133 | 0.811 | 0.166 | Baseline |
| M1 | + Mendeley, plain union | 0.509 | 0.611 | 0.235 | not scored | Partial labels taught it to ignore people |
| M2 | + pose-teacher person labels, unlabelled heads masked | **0.703** | **0.579** | 0.939 | 0.513 | Day-1 choice; kept as the fallback |
| M3 | + SHWD helmets (train only) | 0.665 | 0.545 | 0.953 | 0.723 | Rejected: false alarms on hard hats |
| M4 | M2 fine-tuned with Construction-PPE boxes extended to full heads | 0.652 | 0.551 | 0.931 | 0.439 | The box fix alone did not help |
| M5 | M4 fine-tuned + audited SH17 subset | 0.656 | 0.545 | 0.942 | **0.827** | **Selected** |

**Pseudo-labels** (M1 → M2) took person recall at confidence 0.3 from 0.146 to 0.896.

**SH17's contribution** is isolated by comparing M5 with M4:
- no_helmet AP50 on SH17 val rose by 0.39.
- person AP50 rose by 0.08.
- Mendeley was unchanged (0.744 against 0.739).

## 3. Final comparison on validation (M2, M3, M5)

| Set | Model | mAP50 / mAP50-95 | person AP50 | helmet AP50 | no_helmet P / R / AP50 |
|---|---|---|---:|---:|---|
| Common val | M2 | **0.703 / 0.489** | 0.939 | **0.590** | **0.556** / **0.695** / **0.579** |
| Common val | M3 | 0.665 / 0.477 | **0.953** | 0.497 | 0.462 / 0.674 / 0.545 |
| Common val | M5 | 0.656 / 0.449 | 0.942 | 0.482 | 0.507 / 0.687 / 0.545 |
| Mendeley slice | M5 | **0.744** / 0.560 | 0.957 | 0.605 | 0.566 / **0.877** / **0.669** |
| SH17 val | M2 | 0.596 / 0.311 | 0.790 | 0.484 | 0.740 / 0.408 / 0.513 |
| SH17 val | M3 | 0.698 / 0.433 | 0.833 | 0.536 | 0.912 / 0.540 / 0.723 |
| SH17 val | M5 | **0.770 / 0.526** | **0.859** | **0.623** | **0.944 / 0.704 / 0.827** |

**Box style explains most of the Construction-PPE gap.**
- **With shell-style labels,** the Construction-PPE validation slice scores M2 0.630, M4 0.425 and M5 0.438 mAP50.
- **With labels extended to full heads,** it scores M2 0.406, M4 0.702 and M5 0.649.
- **That second set of labels uses the same rule as M4 and M5's training data,** so it favours them. It shows the size of the effect, not a neutral score.

## 4. Thresholds

There are two thresholds, for two jobs.

| Threshold | Value | Method | Used for |
|---|---|---|---|
| **Comparison** | M2 0.65, M3 0.50, M5 0.50 | One rule, fixed before results were seen: the lowest confidence at which SH17-val no_helmet precision reaches 0.95 ([`reports/pr_curves.json`](../reports/pr_curves.json)) | Comparing models fairly on unseen footage |
| **Application** | M5 **0.60** | Chosen earlier from validation and five demo clips. At 0.3 and at 0.5, M5 raised false alarms on helmets seen from behind (3 and 2 false alarms). At 0.6 it raised none. | The running app and every application result |

At the application threshold on SH17 val, no_helmet precision is **0.981** and recall **0.615** ([`reports/operating_points.json`](../reports/operating_points.json)). The comparison threshold gives 0.951 and 0.667: the app trades some recall for fewer false alarms.

## 5. Unseen worksite footage (full pipeline)

Ten Wikimedia Commons clips, up to 1,500 frames each. Ground truth was written by eye from raw frames **before any model was run**, and no threshold was tuned on these clips. Each column header gives the no_helmet threshold used.

| Measure | M2 (0.65) | M3 (0.50) | M5 (0.50) | M5 (0.60), app |
|---|---|---|---|---|
| True no-helmet alerts, worksite clips | 0 | 1 | 2 (one worker in a soft cap, two camera shots) | 2 |
| False safety alerts, worksite clips | 0 | 2–3 (white and dark hard hats called bare) | 0 | 0 |
| Worker in a soft cap, clip c01 | Missed | Caught | Caught | Caught |
| 5–7 distant bare-headed workers, c09/c10 | All missed | All missed | All missed | All missed |
| False no_helmet detections per 100 frames, helmeted c02 | 0.2 | 10.1 | 0.9 | 0.1 |
| Track IDs issued, ten clips (IDs lasting under 1 s) | 50 (12) | 59 (14) | 47 (5) | 47 (5) |

**Non-worksite clips.**
- **c11, an archive film:** every configuration flags the bare-headed people. That is correct detection, but the system has no notion of whether a scene is a worksite.
- **c07, an interview:** M5 at 0.50 flags the speaker; M5 at 0.60 does not.

**Demo clips at the application threshold** (five clips, ground truth counted by eye): **4 of 4** true no-helmet incidents raised, **0** false.

## 6. Why benchmarks and site footage disagree

- **SH17 barely tests helmets.** It has only 152 in validation, so it measures bare-head precision well but says little about helmet mistakes, which is exactly M3's weakness.
- **A quiet model is not a safe model.** At a threshold meeting the precision target, M2 rarely fires and misses the real violator.
- **Neither benchmark contains very distant, low-quality workers,** and every model fails on them.
- **Benchmarks score single images;** the app votes over several frames. That is why M5's occasional single-frame mistakes did not become alerts.

## 7. Selection

**M5 was selected at the application threshold 0.60,** and not on SH17 alone:
- It caught real violations on unseen footage with no false alarms.
- It had the steadiest tracking.
- It was level with or better than M2 on Mendeley.
- It was much better on fully labelled bare-head data.

**The cost:** lower common-val mAP50 (0.656 against 0.703) and lower Construction-PPE test scores, both dominated by box style.

## 8. Held-out test (run once, after selection)

| Test set | M5 mAP50 / mAP50-95 | M2 mAP50 / mAP50-95 | M5 no_helmet P / R / AP50 | M2 no_helmet P / R / AP50 |
|---|---|---|---|---|
| Construction-PPE official (141 images) | 0.427 / 0.177 | **0.583 / 0.278** | 0.209 / 0.125 / 0.134 | 0.404 / 0.175 / 0.155 |
| Mendeley (360 images, helmet and no_helmet labels only) | **0.671** / 0.478 | 0.667 / **0.482** | 0.531 / 0.858 / 0.704 | 0.529 / 0.832 / 0.693 |

On the Construction-PPE test set, M5's helmet AP50 fell from 0.818 to 0.334, while its person AP50 rose (0.813 against 0.776). This matches the box-style difference measured on validation. It was not verified on test, because test labels were not changed. The 40 no_helmet labels in that test set are mostly portraits, children and sport. Precision on both test sets is a lower bound because of unlabelled heads.

## 9. Runtime performance (2 November 2026, RTX 2000 Ada, 16 GB)

| Measure | Value | Source |
|---|---|---|
| Model inference, 1280×720 frame at 640 px | about 9.5–10 ms, plus about 0.8–1.2 ms pre-processing and about 1.25 ms post-processing | [`reports/runtime/model_latency.json`](../reports/runtime/model_latency.json) |
| Full pipeline, no UI, 3 repeats per clip | about 52–82 FPS depending on the clip; repeats gave identical incidents | [`reports/runtime/performance.json`](../reports/runtime/performance.json) |
| Full pipeline in the app, browser attached | about 41–60 FPS in the readiness audit; 20–40 FPS later the same day while the GPU stayed at low clocks | [`docs/records/DEMO_READINESS.md`](records/DEMO_READINESS.md), [`docs/design/REDESIGN_QA.md`](design/REDESIGN_QA.md) |
| Peak PyTorch GPU memory | 64 MB allocated, 76 MB reserved | `performance.json` |

An interleaved A/B test of the old and new interfaces at 1280×800 gave 15.7 and 16.5 FPS during the slow period ([`docs/design/qa/ab_fps_1280x800.json`](design/qa/ab_fps_1280x800.json)), showing that the interface was not the cause.

## 10. What was not evaluated

- **Real-site cameras:** no site's own cameras were used.
- **Fairness:** no analysis by skin tone, hair or headwear type.
- **Identity-switch rate:** not measured against ground truth. Track counts are reported, not people.
- **Long-duration stability:** runs were minutes, not shifts.
