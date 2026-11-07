# 23 — Industrial pilot readiness (milestone M3)

6 November 2026, branch `research/platform-foundations`, all changes uncommitted. This document answers: what is
actually built and tested, what the safety policy does, and what a warehouse or factory pilot would have to pass, gate
by gate. Companions: data plan [`22`](22_INDUSTRIAL_DATA_ACQUISITION_PLAN.md) and checklist
[`22A`](22A_SITE_DATA_COLLECTION_CHECKLIST.md); physical camera plan
[`23A`](23A_PHYSICAL_CAMERA_ACCEPTANCE_TEST_PLAN.md); next capability [`24`](24_FORKLIFT_PEDESTRIAN_RESEARCH.md).

> **Passing unit tests is not passing a deployment gate.** 258 automated tests pass (§7). None of them involves a real
> site, a physical camera, or human-verified labels, so none of them moves SafeSight past Gate A.

## 1. Status matrix (audited from the code and tests, not from earlier documents)

Legend: **Done** = implemented and covered by automated tests · **Partial** · **Documented** = specified, not
implemented · **Not started** · **BLOCKED** = needs external human input or physical hardware.

### 1.1 The outstanding M2.1 requirements

| # | Requirement | Status | Evidence | What is still missing |
|---|---|---|---|---|
| 1 | Correct incident exposure duration | **Done** (engineering); validation **BLOCKED** | `inference/incident_lifecycle.py`; `tests/test_lifecycle.py` (29); exposure bounded by observation; diagnostic duration error 7.4 → 0.6–0.7 s on provisional labels (`19` §8) | Measurement on verified labels. M3 found that the M2.1 runtime's one remaining large error is a **premature resolution** (c01-E03, soft cap read as a helmet), now counted by the scorer |
| 2 | Temporary detection-loss handling | **Done**; field behaviour unverified | Grace period, UNOBSERVED state, position re-association, re-observation after unknown end; tests in `test_lifecycle.py` | Never exercised on fixed industrial cameras; position re-association can merge two workers who swap places during occlusion (`19` §12) |
| 3 | Configurable PPE requirements by site and zone | **Done**, and corrected in M3; real policy **BLOCKED** | `intelligence/ppe_policy.py` (site, camera, zone, effective times, active flag, conflicts); `runtime.ppe_policy`; M3: a **provisional** entry now gives a review item, never a confirmed violation (`tests/test_policy_safety.py`) | A site safety administrator must write and confirm the real policy. Recurring schedules (shifts) are not supported, only effective windows |
| 4 | Worker-identity-aware event matching | **Done**, extended in M3 | `match_identity` with anchors (M2.1, 11 tests). M3: camera and session scope enforced in the time-only matcher too; pooled multi-camera inputs tested (`tests/test_evaluation_integrity.py`) | Depends on identity anchors that human reviewers record; where absent, the documented time fallback is used and counted (`matched_unknown`) |
| 5 | Duplicate incident handling | **Done** | Alert groups and burst-batched notifications (M2.1); M3 scorer separates duplicates in the same alert group (no second notification) from duplicates the operator was notified about again | Cross-camera duplicates are not merged, by design (no cross-camera identity) |
| 6 | Partial visibility and uncertainty | **Partial** | NOT_OBSERVABLE category, frame-edge rule, ambiguous zone membership when feet are cut off; M3 test: a worker whose head is never seen is never counted compliant | Head size at the model's input (`17` A2) is specified but not recorded by the tools; no small-head rule (deliberately, no evidence) |
| 7 | Independent human annotation verification | **BLOCKED** (human reviewers) | M3 packages `reviewer_1/` (`SSV-M3-R1-5266E182`) and `reviewer_2/` (`SSV-M3-R2-3E205120`), instructions, manifests, completion and blinding checks, exports, agreement and adjudication tooling, `lock-verified` refusal rules; 20 tests | Two independent reviewers and a third adjudicator. **No reviewer has been engaged; I did not and will not act as one** |

### 1.2 The wider reliability architecture

| Area | Status | Notes |
|---|---|---|
| Hazard taxonomy and risk engine | Done | Risk policy `default-0.1`, **draft**; never applies reductions while draft |
| Annotation protocol | Done | `17`, amendment A6 in M3 (independent reviews start empty; reviewer confidence; reviewer notes) |
| Initial validation results | Done, **provisional** | `18`; AI first-pass labels; next phase not earned |
| Human annotation tooling | Done | Annotator reviewer mode with confidence field and adjudicator notes (M3) |
| Event-level evaluation | Done, corrected in M3 | §3 |
| Incident lifecycle | Done | `19` |
| Alert grouping and deduplication | Done | `19` §5 |
| Headless multi-camera runtime | Done (file simulation) | `15`, `16`; 4 × 15 FPS and 8 × 10 FPS on one workstation |
| RTSP with a physical camera | **BLOCKED** (hardware) | Harness and plan ready (`23A`) |
| 24 h / 7-day soak | Not started | Needs a physical camera or a long synthetic run; part of `23A` S06 |
| Camera view-change detection | Done (simulated movements only) | `21`; physical validation **BLOCKED** (hardware) |
| Zone invalidation and revalidation | Done | Operator `view accept | verify-zones` |
| Incident acknowledgement | **Partial → improved in M3** | Operator decisions now append to `incident_reviews` (who, when, previous status, reason) from the dashboard and from `python -m runtime incident review`. No authentication or roles: the reviewer name is self-declared |
| Notification delivery (e-mail, webhook), escalation display | Documented | Interface exists (`drain_notifications`); nothing delivered |
| Shadow mode (record, do not alert) | Documented | Needed for Gate B; today every run is effectively shadow because nothing is delivered |
| Per-camera monitoring coverage report (hours actually monitorable) | Partial | Outages and view events are recorded per camera; no report turns them into monitored hours |
| Evidence redaction, retention, roles, signed configuration | Not started | `10` §7; required before Gate C |
| Ground-plane calibration | Not started | Required for forklift–pedestrian work (`24` §5) |
| Product-line detector on commercially usable data | Not started (licensing decision open) | M5 is research-only; any commercial pilot needs it (`10` §6) |
| Deployment-like evaluation set | Not started; **plan done** | `22` |

## 2. Safety-policy review (Phase 7)

| Question | Answer in the code | M3 change |
|---|---|---|
| Site-specific PPE requirements | Entries carry `site`; the runtime passes each camera's `site` | — |
| Zone-specific requirements | Zone-scoped entries beat camera-wide ones; conflicts at one scope are ambiguous (review) | — |
| Policy versioning | Every decision carries policy version, document status and entry status; runtime status shows them | — (history and signing of policy changes are not built: roadmap C5) |
| Configurable activation | `active` flag and effective windows | — |
| Unconfigured policy | Review item, never a confirmed violation, never silence | — |
| **Draft or provisional rules** | **Before M3, a provisional entry produced confirmed violations** (category `confirmed_violation`) | **Fixed:** only an entry confirmed by a named person (`established_by`) can make a confirmed violation; provisional gives a review item and the new category `requirement_not_confirmed` (also never "confirmed compliance") |
| Unknown worker visibility | `not_observable`, reported apart from `uncertain`; never counted as compliant | Test added |
| Incident exposure | Bounded by observation | — |
| Camera interruption | Unknown outcome at the last reliable observation; never a resolution, never position-linked afterwards | Scorer now reports end outcomes; an interruption is never counted as a resolution (tests for all seven unknown ends) |
| Operator acknowledgement | Operator status survives detector closure | **Audit trail** (`incident_reviews`) and headless CLI |
| Incident resolution | Only positive evidence held for `resolve_seconds`, a debounced zone exit, or leaving the required area | Scorer counts **premature resolutions** (resolved while the labelled violation continued) |

Principles kept: SafeSight never infers a requirement from the image; a camera that cannot observe proves nothing about
safety; draft rules are never presented as approved policy; site policies need authorised human configuration.

## 3. Evaluation framework audit (Phase 4)

| Must handle | How | Test |
|---|---|---|
| Camera identity | Both matchers refuse pairs naming different cameras (M3: time-only matcher too) | `test_a_worker_on_one_camera_never_matches_an_episode_on_another` |
| Session identity | Same rule for sessions | `test_sessions_are_scoped_like_cameras` |
| Worker identity | Anchors vs track boxes; inconsistent pairs never match; unknown falls back to time and is counted | `test_identity_matching.py` (11) |
| Fallback without camera on labels | Allowed and documented (per-clip labels = one camera session) | `test_documented_fallback_when_labels_do_not_name_the_camera`, `test_one_camera_with_unnamed_labels_still_uses_the_fallback` |
| Pooled inputs where an item omits its camera or session (M3 re-audit) | **Refused** (`ValueError`): once inputs name more than one camera or session, an unnamed item could match across cameras. Before the re-audit this was documented but not enforced | `test_pooled_inputs_with_an_unnamed_item_are_refused` (4) |
| Hazard category, zone identity | Must match | `test_hazard_and_zone_identity` |
| Uncertain / unobservable / unusable intervals | Unscorable, not false alarms; not in the denominator | `test_uncertain_and_unobservable_time_is_unscorable_not_a_false_alarm` |
| Duplicate predictions | Duplicates; alert-group duplicates counted apart | `test_exact_duplicate_prediction_is_a_duplicate`, `test_tracker_reset_fragment_…` |
| Multiple simultaneous workers, crossings | Identity-aware global assignment | `test_identity_matching.py` |
| Tracker resets | A fragment of the same worker is a duplicate, another worker is a false alarm | `test_tracker_reset_fragment_is_a_duplicate_and_same_group_is_counted_apart` |
| Interrupted observation (camera moved or blocked) | Labels mark `unusable`; incidents end with an unknown outcome; never a resolution | `test_an_interruption_is_never_counted_as_a_resolution` (7 end reasons) |
| Clustered data | `summarise()` pools per-clip rows and bootstraps whole sites/source groups; a result resting on one site shows an interval from 0 | `test_summarise_*` (3) |

Metrics now produced by `run_evaluation.py score`: precision, recall and F1 per hazard; false alarms per monitorable
camera-hour (Poisson and cluster bootstrap); latency; duration error by end outcome; premature resolutions; missed
events; duplicate rate (and same-group duplicates); **per camera and per site tables**; per clip; recall by observability;
unscorable alerts by label state; Wilson and cluster-bootstrap intervals; a sufficiency flag (≥ 10 episodes from ≥ 3
clusters). **Regression check:** re-scoring the stored M2 run and the M2.1 runtime run reproduced every previously
reported metric exactly; only new fields were added (written to a scratch folder; no stored result was touched).

**Finding, not a tuning:** of the 9 required matches in the M2.1 runtime run, 2 ended on a confirmed resolution and 7
with an unknown outcome (observation lost or end of clip), and 1 of the 2 resolutions was premature. On provisional
labels and 26 minutes of public footage this is a diagnostic, not a measurement. Nothing was tuned on it.

## 4. Pilot framework

A supervised pilot that could be offered to a warehouse or manufacturing site. Durations are planning estimates.

| Step | What happens | Owner | Output |
|---|---|---|---|
| 1. Site survey | Checklist `22A` sections A–C; hazard areas, documented PPE rules and restricted areas, traffic rules | SafeSight lead + site safety lead | Signed checklist, data agreement, DPIA reference |
| 2. Camera suitability | Inventory (`22A` D); probe each candidate camera (`camera_acceptance.py probe`, 10 min); exclude handheld, moving or unsuitable views | SafeSight + site IT | Camera list with delivered resolution, FPS, mount, distance band |
| 3. Physical camera acceptance | Mandatory cases of `23A` on each camera model used | SafeSight | `results.csv` per camera; verdict "mandatory cases passed" |
| 4. Zone calibration | Zones drawn on the verified reference view; `view verify-zones` by a named person; zone kinds match the site's documents | Site safety lead approves | Zones with documentation references |
| 5. PPE policy configuration | Policy file written with the safety lead; every entry `confirmed` with `established_by`; document `approved` with approver and date | Site safety lead | `config/ppe_policy.json`, version recorded |
| 6. Installation | Edge machine on the camera network, outbound internet off; model hash verified; runtime as a service with restart policy | SafeSight + site IT | Installation record, model SHA-256, configuration hashes |
| 7. Camera-health verification | Runtime status shows every camera STREAMING and `VIEW_STABLE`; outage test (S03) repeated on site | SafeSight | Status snapshot |
| 8. View-change verification | One staged knock or cover per camera, if the site allows, with the operator revalidation exercised | SafeSight + site | View events acknowledged by name |
| 9. Shadow operation | Alerts recorded, **not delivered**; notifications reviewed weekly | Safety officer | Weekly review log |
| 10. Ground-truth sampling | Recorded footage sampled (stratified by camera and shift), labelled by two independent reviewers blind to SafeSight, adjudicated, locked (`human_review.py`) | Reviewers (not SafeSight staff who saw alerts) | Locked verified label set per pilot period |
| 11. Safety officer review | Every alert dispositioned (`runtime incident review --by`): real, false alarm, not applicable | Safety officer | `incident_reviews` audit trail |
| 12. Incident acknowledgement workflow | Agreed response times for review items; who acknowledges view events | Site | Written procedure |
| 13. Performance review | `run_evaluation.py score` on the locked labels; per camera, per site; false alarms per monitorable camera-hour; latency; premature resolutions; operator time per alert | SafeSight + safety officer | Pilot report |
| 14. Completion | Against the gate criteria below | Site + SafeSight | Go / no-go for the next gate |

## 5. Gates

Gates are cumulative. **Passing a gate is a decision by named people on recorded evidence, not a test result.**

### Gate A — Controlled demonstration

Purpose: show technical functionality on known footage.

| Criterion | Status |
|---|---|
| Runtime processes recorded clips end to end; incidents, lifecycle, notifications, view monitoring and audit recorded | **Met** (M1–M3 tests, demo runs) |
| Results labelled "controlled demonstration; provisional labels; research-only model" wherever shown | **Met** (documents and reports carry the warning) |
| No claim of accuracy beyond the provisional numbers | **Met** |

**May be claimed:** "a working prototype with an auditable incident pipeline", nothing about field accuracy.

### Gate B — Supervised technical pilot

Purpose: run on a real site, under the safety team's supervision, in shadow mode.

| Criterion | Status |
|---|---|
| Verified labels for the existing benchmark (`m2-verified-v1`), and the frozen model re-scored on them | **BLOCKED** (human reviewers) |
| Site authorisation, DPIA, worker information (`22A` A–B) | **BLOCKED** (no partner site) |
| Physical camera acceptance: mandatory `23A` cases passed for each camera model | **BLOCKED** (hardware) |
| Real PPE policy confirmed and approved by the site; zones verified by a named person | **BLOCKED** (site safety lead) |
| Shadow mode: no alert delivered to workers or supervisors as a live safety signal | Ready by construction (no delivery is built); must be written into the pilot agreement |
| Licensing route for the model used on site agreed (M5 is non-commercial; a research pilot only, or the product-line detector) | **Open decision** |
| Incident review audit, view-event acknowledgement | **Met** (M3) |

**Exit criteria:** the pipeline ran on the site's cameras for the agreed period without a stuck camera; every alert was
dispositioned by the safety officer; a stratified sample was labelled independently; the data needed for Gate C exists.
**May be claimed:** "operated at site X in shadow mode under supervision". No accuracy claim beyond that sample.

### Gate C — Operational pilot

Purpose: measure detection reliability and workflow usefulness over a representative period.

| Criterion | Target (to be agreed with the site's safety professional before the period starts) |
|---|---|
| Duration and coverage | At least 4 weeks; all shifts the site runs; ≥ 100 monitorable camera-hours per hazard (`22` §2.4) |
| Verified labels | Two independent reviewers, adjudicated; interval-state κ ≥ 0.6 and violation PSA ≥ 0.8, per hazard and with no clip below κ 0.4 hidden in the pool |
| Recall per hazard | Lower 95 % bound (cluster bootstrap by camera) above the agreed target |
| False alarms | Upper 95 % bound per monitorable camera-hour below the rate the site accepts (for example 0.25 per camera-hour) |
| Premature resolutions and duplicates | Reported; the site agrees they are acceptable |
| Workflow | Median time to disposition review items; share of alerts the safety officer judged useful |
| Operations | Uptime per camera, view events and their acknowledgement times, monitored hours vs scheduled hours |
| Controls | Evidence redaction, retention job, access roles in place (`10` §7) |

**May be claimed:** measured performance at that site and period, with intervals. Not general performance.

### Gate D — Production readiness

Requires substantially stronger evidence and controls:
- Gate C met at **≥ 10 independent sites** of at least 3 site types, with held-out sites scored once on frozen
  configuration (`22`);
- a commercially licensed detector line;
- an independent security review (threat model `10` §7.2, penetration test);
- a legal and data-protection assessment per market (EU AI Act classification, GDPR/DPDP, works councils) ⚖;
- a safety assessment of the product's role, confirming it is advisory and does not replace engineered controls;
- signed configuration and model updates with rollback, monitoring, support processes;
- documentation per `09` §6.

**May be claimed:** only what the multi-site evidence supports, with its intervals and limits.

## 6. Where SafeSight stands

| Gate | Status |
|---|---|
| A — Controlled demo | **Met** |
| B — Supervised technical pilot | **BLOCKED**: human reviewers, a partner site, physical cameras, a site safety lead, and a licensing decision |
| C — Operational pilot | Not reachable before B |
| D — Production readiness | Not reachable before C |

The technical preparation for Gate B is complete: review packages, evaluation framework, policy rules, audit trail,
camera acceptance harness, data plan and checklists. What remains is external: people, a site and hardware.

## 7. Tests at the end of M3

| Check | Result |
|---|---|
| Full suite (weights, clips, processed data present) | **258 passed** (211 before M3 + 47 new) |
| CI simulation (PyTorch, Ultralytics, Streamlit blocked) | 239 passed, 6 skipped |
| New in M3 | `tests/test_evaluation_integrity.py` (22), `tests/test_policy_safety.py` (9), `tests/test_camera_acceptance.py` (5), `tests/test_baseline_record.py` (2), 9 new in `tests/test_human_review.py` |
| Baseline integrity | `python scripts/validation/freeze_baseline.py verify`: `ok` — model hash, label locks, historical results and benchmarks unchanged |
| M3 re-audit (same day) | Pooled-scope guard added (§3); **264 passed** (258 + 6 new cases); both stored runs re-scored into a scratch folder: every stored metric identical (M2 run time-only, M2.1 run identity-aware) |
