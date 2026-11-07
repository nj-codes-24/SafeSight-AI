# 18 — Validation results (milestone M2)

Frozen M5 model through the headless runtime, scored at event level against locked labels, 5 November 2026.
Branch `research/platform-foundations`, all changes uncommitted.

> **PROVISIONAL.** The labels are an AI first pass (status `provisional`) with no independent human review, so by
> the protocol in [`17_ANNOTATION_PROTOCOL.md`](17_ANNOTATION_PROTOCOL.md) they are **not ground truth**, and none of
> the numbers below is a validated measurement. They come from 26 minutes of public, mostly handheld and edited
> footage. This is not industrial-site validation. The model (M5) is research-only because of its training-data
> licence. Nothing here supports a claim of production readiness, certification or accident prevention.

## Executive summary

**Decision: SafeSight has not yet earned the move to its next major capability-development phase.** The
measurement infrastructure is ready, but there is no human-verified ground truth yet. Even on the provisional labels,
the one capability with held-out evidence, missing head protection, is weak: it finds half the violations and raises
two noisy alerts for every real one. The fixes are specific, and most are cheap. They come before any new hazard type.

| Question | Answer on this dataset (provisional labels v1) |
|---|---|
| What does it detect reliably? | **Nothing yet, by the evidence standard set for M2.** The best result is bare heads that are close, front-facing and sustained: 2 of 2 development episodes, detected in about 0.5 s. Zone entry was 4 of 4, but on only 20 s of development footage with demo zones. |
| What does it miss? | Missing head protection: **3 of 6 held-out episodes** (recall 0.50, Wilson 95 % 0.19–0.81), plus 2 of 2 low-observability crowd episodes (optional). The misses are soft caps and hoods (seen from behind) and heads of 8–13 px at the model's input. |
| How often does it raise false alerts? | **2 genuine false alarms in 0.244 monitorable hours (8.2 per hour, Poisson 95 % 0.9–29.6)**, both compliant workers. A further **8 alerts fired where the PPE rule does not apply** (an office or classroom, and a passer-by). Only **1 in 3 scorable PPE alerts (5 of 15) was a real violation.** |
| How quickly? | Median 0.54 s from onset for the 5 detected PPE episodes, but 2 of the 3 held-out detections were late (5.9 s and 10.8 s). Zone entry had a median of 0.46 s. |
| Which conditions cause failures? | Look-alike headwear: dark hard hats read as bare heads, and soft caps or hoods not read as bare. Small heads at the model's 640 px input. A hard hat cut off by the frame edge. And, above all, the rule firing in places where head protection isn't required. |
| What has sufficient evidence? | **No capability.** The cut-off was 10 or more primary episodes from 3 or more independent source groups. PPE has 8 episodes; held-out has 6 from 2 groups. Zone entry has 4 episodes, development only. |
| What needs further validation? | Everything, starting with human-verified labels on these clips. Then deployment-like footage: fixed cameras, real restricted zones, several sites, hours rather than minutes. |
| What next? | P0: verified labels, worker-aware matching, a fix for exposure-time collapse, a bigger dataset. P1: PPE-required areas, alert grouping, a frame-edge rule, headwear data, small-head resolution. See §10. |

What M2 did establish:

- A reproducible measurement pipeline: a frozen manifest, locked and hashed labels, scoring with ignore and context regions, cluster-bootstrap CIs, evidence frames, and a cause for every error.
- The runtime processed all 15 clips (46,002 frames) with no stuck camera, in 7 min 25 s for 26 min of video.
- Five evaluation defects were found during M2. Three are fixed; two are open as P0.

## 1. What was measured

| Item | Value |
|---|---|
| Model | `models/best.pt`, SHA-256 `E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534` (unchanged), YOLO26n at 640 px, classes person / helmet / no_helmet |
| Thresholds | person 0.35, PPE 0.30, no_helmet 0.60, confirm 0.5 s (vote ≥ 70 %), cooldown 30 s, lost track 2 s (code defaults; `models/runtime_config.json` holds only zones) |
| Tracker | ByteTrack, `inference/bytetrack_safesight.yaml` SHA `0E1F26D7…` |
| Runtime | `runtime/` headless service, batched backend, file sources with `realtime: false` (every frame, media time), separate database per run |
| Risk policy | `default-0.1`, **draft** (unchanged) |
| Labels | `m2-provisional-v1`, 15 files, combined SHA `5FA81F00…4BAB2`, locked before the run (primary). `m2-provisional-v1.1` is a post-hoc sensitivity check (§3.2). |
| Scoring | Tolerance max(2 s, annotation uncertainty); late detection > 3 s; episodes < 1 s or low observability are optional; same-worker violation episodes merged when < 30 s apart; cluster bootstrap by source group, n = 4000, seed 0 |
| Footage | 15 recordings from 12 independent source groups, 1,562.7 s in total. Of the PPE time: 878.9 s monitorable, 62.5 s where the rule does not apply (context), 621.3 s ignored (uncertain, unobservable or unusable) |
| Split | Held-out: 10 recordings, 831.5 s monitorable. Development: 5 recordings used in earlier tuning, 47.4 s monitorable, reported separately |
| Records | `reports/validation/evaluation_manifest.json` (git head, code hashes, clip hashes), `baseline_metrics.json` |

Hazards in scope are the built ones only. `PPE.HEAD.MISSING` is scored on every clip. `ZONE.ENTRY` is scored only on
the two clips with configured zones. Those zones were drawn for the demo, so this measures geometric zone-entry
detection, not real restricted-area violations.

## 2. Results

### 2.1 Missing head protection (`PPE.HEAD.MISSING`), labels v1 (primary)

| Split | Episodes | TP | FN | FP | Context alerts | Unscorable | Precision (Wilson 95 %) | Recall (Wilson 95 %) | Recall, cluster bootstrap | F1 | FP per monitorable h (Poisson 95 %) | Alert precision¹ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Held-out** | 6 (2 groups) | 3 | 3 | 2 | 7 | 4 | 0.60 (0.23–0.88) | **0.50 (0.19–0.81)** | 0.00–0.75 | 0.55 | 8.7 (1.0–31.3) in 0.231 h | **0.25** |
| Development | 2 (2 groups) | 2 | 0 | 0 | 1 | 0 | 1.00 (0.34–1.00) | 1.00 (0.34–1.00) | — | 1.00 | 0 (0–280) in 0.013 h | 0.67 |
| All | 8 (4 groups) | 5 | 3 | 2 | 8 | 4 | 0.71 (0.36–0.92) | 0.63 (0.31–0.86) | 0.00–1.00 | 0.67 | 8.2 (0.9–29.6) in 0.244 h | 0.33 |

¹ TP ÷ (TP + FP + duplicates + context alerts): the share of scorable alerts an operator would find correct. There were no duplicates.

- **Not sufficient** for any estimate by the pre-set rule (10 or more episodes from 3 or more groups with positives). The cluster bootstrap for held-out precision collapses to 0.60–0.60 because every held-out true and false alert came from one source group (G01, three recordings from one site). That is the clustering problem, made visible.
- **Evident-only variant** (drops the two c08 episodes, where the requirement is assumed): held-out 3 of 4, recall 0.75 (0.30–0.95), from 1 group.
- **Optional episodes:** 1 of 7 detected. These are low-observability violations and uncertain events. The two low-observability crowd violations (c09, c10) were both missed.

### 2.2 Zone entry (`ZONE.ENTRY`), development clips only

| Episodes | TP | FN | FP | Monitorable | Median latency | Duration error after attributing by worker² |
|---|---|---|---|---|---|---|
| 4 (2 groups) | 4 | 0 | 0 | 19.9 s | 0.46 s | ≤ 0.7 s |

² The scorer matches without identity. It swapped two roadworks_night workers and reported errors of +7.35 s and −7.44 s. Matched by worker from the evidence frames, they are +0.60 s and −0.70 s. See §4.4.

**Insufficient:** 20 seconds of development footage with demo zones is a functional check, not a measurement.

### 2.3 Temporal performance (PPE, required episodes)

| Event | Split | Onset | First alert | Latency | Late? | True duration | Alert duration |
|---|---|---|---|---|---|---|---|
| c01-E01 pink suit, navy soft cap | held-out | 41.0 | 46.88 | 5.88 s | yes | 17.0 s | 1.1 s |
| c01-E03/E04, two workers² | held-out | 200.5 | 201.03, 211.31 | 0.53 s (white suit), 10.81 s (pink suit) | one late | 29.4 s | ~4 s each |
| helmet_put_on-E01 | dev | 0.0 | 0.46 | 0.46 s | no | 1.4 s | 1.9 s |
| framing_bare_head-E01 | dev | 0.0 | 0.54 | 0.54 s | no | 9.0 s | 8.4 s |

- **Latency:** the median of all 9 required matches, PPE and zone, is 0.53 s. On held-out footage, 2 of 3 detections came more than 3 s late. Both were the worker in the navy soft cap. Their raw no_helmet score was 0.15–0.39 at 41–47 s, with the same head sometimes scored helmet 0.29–0.38, and 0.47–0.57 at 201–211 s, just under the 0.60 threshold. The white-suited worker beside them scored 0.67 and was caught in 0.53 s.
- **Duration collapse (new finding):** on held-out footage, PPE incidents closed within about 1–4 s while the violation lasted 17–29 s (median absolute error 25 s). No second alert followed during those episodes; the 30 s cooldown runs from an incident's end. So the exposure time the risk engine escalates on is underestimated by an order of magnitude.
- **Repeated alerts for one event:** none; there were 0 duplicates.

### 2.4 Worker tracking

There is no identity ground truth, so ID switches, IDF1 and HOTA **cannot be measured** and are not reported. The
proxy below compares track IDs issued with distinct people labelled. On edited footage every cut starts new tracks,
so this is not a switch count.

| Clip | People labelled | Track IDs | Confirmed tracks (≥ 1 s) | IDs per person |
|---|---|---|---|---|
| helmet_put_on | 1 | 1 | 1 | 1.0 |
| framing_bare_head | 2 | 2 | 2 | 1.0 |
| roadworks_night | 5 | 7 | 6 | 1.4 |
| c03 (zoom and tilt at the end) | 1 | 2 | 1 | 2.0 |
| track_work_day | 3 | 9 | 7 | 3.0 |
| c07 (documentary with cuts) | 1 | 3 | 3 | 3.0 |

Fragmentation shows up indirectly in the duration collapse (§2.3) and in the two latency and duration swaps (§4.4).

### 2.5 Robustness breakdown

| Slice | Episodes or time | Result |
|---|---|---|
| PPE, observability `clear` | 1 episode | 1 detected; **insufficient** |
| PPE, `partial` (small, occluded or rear view) | 7 episodes | 4 detected; **insufficient** (n < 10) |
| PPE, `low` | 2 episodes | 0 detected; **insufficient** |
| False alarms by lighting, distance or camera motion | each slice 6–647 monitorable s | Only two slices reach 0.1 h. "Bright daylight" (c00, c01; 0.112 h) has 1 false alarm, 8.9 per h. "Far to medium, pans and zooms" (c00–c02, one site; 0.18 h) has 2 false alarms, 11.1 per h. Every other slice is **insufficient** |
| Night | 1 clip, 12.4 s | **insufficient** |
| Worker density, scene complexity, camera angle | — | Not sliced: every slice would be one or two recordings |

All slices are confounded with recording. The qualitative pattern from the error analysis (§4) is more informative
than any of these rates.

## 3. Label quality

### 3.1 Status

| Requirement in `17` | State |
|---|---|
| Labels created blind to model output | **Partly.** The AI annotator saw M1 incidents for the development clips, and the repository's aggregate unseen-footage notes for the held-out clips |
| Independent human review | **Not done** |
| Two annotators on ≥ 20 % with agreement measured | **Not done** |
| Adjudication | **Not done** (no event has severity ≥ 4; both hazards are severity 3) |
| Locked and hashed before evaluation | **Done**: `m2-provisional-v1.lock.json`, combined `5FA81F00…`, re-verified after the lock-path bug (§8) |
| Status | `provisional`; `ground_truth: false` in every output |

Cross-check: the earlier human by-eye violator counts in `reports/unseen_gt/ground_truth.json` agree with v1 on 9
held-out clips. That file describes c11 as a meeting; the footage is forklift training with an office scene.

### 3.2 Label errors found during error analysis (post hoc, not blind)

| Version | Change | Found by | Effect |
|---|---|---|---|
| v1.1 | c01 230.5–245 s, `uncertain` → `monitorable`: the worker clearly wears a dark grey hard hat | Inspecting alert INC-…-26ABA020 at full resolution | That alert becomes a false alarm: held-out precision 0.50 (was 0.60), 12.8 false alarms per h (was 8.7), recall unchanged |

v1.1 only makes the model look worse. It is reported in `reports/validation/sensitivity_v1.1/` beside v1, never
instead of it. Judgement calls were not changed by the AI; they are in the review queue (§9).

## 4. Error analysis

Every error was inspected using:
- the runtime's evidence frame;
- full-resolution crops (`scripts/validation/review_frames.py`);
- the frozen model's raw output down to 0.10 (`scripts/validation/probe_detections.py`).

Causes are in `reports/validation/error_causes.json`, and the frames are in `reports/validation/representative_failures/`
(local only, git-ignored).

### 4.1 False alarms (genuine: compliant worker flagged)

| Alert | Clip, time | What happened | Raw score | Cause | Fix type |
|---|---|---|---|---|---|
| INC-…-BC126DEA | c00 237 s | White hard hat worn tilted back and cut off by the top of the frame, face visible | 0.68 | Occlusion (frame edge) | Rule |
| INC-…-5EDF203C | c02 318 s | Black climbing-style hard hat seen from behind; alert open 15 s at MEDIUM risk | 0.68 | Other: dark helmet read as bare head | Data |
| INC-…-26ABA020 (v1.1) | c01 241 s | Dark grey hard hat, close and unoccluded | 0.78 | Other: dark helmet read as bare head | Data |

### 4.2 Missed violations

| Event | What the model did | Cause | Fix type |
|---|---|---|---|
| c01-E02, white coverall with dark soft cap or hood, mostly rear view, 19.5 s | no_helmet 0.16–0.38 on the head; no head box at all in rear views with the hood up | Excessive confidence threshold, on look-alike headwear | Data (threshold alone does not separate; see §4.5) |
| c08-E01, worker beside an excavator, 9.5 s | Head 24–39 px in the source, **8–13 px at the 640 px model input**; no_helmet 0.10–0.36 | Small object size | Architecture |
| c08-E02, second worker | Head 23–30 px in the source, 8–10 px at input; no_helmet 0.10–0.25, helmet 0.15 | Small object size | Architecture |

### 4.3 Alerts where the rule does not apply, and unscorable alerts

| Alerts | What happened | Cause | Fix type |
|---|---|---|---|
| 7 × c11, 16–24 s | Correct bare-head detections of people in an office and classroom; 7 alerts in 8 s | Other: PPE rule applied where head protection isn't required; plus event aggregation | Rule |
| roadworks_night 10.9 s | A passer-by outside the works area | Other: member of the public outside the work-area polygon | Rule |
| c11 58.9 s (unscorable) | A bare-headed instructor with a megaphone in a warehouse; requirement unknown | Ambiguous scene | Rule (per-area requirement) |
| c01 32.6 s (unscorable) | The navy-cap worker at ~30 px head height, 8 s before the labelled onset | Ambiguous scene | Evaluation (human decision) |
| c02 189 s (unscorable) | Cross-dissolve between shots | Other: editing artefact | Not solvable; does not occur on a live camera |

### 4.4 Evaluation defects exposed by the error analysis

| Defect | Evidence | Status |
|---|---|---|
| Matching ignores worker identity, so with two workers in one window latency and duration attach to the wrong worker | c01 200–230 s (alerts W63 and W62 credited to the opposite events); roadworks_night zone (±7.4 s errors are really ≤ 0.7 s) | **Open, P0** (counts unaffected here) |
| Same-worker merge also joined an `uncertain` stretch onto a violation | helmet_put_on scored as 3.8 s instead of 1.4 s | **Fixed** in `intelligence/annotations.py`, with a test; only that one duration error changed |
| `lock()` used `with_suffix`, so locking `…-v1.1` overwrote `…-v1.lock.json` | Scoring v1 failed verification | **Fixed** (`lock_path`, label-set name checked), with a test. v1's lock was restored and its recomputed combined hash matches the pre-run value exactly, which proves the v1 files never changed |
| The observability size rule (24 px / 12 px) is defined at native resolution, which is not what the model sees | The c08 heads were "partial" at 23–39 source px but 8–13 px at the 640 px model input | **Open, P0**: `17` §12 now asks for the model-input size as well |
| The old denominator, ignore and context semantics | See §7, question 10 | Fixed at the start of M2 |

### 4.5 Ranked failure categories

Ranked by frequency, then by operational significance. Counts use v1, with v1.1 in brackets.

| Rank | Category | Errors | Why it matters |
|---|---|---|---|
| 1 | **No notion of where PPE is required** (offices, classrooms, passers-by, instructors) | 8 context alerts + 1 unscorable | Over half of all scorable alerts. Removing them would raise alert precision from 0.33 to 0.71. It is the first thing an operator would switch off |
| 2 | **Look-alike headwear**: dark hard hats → "no helmet"; soft caps and hoods → not confidently "no helmet" | 1 (2) false alarms, 1 miss, 2 late detections | Wrong in both directions: it accuses compliant workers and stays silent on real violations |
| 3 | **Small heads at model input** (1080p wide shots downscaled 3× to 640 px) | 2 misses + 2 of 2 low-observability crowd episodes | Typical of a fixed site camera covering a large area |
| 4 | **Exposure-time collapse** (incidents close while the violation continues) | Every held-out detection | The risk engine's escalation-by-exposure cannot work on this evidence |
| 5 | Frame-edge truncation | 1 false alarm | Cheap rule |
| 6 | Editing artefacts | 1 unscorable | Not relevant to live cameras |

The threshold is not the lever. The genuine false alarms scored 0.68–0.78. The misses peaked at 0.16–0.38 for the
soft cap and 0.10–0.36 for the small heads. The late-detected soft cap sat at 0.15–0.39 (sometimes classed as helmet)
and then 0.47–0.57. Lowering no_helmet to about 0.35–0.45 might bring those in, would not reach the small heads
reliably, and could not remove a single false alarm. Any threshold study belongs on development data, not on these
held-out clips.

### 4.6 The three most serious weaknesses, and where the fix lives

| # | Weakness | Rule engine | Better tracking | New training data | Different architecture | Not solvable with this input |
|---|---|---|---|---|---|---|
| 1 | PPE rule fires where it doesn't apply | **Yes**: PPE-required areas and schedules per camera, work-area scoping, alert grouping | — | — | Scene classification could help later (research) | Whether a helmet is required is not visible; it must be configured |
| 2 | Look-alike headwear | Partly: a frame-edge rule; an "unknown" state for rear views | — | **Yes**: dark and coloured hard hats, rear views, soft caps, hoods, beanies, bump caps; hard-negative mining | Possibly a second-stage head classifier on native-resolution crops | A hood that fully covers the head from behind |
| 3 | Small heads | — | — | Some help: small-object examples | **Yes**: tiled or higher-resolution inference, or a crop classifier on person boxes at source resolution | Heads under ~12 px in the **source**; better camera placement is the real fix |
| (4) | Exposure collapse | **Yes**: close an incident only after the state has stayed compliant or unknown for N s, not on the first flip | **Yes**: track continuity in moving shots | — | — | — |

## 5. Runtime under the evaluation workload (simulated cameras)

These are video files replayed on one workstation (RTX 2000 Ada, Xeon w5-2565X), not RTSP streams and not a site. A
short run is a throughput test, not a reliability test. No power or clock settings were changed. Full results are in
`reports/runtime/multicamera_benchmark_eval.json`; the earlier benchmark on the 720p demo clips is in
`reports/runtime/multicamera_benchmark.json`.

The workload is evaluation clips c01 and c02 (1920×1080 VP9), c11 (720×576 Theora) and c12 (1280×720 Theora),
cycled across cameras. The batched backend was used throughout, with a 6 s warm-up and a 20 s window.

| Cameras | Mode | Aggregate FPS, earlier → eval | Per-camera FPS (eval) | Drops (eval) | End-to-end p95 (eval) | Frame-to-incident latency max (eval) | Process CPU (eval)³ | RSS (eval) | CUDA peak, earlier → eval | GPU % @ mean SM clock, earlier → eval | Health (eval) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | throughput | 65.6 → 61.6 | 61.7 | 0 % | 116 ms | 139 ms | 183 % | 1.46 GB | 87 → 87 MB | 32 % @ 1512 → 29 % @ 1677 MHz | STREAMING |
| 2 | throughput | 91.8 → 94.5 | 47.2–47.3 | 0 % | 148 ms | 181 ms | 245 % | 1.61 GB | 102 → 102 MB | 34 % @ 1362 → 31 % @ 1519 | STREAMING |
| 4 | throughput | 118.1 → 130.8 | 31.5–33.1 | 0 % | 212–261 ms | 262 ms | 252 % | 1.80 GB | 131 → 168 MB | 33 % @ 1094 → 40 % @ 2312 | STREAMING |
| 8 | throughput | 90.3 → 140.1 | 13.7–19.7 | 0 % | 343–530 ms | 463–483 ms | 291 % | 2.33 GB | 186 → 261 MB | 35 % @ 782 → 40 % @ 2489 | STREAMING |
| 1 | live 15 fps | 15.0 → 15.0 | 15.0 | 0 % | 34 ms | — | 63 % | 1.41 GB | 87 → 87 MB | 25 % @ 786 → 41 % @ 453 | STREAMING |
| 2 | live 15 fps | 29.9 → 30.0 | 15.0 | 0 % | 53–59 ms | — | 119 % | 1.55 GB | 102 → 102 MB | 42 % @ 574 → 40 % @ 943 | STREAMING |
| 4 | live 15 fps | 59.9 → 60.0 | 15.0 | 0 % | 66–89 ms | 145 ms | 171 % | 1.74 GB | 130 → 168 MB | 32 % @ 1178 → 30 % @ 1360 | STREAMING |
| 8 | live 15 fps | 92.6 → 115.8 | 13.7–14.9 | 0–8.1 % (earlier 13.7–32 %) | 104–214 ms | 246–258 ms | 311 % | 2.20 GB | 186 → 261 MB | 33 % @ 812 → 34 % @ 1907 | all STREAMING (earlier: some DEGRADED) |
| 8 | live 10 fps | 79.9 → 79.9 | 9.9–10.0 | 0 % | 84–100 ms | 99–109 ms | 245 % | 2.17 GB | 186 → 264 MB | 30 % @ 940 → 33 % @ 1230 | STREAMING |

³ Percent of one logical CPU; the machine has 36.

- **Capacity statement (unchanged):** 4 cameras at 15 fps, or 8 at 10 fps, with no drops and every camera STREAMING, under both workloads. 8 cameras at 15 fps passed this time but not before.
- **The 8-camera improvement is not a software or workload effect.** The GPU's mean SM clock was 1,907–2,489 MHz this time against 782–812 MHz before. The driver chose those clocks; nothing was changed. At 8 cameras capacity follows the GPU clock, so the conservative figure stands until a longer run with clocks logged settles it.
- **The evaluation workload costs more CPU** (183 % against 137 % for one camera in throughput mode) because 1080p VP9 decoding is heavier than the 720p demo MP4s. Even so, it stays under 3.2 cores of 36. RSS rises about 5 %. CUDA peak memory rises to 261 MB at 8 cameras, because of larger batches.
- **Event-processing latency** (frame capture to incident stored) stays under 0.26 s in live mode. The detection latency in video time (§2.3) comes from the 0.5 s confirmation, which the pipeline applies at the analysis rate, so it is the same in live mode.
- **The full evaluation pass** ran 15 cameras concurrently in file mode: 46,002 frames in 445 s, model p50 8.9 ms, p95 16.3 ms, mean batch 1.95, no stuck cameras.
- **Not tested:** RTSP from a real camera, runs longer than 20 s, power-managed clocks held fixed.

## 6. Answers in one place

| Question | Answer |
|---|---|
| What can SafeSight reliably detect on this dataset? | Nothing meets the sufficiency rule. On the best case, a close, front-facing bare head held for several seconds, it fired every time (2 of 2 development, plus 1 of 1 for the close white-suited worker on held-out) within about 0.5 s. |
| What does it fail to detect? | Soft caps and hoods (especially from behind); heads of 8–13 px at model input; low-observability crowds (0 of 2). It also misses how long a violation lasts. |
| How frequently does it generate false alerts? | 8.2 genuine false alarms per monitorable hour (0.9–29.6) with v1; 12.1 (2.4–35.3) with v1.1. Plus 8 alerts where the rule does not apply: 7 in 62.5 s of office and classroom footage, and a passer-by. Only one alert in three was a real violation. |
| How quickly does it detect visible events? | Median 0.53 s across all required matches; held-out PPE at 0.53, 5.9 and 10.8 s. |
| Which conditions cause failures? | Context (no PPE requirement), look-alike headwear, small heads, a frame-edge cut-off, and incident closing in moving shots. |
| Which capabilities have sufficient evidence? | None. |
| Which require further validation? | Missing head protection (verified labels, then 50 or more episodes from 10 or more sites); zone entry (real restricted zones, real exposure, hours of footage); RTSP operation (never tested on a camera). |
| What should be improved next? | §10. |

## 7. Methodology audit (Phase 1 questions)

| # | Question | How it works now |
|---|---|---|
| 1 | What is a detection? | A model box at 640 px above its class threshold (person 0.35 to start or keep a ByteTrack track; helmet 0.30; no_helmet 0.60), with heads associated to a tracked person's head region (`inference/ppe_association.py`). Per frame; never an alert by itself. |
| 2 | What is a safety incident? | NO_HELMET: the per-track vote is ≥ 70 % "no helmet" over at least 0.5 s of frames, within a window of three times that. ZONE_INTRUSION: a tracked person's foot point inside a zone polygon for the 0.5 s entry debounce. `IncidentManager` then raises one incident with an evidence frame and a draft-policy risk assessment. |
| 3 | How are repeated detections grouped? | Per (type, track, zone). A 30 s cooldown in video time runs from the incident's end. A new track inside the cooldown and within one box height of a lost one counts as the same worker. |
| 4 | Start and end times? | Start is the confirmation time (`incident_context.opened_t`), so always at least ~0.5 s after onset. End (`closed_t`) is when the state changes, the track has been lost for 2 s, or the stream ends. §2.3 shows that end is too early in practice. |
| 5 | How are duplicate alerts handled? | Runtime: cooldown plus lost-track dedup. Evaluation: an extra alert that falls in the window of an episode already matched is a duplicate, counted separately (not a false alarm) and included in alert precision. |
| 6 | How are camera-hours calculated? | **Before M2:** the whole clip duration. **Now:** labelled `monitorable` seconds only. Footage where the rule does not apply is counted separately as context hours; uncertain, unobservable, unusable and unlabelled time is excluded. |
| 7 | How are missed events identified? | A required episode (violation, clear or partial observability, ≥ 1 s, requirement basis present) with no same-hazard alert in [start − max(2 s, uncertainty), end + max(2 s, uncertainty)], same zone for zone hazards. |
| 8 | How are false alarms identified? | An alert in no episode window, not inside a context region (else it is a context alert), and not inside an ignore region (else it is unscorable). |
| 9 | How are confidence intervals computed? | Wilson score for precision and recall; Byar's approximation to the exact Poisson interval for false-alarm counts, divided by monitorable hours; and a percentile cluster bootstrap over source groups (4000 resamples; undefined if fewer than half the resamples are defined). |
| 10 | Problems in the matching logic? | Found and fixed at the start of M2: (a) the false-alarm denominator included unobservable and irrelevant footage; (b) no ignore regions, so alerts where the truth is unknowable counted as false alarms; (c) alerts where the rule does not apply were conflated with false alarms; (d) the tolerance ignored annotation uncertainty; (e) sub-second and unobservable violations counted as misses; (f) greedy matching could prefer a nearby episode over the one containing the alert; (g) intervals assumed independence across events from one recording. Found during M2: (h) identity-agnostic matching (open, P0); (i) cross-kind merging and (j) the dotted lock path (both fixed, §4.4). |

## 8. Statistical integrity

- **Duplicates and overlaps:** the 5 demo files are copies of candidate recordings (dHash overlap 1.0, or 0.77 for helmet_put_on). Each is scored once, under its demo name. c00, c01 and c02 are distinct recordings but share a site and camera operator, so they form one source group, as do c09 and c10. See `clip_manifest.csv` and `overlap_check.json`.
- **Clustering:** every held-out true positive and genuine false alarm comes from source group G01 (c00–c02, one site). The cluster bootstrap shows this directly: the precision interval collapses to one value, and the recall interval spans 0 to 0.75.
- **Raw counts** are shown next to every rate. Every rate with fewer than 10 events or under 0.1 h is marked insufficient in `baseline_metrics.json` (`sufficient_for_recall_estimate: false` everywhere).
- **What a useful estimate needs:** at recall around 0.8, a ±10-point Wilson interval needs about 60 episodes before clustering. At around 8 false alarms per hour, a ±25 % interval needs about 8 or more monitorable hours. This dataset has 8 episodes and 0.24 h.
- **No extrapolation:** nothing here is projected to RTSP streams, longer runs or industrial sites.

## 9. Human verification needed before scoring can be formal

Formal scoring is paused here, as the brief requires. Exactly this is needed:

1. **Two independent human annotators**, safety-literate and at least one with construction PPE experience. They label all 15 evaluated clips (26 min of video) with `scripts/validation/annotator.py`, starting from **empty** label sets `m2-human-a` and `m2-human-b`. They must not see `eval_runs/`, `representative_failures/`, `error_causes.json`, this document or the AI labels. Expect about 3–4.5 h each at 6–10× real time.
2. **Agreement:** interval-state agreement on 1 s bins (Cohen's κ, target ≥ 0.6), event-level agreement using the same matcher at 2 s tolerance, and boundary error (target median ≤ 1 s).
3. **Adjudication** by a third person (about 1–2 h) of every disagreement and every item in the review queue below, giving `m2-verified-v1` with status `verified`. Then lock it.
4. **Rescore the same run.** No new GPU pass is needed: `python scripts/validation/run_evaluation.py score --labels m2-verified-v1 --run m2-provisional-v1_20261105-101928`.

**Review queue.** These are AI judgement calls a human must make:

| Item | Question |
|---|---|
| c01 22–40 s | Is the pink-suited worker's navy cap identifiable as a soft cap at ~30 px head height? If yes, c01-E01 starts by ~30 s and the 32.6 s alert is a true detection |
| c01 230.5–245 s | Confirm the dark grey hard hat (the v1.1 change) |
| c01-E02 | Is it a soft cap or a coverall hood, and is the violation basis "evident"? |
| c08-E01/E02 | Are both workers bare-headed, and is head protection required beside a working excavator in a street (v1 says "assumed")? |
| c02 316–324 s, c00 237 s | Confirm the dark climbing-style hard hat, and the hard hat cut off by the frame |
| c11 | Is head protection required for instructors and visitors in the forklift warehouse? |
| framing_bare_head-E01, roadworks_night E01/E03 | Requirement basis; the uncertain workers |
| All clips | Monitorable vs uncertain boundaries, especially in edited footage |

Even verified, these 15 clips stay a development-grade benchmark. The next phase also needs deployment-like footage
(§10, P0.4).

## 10. Prioritised improvements

Each item below gives: the failure it addresses (with its evidence), the expected benefit, the approach, the data needed, the complexity (S ≤ 2 engineer-weeks, M 2–6, L 6–12), how to validate it, and the regression risk.

### P0 — Reliability and evaluation defects

**P0.1 Human-verified labels** (§9).
- Failure / evidence: no ground truth. Every result is provisional. 9 judgement calls are open.
- Benefit: the M2 numbers become a real baseline.
- Approach: the annotator tool, two blind annotators, adjudication.
- Data: the 15 existing clips.
- Complexity: S (8–11 person-hours).
- Validation: κ ≥ 0.6, plus the lock.
- Regression risk: none.

**P0.2 Worker-aware matching.**
- Failure / evidence: latency and duration swapped between workers (c01 200 s; roadworks_night).
- Benefit: correct per-event latency and exposure. It is required before exposure can be measured.
- Approach: events carry a position hint (normalised foot point at a reference time); alerts carry the worker box at confirmation; matching requires overlap.
- Data: a position per event in the label schema (`safesight.labels/1.1`).
- Complexity: S.
- Validation: unit tests with two workers, then rescore.
- Regression risk: counts may shift where hints are wrong; keep the identity-agnostic result alongside.

**P0.3 Observability at model-input resolution.**
- Failure / evidence: "partial" c08 heads were 8–13 px at input.
- Benefit: the slices reflect what the model sees.
- Approach: the protocol amendment (`17` §12, done), plus a head-size field computed from the P0.2 position hint and the inference size.
- Data: none.
- Complexity: S.
- Validation: unit test.
- Regression risk: none.

**P0.4 Deployment-like evaluation set.**
- Failure / evidence: 8 episodes, 4 groups, 0.24 h. The bootstrap is degenerate. The footage is handheld and edited.
- Benefit: the only route to a capability claim.
- Approach: fixed-camera recordings at 10 or more sites (partner, own sites with consent, or licensed footage), labelled blind.
- Data: ≥ 50 PPE episodes, ≥ 10 monitorable hours, real restricted zones.
- Complexity: L (mostly access and consent).
- Validation: sufficiency rule met per hazard.
- Regression risk: none.

**P0.5 Exposure-time collapse.**
- Failure / evidence: held-out incidents last 1–4 s against violations of 17–29 s.
- Benefit: the risk engine's exposure escalation works, and the duration error becomes measurable.
- Approach: closing hysteresis (close only after N s compliant or unknown); keep the incident open across short track loss.
- Data: verified labels with end times.
- Complexity: S–M.
- Validation: duration error on verified labels, latency unchanged.
- Regression risk: longer incidents could merge two violations; worker-aware matching (P0.2) checks this.

### P1 — Higher value from the current capabilities

**P1.1 PPE-required areas.**
- Failure / evidence: 8 context alerts + 1 unscorable. Alert precision would rise from 0.33 to 0.71 if they were gone.
- Benefit: the largest single cut in operator-visible noise.
- Approach: PPE policy per camera, zone and schedule (zones already exist); people whose foot point is outside the work area are not evaluated.
- Data: configuration only.
- Complexity: S.
- Validation: on **new** footage, or verified labels with zones drawn blind to the alerts.
- Regression risk: a misconfigured area hides real violations, so show the coverage in the UI.

**P1.2 Alert grouping.**
- Failure / evidence: 7 alerts in 8 s from one scene.
- Benefit: one actionable alert per situation.
- Approach: group same-hazard alerts within T s on one camera into one alert with a count.
- Data: none.
- Complexity: S.
- Validation: unit tests, then rescore with grouped alerts counted once.
- Regression risk: two separate violations reported as one; the group still keeps per-worker records.

**P1.3 Frame-edge rule.**
- Failure / evidence: c00 false alarm.
- Benefit: removes a class of false alarm.
- Approach: a head box touching the image border, or a person box clipped at the top, gives "unknown".
- Data: none.
- Complexity: S.
- Validation: unit test, then rescore.
- Regression risk: misses workers at the frame edge, which is acceptable because the next frames usually show them.

**P1.4 Headwear data.**
- Failure / evidence: dark hard hats (2 false alarms in v1.1), soft cap and hood (1 miss, 2 late).
- Benefit: errors in both directions on the main capability.
- Approach: licence-clean images of dark and coloured hard hats, rear views, soft caps, hoods, beanies and bump caps; hard-negative mining; retrain only after the licensing decision.
- Data: several thousand head crops with clean licences (M5 is research-only).
- Complexity: M–L.
- Validation: a held-out headwear test set, then rescore the M2 set and P0.4.
- Regression risk: catastrophic forgetting of the existing classes, so compare per class.

**P1.5 Small heads.**
- Failure / evidence: c08 heads at 8–13 px input; 0 of 2 low-observability.
- Benefit: wide fixed views become usable.
- Approach: tiled or higher-resolution inference on wide views, or a second-stage head classifier on source-resolution crops of person boxes.
- Data: small-head examples.
- Complexity: M.
- Validation: recall by model-input head size (P0.3), plus the runtime benchmark (§5).
- Regression risk: more GPU per camera (fewer cameras per box); more texture false alarms.

**P1.6 Threshold and vote study.**
- Failure / evidence: misses scored 0.16–0.55 against false alarms at 0.68–0.78.
- Benefit: an operating curve instead of one fixed point.
- Approach: sweep no_helmet, confirm time and vote ratio on **development data only**, and report the curve.
- Data: a development set separate from P0.4.
- Complexity: S.
- Validation: held-out is touched once, at the end.
- Regression risk: overfitting to the development footage.

### P2 — Additional hazard opportunities (only after P0 and P1)

**P2.1 Real restricted zones.**
- Failure / evidence: zone entry has only 20 s, with demo zones.
- Benefit: makes the second built capability measurable.
- Approach: zones drawn from site rules on P0.4 footage, with authorisation recorded.
- Data: P0.4.
- Complexity: S.
- Validation: the sufficiency rule.
- Regression risk: none.

**P2.2 Vehicle–pedestrian proximity.**
- Failure / evidence: none measured; the inventory shows the scenes exist (c02 telehandler, c08 excavator, c11 forklifts).
- Benefit: the logistics wedge in `12`.
- Approach: ground-plane calibration plus separation and closing speed (roadmap M2).
- Data: vehicle classes; licence-clean.
- Complexity: L.
- Validation: labelled conflict episodes.
- Regression risk: a new false-alarm source.

**P2.3 Hi-vis.**
- Failure / evidence: none measured.
- Benefit: a second PPE item.
- Approach: only once P1.4 has shown headwear can be made reliable.
- Data: licence-clean.
- Complexity: M.
- Validation: the same protocol.
- Regression risk: the same as P1.4.

### P3 — Research

**P3.1 Exposure analytics and leading indicators** (needs P0.5).
- Benefit: shift-level exposure instead of single alerts.
- Approach: aggregate verified exposure time per area.
- Data: P0.4.
- Complexity: M.
- Validation: agreement with verified durations.
- Regression risk: none.

**P3.2 Operator-feedback learning loop.**
- Benefit: hard negatives from reviewed alerts.
- Approach: the review queue feeds labelled crops into a candidate dataset, with consent.
- Data: pilot feedback.
- Complexity: M.
- Validation: held-out improvement.
- Regression risk: feedback bias.

**P3.3 Scene-context classification** (office or site).
- Benefit: could automate P1.1.
- Approach: a scene classifier as a suggestion, never an override.
- Data: scenes.
- Complexity: M.
- Validation: P1.1 configurations as the reference.
- Regression risk: silent suppression; keep it advisory.

## 11. Reproduce

```bash
python scripts/validation/inventory.py
python scripts/validation/run_evaluation.py run
python scripts/validation/run_evaluation.py score
python scripts/validation/run_evaluation.py score --labels m2-provisional-v1.1 --run m2-provisional-v1_20261105-101928 --out reports/validation/sensitivity_v1.1
python scripts/validation/render_failures.py
python scripts/validation/probe_detections.py c08 2.5,6.2 --crop 0.12 0.45 0.42 0.85
python scripts/benchmark/runtime_benchmark.py --batched-only --clips data/demo/candidates/c01.webm,data/demo/candidates/c02.webm,data/demo/candidates/c11.ogv,data/demo/candidates/c12.ogv --out reports/runtime/multicamera_benchmark_eval.json
```

What each command does:
- `inventory.py` writes the manifest, the overlap check and the contact sheets.
- `run_evaluation.py run` is the frozen pass, about 7.5 min on the RTX 2000 Ada.
- The first `score` scores the primary result, v1.
- The second `score` scores the v1.1 sensitivity check against the same run.
- `render_failures.py` writes the evidence frames (local only).
- `probe_detections.py` shows raw model output for diagnosis.
- `runtime_benchmark.py` runs the Phase 9 benchmark.

The run is deterministic up to GPU numerics; the scoring is deterministic.
