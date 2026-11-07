# M2 validation summary
<!-- M3 note start -->

> **Status after milestone M3 (6 November 2026):** the numbers below are unchanged and still **provisional**. Independent
> human review packages are ready (`human_review/reviewer_1`, `reviewer_2`; `human_review/M3_REVIEW_WORKFLOW.md`) and
> **blocked on two human reviewers and an adjudicator**. The scorer gained camera/session scoping in both matchers,
> end-outcome reporting (a camera interruption is never a resolution), premature-resolution and same-group duplicate
> counts, and per-camera and per-site tables; re-scoring the stored M2 and M2.1 runs reproduced every earlier metric
> exactly. Current status: [`M3_VALIDATION_STATUS.md`](M3_VALIDATION_STATUS.md).
<!-- M3 note end -->

**PROVISIONAL — the labels are an AI first pass, not human-verified ground truth.** The footage is 26 minutes of public
demo video, not an industrial site. The model (M5) is research-only. The full report, with error analysis and
priorities, is [`docs/product_research/18_VALIDATION_RESULTS.md`](../../docs/product_research/18_VALIDATION_RESULTS.md).

**Verdict:** the next capability phase is not earned yet. Verify the labels first (§9 of the report), then fix the
P0/P1 items, then measure on deployment-like footage.

## Headline (labels `m2-provisional-v1`, locked before the run; frozen M5 through the headless runtime)

| Hazard | Split | Episodes | TP | FN | FP | Context alerts | Precision (95 %) | Recall (95 %) | FP per monitorable h (95 %) | Sufficient? |
|---|---|---|---|---|---|---|---|---|---|---|
| PPE.HEAD.MISSING | held-out | 6 | 3 | 3 | 2 | 7 | 0.60 (0.23–0.88) | 0.50 (0.19–0.81) | 8.7 (1.0–31.3), 0.231 h | No |
| PPE.HEAD.MISSING | development | 2 | 2 | 0 | 0 | 1 | 1.00 (0.34–1.00) | 1.00 (0.34–1.00) | 0, 0.013 h | No |
| ZONE.ENTRY (demo zones) | development | 4 | 4 | 0 | 0 | 0 | 1.00 (0.51–1.00) | 1.00 (0.51–1.00) | 0, 0.006 h | No |

- **Alert precision for PPE:** 5 of 15 scorable alerts were real violations (0.33).
- **Median latency** from onset to alert: 0.53 s. 2 of the 3 held-out PPE detections were late (5.9 s and 10.8 s).
- **Exposure time:** PPE incidents closed after 1–4 s while the violations lasted 17–29 s.
- **Sensitivity check `m2-provisional-v1.1`** (one post-hoc correction): held-out precision 0.50, 12.8 false alarms per hour; recall unchanged. See `sensitivity_v1.1/`.
- **Top failures:** the PPE rule fires where it does not apply (8 alerts); look-alike headwear (dark hard hats flagged as bare heads, soft caps and hoods not flagged); heads of 8–13 px at the model's input.

## Files

| File | Content |
|---|---|
| `clip_manifest.csv` | Every footage file: hashes, decode check, format, provenance, licence, split, source group, duplicates, visual description |
| `overlap_check.json` | Perceptual-hash overlap between files |
| `clip_review.json` | The reviewer's visual descriptions, merged into the manifest |
| `annotations/m2-provisional-v1/` + `.lock.json` | Primary labels, locked before the run (combined SHA `5FA81F00…`) |
| `annotations/m2-provisional-v1.1/` + `.lock.json` | v1 plus one post-hoc correction, with a change log in each file |
| `evaluation_manifest.json` | Frozen conditions: model, thresholds, tracker, zones, policy, runtime, scoring rules, label lock, clip hashes, code hashes, per-clip run summary |
| `baseline_metrics.json` | All metrics by hazard, variant (all / evident-only) and split, with Wilson, Poisson and cluster-bootstrap intervals; robustness slices; tracking proxy; scoring-code hashes |
| `per_hazard_metrics.csv`, `per_clip_metrics.csv` | Tabular versions |
| `false_alarm_analysis.csv` | Every non-matching alert: category, label state, evidence path, cause, fix type |
| `missed_event_analysis.csv` | Every missed episode, with nearby alerts, cause and fix type |
| `detection_latency.csv` | Every matched episode: onset, first alert, latency, late flag, duration error |
| `error_causes.json` | Causes assigned after inspection |
| `representative_failures/` | Evidence frames and montages (JPEG, local only, git-ignored) |
| `eval_runs/<run>/` | Run database, status, log and manifest (database git-ignored) |
| `sensitivity_v1.1/` | The same reports scored against v1.1 |
| `review/` | Contact sheets, detail crops and model probes (JPEG, local only) |

## Reproduce

```bash
python scripts/validation/run_evaluation.py run
python scripts/validation/run_evaluation.py score
python scripts/validation/run_evaluation.py score --labels m2-provisional-v1.1 --run m2-provisional-v1_20261105-101928 --out reports/validation/sensitivity_v1.1
python scripts/validation/render_failures.py
```

The first command (`run`) needs the GPU, about 7.5 min. The others need no model, except `probe_detections.py` (diagnostic only).
