# 25 — M3 executive decision report

6 November 2026 · branch `research/platform-foundations` · nothing committed or pushed · M5 model unchanged
(`E9B2583D…CC3C7534`).

## Decision in one paragraph

SafeSight is technically prepared for a supervised pilot but has **not** earned one, and has **not** earned the right
to build forklift–pedestrian intelligence. Every remaining blocker is external: two human reviewers and an
adjudicator, a partner site with a safety lead, physical cameras, and a licensing decision for the detector. Until the
labels are verified, no accuracy number in this repository is a measurement.

## Ready

| What | Where |
|---|---|
| Frozen engineering baseline, with a verifier that proves nothing historical changed | `reports/validation/m3_baseline/`, `scripts/validation/freeze_baseline.py` |
| Two blinded, empty, separately identifiable review packages with instructions, manifests, completion and blinding checks, exports; agreement analysis (per decision type, per clip, clip bootstrap); adjudication workflow; refusal to lock without two humans and a third | `reports/validation/human_review/reviewer_1`, `reviewer_2`, `M3_REVIEW_WORKFLOW.md` |
| Evaluation framework audited and corrected: camera/session scope in both matchers, identity-aware matching, end outcomes (interruption ≠ resolution), premature resolutions, same-group duplicates, per-camera and per-site tables, cluster-aware intervals; 22 new deterministic tests; historical metrics reproduced exactly | `intelligence/event_metrics.py`, `23` §3 |
| Safety-policy fix: a provisional (unconfirmed) PPE rule no longer produces confirmed violations; audited operator decisions with a headless CLI | `inference/tracker.py`, `database/database.py`, `runtime/__main__.py` |
| Industrial data acquisition plan with per-hazard minimums (the old 10-hour minimum was an order of magnitude too low) and a site checklist | `22`, `22A` |
| Physical camera acceptance plan and harness (28 cases) | `23A`, `scripts/validation/camera_acceptance.py` |
| Pilot framework and Gates A–D | `23` |
| Forklift–pedestrian technical specification | `24` |

## Requires human input (BLOCKED)

1. Two independent reviewers (about 2.6–4.4 h each) and an adjudicator (1–2 h) for the 15 benchmark clips.
2. A site safety lead to write and confirm a real PPE policy and zone documentation.
3. Legal/data-protection review for any site recording (DPIA, worker information, legal basis) ⚖.
4. A decision on the commercial detector route (M5 is non-commercial).

## Requires physical hardware (BLOCKED)

1. At least three fixed IP camera models (one with IR, one varifocal/PTZ), a PoE switch, NTP, a test space.
2. Execution of the 17 mandatory cases of `23A` on each model, plus a 24-hour stream.

## Gates

| Gate | Status |
|---|---|
| A — Controlled demo | **Met** |
| B — Supervised technical pilot | **BLOCKED** (reviewers, site, cameras, safety lead, licensing) |
| C — Operational pilot | Not reachable yet |
| D — Production readiness | Not reachable yet |

## Have we earned forklift–pedestrian intelligence?

**No — not its implementation.** Its gate (`20` §1, `24` §11) needs verified re-scoring of the existing functions
(blocked), deployment-like multi-site data (not started), physical view-integrity validation (blocked), ground-plane
calibration (not started) and a licensing decision (open). The research and specification are done and may continue
without risk: calibration design, synthetic-trajectory tests for separation/PET/TTC, and pair-labelling tooling. The
detector and alert logic should wait.

**Recommended next step:** engage the two reviewers and the adjudicator this week; in parallel, approach one warehouse
or distribution centre for a Gate B shadow pilot using `22A`, and borrow or buy three cameras for `23A`.
