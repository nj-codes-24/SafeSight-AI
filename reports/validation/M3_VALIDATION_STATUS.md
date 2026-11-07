# Validation status after milestone M3 (6 November 2026)

**No result in this repository is a validated measurement yet.** The M2 numbers in `validation_summary.md` are
unchanged and provisional (AI first-pass labels, 26 minutes of public demo footage, research-only model).

| Item | State |
|---|---|
| Ground truth | **AWAITING EXTERNAL HUMAN REVIEW.** Packages `human_review/reviewer_1` (`SSV-M3-R1-5266E182`) and `human_review/reviewer_2` (`SSV-M3-R2-3E205120`) are empty and blinded; workflow in `human_review/M3_REVIEW_WORKFLOW.md`, adjudication in `human_review/ADJUDICATION_M3.md`. `completion_check.json` in each package currently says NOT READY (nothing labelled) |
| Label sets | `m2-provisional-v1` `5FA81F00…`, `v1.1` `0BC85D6F…`, `v1.2` `34F4633D…`: locks verify, byte-identical. `m2-verified-v1` does not exist |
| Scorer | Corrected and extended in M3 (`docs/product_research/23` §3); the M3 re-audit added a guard refusing pooled multi-camera inputs in which an item omits its camera or session. Re-scoring the stored M2 run (`m2-provisional-v1_20261105-101928`) and the M2.1 runtime run (`m2-provisional-v1.2_20261105-195803`) reproduced every earlier metric exactly; only new fields were added |
| New diagnostic fields (provisional labels) | M2.1 runtime run, PPE: 2 matches ended on a confirmed resolution, 3 with an unknown outcome, **1 premature resolution** (c01-E03, soft cap read as a helmet; known from `19` §12); 0 same-group duplicates. Zone: 4 matches, all ended at end of clip |
| Historical results | Not modified. `freeze_baseline.py verify` against `m3_baseline/baseline_record.json` checks every file under `reports/validation` and `reports/runtime` |
| Physical cameras | **BLOCKED (hardware).** Plan `docs/product_research/23A_…`; harness `scripts/validation/camera_acceptance.py`; no `camera_acceptance/` results exist |
| Deployment-like data | Not started; plan `docs/product_research/22_…` |

Next, in order: two reviewers and an adjudicator → `lock-verified` → re-score both stored runs against
`m2-verified-v1` (commands in `human_review/M3_REVIEW_WORKFLOW.md`) → decide whether the helmet and zone functions are
reliable enough for a supervised pilot (Gate B, `docs/product_research/23` §5).
