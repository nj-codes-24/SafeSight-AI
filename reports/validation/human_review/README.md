# Independent human review of the evaluation labels
<!-- M3 note start -->

> **Milestone M3 (6 November 2026): use `reviewer_1/` and `reviewer_2/` and follow
> [`M3_REVIEW_WORKFLOW.md`](M3_REVIEW_WORKFLOW.md) and [`ADJUDICATION_M3.md`](ADJUDICATION_M3.md).** The M2.1 packages
> `reviewer_A/` and `reviewer_B/` below were never started and are superseded; they are kept unchanged as a record. The
> rest of this file describes the M2.1 preparation.
<!-- M3 note end -->

**Status: prepared, not started. The formal evaluation gate is BLOCKED until two independent human reviewers have
labelled all 15 clips, a third person has adjudicated their disagreements, and the result is locked as
`m2-verified-v1`.** No label in this repository is verified ground truth today. The AI first pass
(`m2-provisional-v1`) is never shown to the reviewers and is not used to make the verified set.

## Contents

| Path | What it is |
|---|---|
| `REVIEWER_INSTRUCTIONS.md` | What each reviewer does, step by step, and what they must not look at |
| `ADJUDICATION.md` | What the third reviewer does, and how the verified set is locked |
| `reviewer_A/`, `reviewer_B/` | One blinded package each. `package.json` holds the clip list (each reviewer gets a different random order), protocol version and hash, and the blinding statement. `labels/` holds an empty label file per clip (schema `safesight.labels/1.1`): no events, no intervals, no annotator yet |
| `progress.csv` | Per clip and reviewer: status (not started / in progress / done), reviewer id, number of events, share of the clip with head-protection intervals. Refresh with `status` |
| `agreement/` | Made by `agreement` once both reviewers finish: `agreement.json`, `disagreement_report.md`, `adjudication_worksheet.csv` |
| `adjudication/labels/` | Made by `adjudicate`: the merged starting point the third reviewer edits |

## Commands

```bash
python scripts/validation/human_review.py status
python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_A
python scripts/validation/human_review.py agreement
python scripts/validation/human_review.py adjudicate
python scripts/validation/human_review.py lock-verified
python scripts/validation/run_evaluation.py score --labels m2-verified-v1 --run m2-provisional-v1_20261105-101928 --out reports/validation/verified_v1
```

What each command does, in order:
- `status` refreshes `progress.csv`.
- The `annotator.py` command opens the tool in reviewer mode, scoped to one package. Reviewer B uses the same command with `reviewer_B`.
- `agreement` runs after both reviewers have finished.
- `adjudicate` builds the starting point for the third reviewer.
- `lock-verified` runs after adjudication.
- The final `score` command re-scores the existing frozen-model run against the verified labels; no new model pass is needed.

## Agreement measures

The measures are documented in `intelligence/agreement.py`. Each kind of decision gets the measure that suits it:

| Decision | Measure | Target | Why not one kappa |
|---|---|---|---|
| Interval states (monitorable, uncertain, unobservable, unusable, not applicable) | Cohen's kappa on 0.5 s samples, plus specific agreement for each state with its sample count | kappa ≥ 0.6; every state with ≥ 10 samples ≥ 0.6 | Kappa fits here, because both reviewers classify the same time units. Neighbouring samples are correlated, so no standard error is given. Kappa depends on prevalence, hence the per-state values |
| Violation events found | Raw counts (both, only A, only B) and positive specific agreement | ≥ 0.8 | On a continuous timeline the "neither" cell is undefined, so kappa would be arbitrary |
| Event boundaries | Median and 90th-percentile absolute start and end differences; temporal IoU | median ≤ 1 s | These are in seconds, against the protocol's stated uncertainty |
| Observability and requirement basis | Percent agreement; kappa only with ≥ 10 paired events | ≥ 0.6 | With few pairs, kappa is unstable and reported as insufficient |

Every measure below its target is listed under `flags`, so a weak category cannot hide behind a good overall number.

## What this does not do

- It does not label anything. It does not act as a reviewer.
- It does not mark labels verified without two different named humans and a third adjudicator. `lock-verified` checks this.
- It does not overwrite a reviewer's work (`prepare` refuses), or an existing verified set.
