# Independent human review — milestone M3 workflow (coordinator)

**Status: AWAITING EXTERNAL HUMAN REVIEW. Packages prepared 6 November 2026; no reviewer has been engaged.** Nothing in
this folder is ground truth until two independent human reviewers have finished, a third person has adjudicated, and
`lock-verified` has written `reports/validation/annotations/m2-verified-v1/`. No AI system acts as a reviewer, and none
of the AI first-pass labels (`m2-provisional-v1*`) is shown to the reviewers or used to build the verified set.

This supersedes the M2.1 packages `reviewer_A/` and `reviewer_B/`, which were never started. They are left exactly as
they were, as a record; do not hand them out.

## What is here

| Path | What it is |
|---|---|
| `reviewer_1/`, `reviewer_2/` | One blinded package per reviewer. `package.json` (package id, label set, clip order, protocol hash, blinding statement); `INSTRUCTIONS.md` (exact instructions for that reviewer); `clip_manifest.csv` (clips in that reviewer's order, hazards to label, zones drawn, estimated minutes); `labels/` (one empty label file per clip, schema `safesight.labels/1.1`); `progress.csv`; `completion_check.json`; `exports/` (flat CSV of the reviewer's events and intervals) |
| `review_progress.csv` | Both reviewers side by side, per clip |
| `M3_REVIEW_WORKFLOW.md` | This file |
| `ADJUDICATION_M3.md` | Instructions for the third reviewer |
| `agreement/` | Written by `agreement` after both finish: `agreement.json`, `disagreement_report.md`, `adjudication_worksheet.csv` |
| `adjudication/` | Written by `adjudicate`: the third reviewer's workspace |

Package identities: `reviewer_1` = `SSV-M3-R1-5266E182` (label set `m2-human-r1`), `reviewer_2` = `SSV-M3-R2-3E205120`
(label set `m2-human-r2`), both made against protocol SHA-256 `040CDE72166A…` (version with amendment A6). Re-running
`prepare` with the same clips and protocol reproduces the same ids and orders, and refuses if a package already holds
work. If the protocol changes before reviewers start, re-prepare (the empty packages are regenerated with the new hash);
after they start, record the change and tell both reviewers.

## Who is needed

| Role | Requirement | Effort |
|---|---|---|
| Reviewer 1 and reviewer 2 | Safety-literate; at least one with construction or industrial PPE experience; must not have seen SafeSight output for these clips | About 2.6–4.4 hours each (26 minutes of video at 6–10 × real time) |
| Adjudicator | A third person, same requirements, not reviewer 1 or 2 | About 1–2 hours |
| Coordinator | Runs the commands below; may be anyone, but does not label | Under 1 hour |

## Steps

```bash
# 0. (done) prepare the packages
python scripts/validation/human_review.py prepare
# 1. give each reviewer only their own package; each runs
python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_1
# 2. track progress at any time
python scripts/validation/human_review.py status
# 3. when a reviewer says they are done: completion and blinding checks (must show READY)
python scripts/validation/human_review.py check
python scripts/validation/human_review.py export
# 4. both READY: agreement and the adjudication worksheet
python scripts/validation/human_review.py agreement
python scripts/validation/human_review.py adjudicate
# 5. adjudicator works (ADJUDICATION_M3.md); then
python scripts/validation/human_review.py lock-verified
# 6. re-score the existing frozen-model runs against the verified labels (no GPU pass)
python scripts/validation/run_evaluation.py score --labels m2-verified-v1 --run m2-provisional-v1_20261105-101928 --out reports/validation/verified_v1_m2logic
python scripts/validation/run_evaluation.py score --labels m2-verified-v1 --run m2-provisional-v1.2_20261105-195803 --identity --out reports/validation/verified_v1_m21logic
```

## Completion checks (`check`)

Blocking, per clip: the file validates; "Clip complete" is ticked; a named human annotator; intervals cover the whole
clip for every hazard in scope; every violation has the reviewer's confidence; every zone violation names its zone; no
forbidden field (`split`, `source_group`, predictions, incidents, model output, scores, risk). Per package: exactly the
package's clips; only the expected files (anything else, such as a copied results file, fails the blinding check); one
reviewer id. Warning only: events without identity anchors.

## Agreement measures (`agreement`, `intelligence/agreement.py`)

| Decision | Measure | Target | Why not one kappa |
|---|---|---|---|
| Interval states (monitorable, uncertain, unobservable, unusable, not applicable) — the uncertainty and observability agreement | Cohen's kappa on 0.5 s samples; specific agreement per state; per-clip kappa; clip-level bootstrap interval | kappa ≥ 0.6; each state with ≥ 10 samples ≥ 0.6; no clip below 0.4 | Both reviewers classify the same time units, so kappa fits. Samples inside a clip are correlated: no standard error; the clip bootstrap is the honest (wide) interval. Kappa depends on prevalence, hence per-state values |
| Violation events found | Counts (both, only 1, only 2) and positive specific agreement; per clip; clip bootstrap | PSA ≥ 0.8 | "Neither reviewer found an event" is not a countable cell on a timeline, so kappa is undefined |
| Temporal boundaries | Median and 90th-percentile absolute start and end differences; temporal IoU | median ≤ 1 s | Seconds, against the protocol's stated uncertainty |
| Hazard category | Violation events paired across hazards; confusion and count of different hazards | 0 differences | Two hazards and few events: a count is clearer than a coefficient |
| Zone assignment | Percent agreement on the zone of paired events | ≥ 0.8 (with ≥ 5 pairs) | Very few pairs per clip |
| Event kind (violation vs uncertain vs not applicable) | Kind confusion on events paired regardless of kind | every difference adjudicated | The decision that most often separates a positive from an unscorable stretch |
| Observability, requirement basis | Percent agreement; kappa with ≥ 10 pairs | ≥ 0.6 | Unstable with few pairs |
| Annotation confidence (high/medium/low) | Percent agreement; linearly weighted kappa with ≥ 10 pairs | reported, no target | Ordinal; a disagreement here is information, not an error |

Every measure below target is listed under `flags` in `agreement.json` and at the top of `disagreement_report.md`; a
weak category cannot hide behind a good aggregate. **κ ≥ 0.6 is a target for interval states only.** Meeting it does not
make the labels correct; it makes them reproducible enough to adjudicate.

## What must not happen

- No reviewer sees model output, the AI first pass, results, or the other reviewer's package before `agreement` runs.
- No AI tool labels, pre-fills, or "suggests" events in the packages.
- No one edits a package's labels except its reviewer; the coordinator only runs the commands.
- `lock-verified` is never bypassed; a verified set is never overwritten (corrections make a new version).
