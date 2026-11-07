# 17 — Annotation protocol for SafeSight evaluation datasets

Version 1.0, 5 November 2026. This protocol is the standard for every SafeSight evaluation dataset, including future site footage. It defines **what is observable**, never what a model believes. Label format: `safesight.labels/1.0` (section 9), validated by `intelligence/annotations.py`. Tooling: `scripts/validation/annotator.py` (local annotation and review app) and `scripts/validation/review_frames.py` (timestamped detail sheets).

## 1. Principles

1. **Label the footage, not the model.** Annotators never see model output, incident lists, alerts or evaluation results while labelling. The tools do not load them.
2. **Uncertainty is a label.** When something cannot be judged, say so (`uncertain`, `unobservable`), and give timing uncertainty in seconds. Never guess to complete a label.
3. **Absence of evidence is not a violation.** A head out of frame, behind an object or too small to judge is not "missing PPE".
4. **No identity.** Workers are referred to by appearance and position ("pink suit, left"), never by name, face or identity. Labels are never used for face recognition or to identify people.
5. **Footage stays local.** No upload to external services. Review images are JPEG files that git ignores.
6. **Only built capabilities are scored.** Hazards with taxonomy status `built` and a configuration that makes them evaluable on the clip. Planned and research hazards may be noted but are never scored.
7. **Labels are locked before evaluation.** A label set is hashed (`lock`) before the frozen model is run. Corrections found later go into a new version with a change log, and results are reported for both versions.

## 2. Roles and status

| Status | Meaning | May be called ground truth? |
|---|---|---|
| `provisional` | First pass by one annotator; for AI annotators always provisional | **No** |
| `reviewed` | A second, independent human reviewer agreed or corrected each event and interval | Not yet |
| `adjudicated` | Disagreements between two reviewers resolved by a third person, with reasons recorded | Yes, for the reviewed scope |
| `verified` | Adjudicated, locked, hashed, and accepted by the evaluation owner | **Yes** |

Rules:
- **AI first passes are provisional.** An AI-generated label is never ground truth because it "looks reasonable".
- **Two independent human reviewers are needed for high-severity or disputed events** (severity ≥ 4, or any event where the first pass is `uncertain`), with adjudication recorded in `reviews`.
- **Reviewers work blind.** They see the clip and the first-pass labels only, never model output. Reviewing first-pass labels is permitted; inventing events from model output is not.
- **Agreement is measured.** Report event-level agreement (matched events / union) and boundary differences on a double-labelled sample of at least 20 %.

## 3. Evaluation units and time

- **Clip:** one evaluated video file. **Recording:** the original video. **Source group:** recordings from the same site or session. Statistics resample source groups, never frames or clips from the same group independently.
- **Duplicates are evaluated once.** A transcoded copy of a recording is not a separate clip.
- **Development vs held-out.** Clips used to choose thresholds, tune trackers or design zones are *development*; results on them are reported separately and never as independent validation.
- **Times** are seconds from the start of the file (frame index ÷ fps). Every boundary has an uncertainty (`start_unc_s`, `end_unc_s`); with sampled review, the uncertainty is at least half the sampling interval.

## 4. Intervals: what may be scored, and against which denominator

Every clip is divided, per hazard, into intervals. Time not covered by an interval is **not evaluated**.

| State | Meaning | Predictions inside it | Counted in monitorable hours? |
|---|---|---|---|
| `monitorable` | The hazard condition can be judged for everyone relevant in view, or nobody is in view. Outside annotated events this is **confirmed negative** footage | Scored: matched to an event, else **false alarm** | **Yes** |
| `uncertain` | Someone relevant is visible but cannot be judged reliably (small, dim, ambiguous headwear) | Ignored unless matched to an event (**unscorable**) | No |
| `unobservable` | People may be present but cannot be seen well enough at all (distant, heads cropped, extreme blur) | Ignored (unscorable) | No |
| `unusable` | The camera image is unusable: black, fades, cross-dissolves, title cards with transitions | Ignored (unscorable) | No |
| `not_applicable` | The hazard rule does not apply to the scene (an office interview has no hard-hat requirement) | **Context false alarm** | No (separate denominator) |

**Never count `uncertain`, `unobservable` or `unusable` time as safe footage.** Camera-hours in every rate are monitorable hours only.

## 5. Events

| Field | Rule |
|---|---|
| `id` | `<clip>-E<nn>`, stable across versions |
| `hazard` | Taxonomy code (`PPE.HEAD.MISSING`, `ZONE.ENTRY`) |
| `kind` | `violation` (a positive), `uncertain` (a region where an alert can be neither confirmed nor rejected) or `not_applicable` (e.g. a bare-headed member of the public: an alert on it is a context false alarm) |
| `start_s`, `end_s`, `start_unc_s`, `end_unc_s` | Condition true and visible from start to end; uncertainty in seconds |
| `zone` | Zone name for zone events |
| `worker` | Appearance and position only; used to merge episodes and to explain errors |
| `observability` | `clear`, `partial` or `low` (section 6) |
| `requirement` | PPE only: `evident` (others in the same area wear the PPE, or a sign/site rule is visible), `assumed` (active construction work, but nobody in view wears it) |
| `evidence_frames` | Frame numbers that show the condition |
| `status`, `annotator`, `reviews` | Section 2 |

**Episode rules (pre-registered):**
- One episode per worker per continuous visible condition. A camera cut, or the worker leaving the frame for longer than 2 s, ends an episode.
- Episodes of the same worker and hazard separated by less than the incident cooldown (30 s) are merged: one alert covers both.
- **Minimum duration:** episodes shorter than 1.0 s are *optional* (detected = counted as found; missed = not counted against recall). The pipeline needs about 0.5 s of agreeing evidence by design.

## 6. Observability classes (heads)

| Class | Rule (at native resolution) | Primary metrics |
|---|---|---|
| `clear` | Head at least ~24 px tall, at least half of it visible, headwear identifiable | Required |
| `partial` | Head ~12–24 px, or partly occluded, or seen from behind, but headwear still identifiable | Required |
| `low` | Head under ~12 px, or headwear not identifiable with confidence, but the scene makes the condition likely (e.g. no bright hard hats anywhere on a rooftop crew) | **Optional**; reported as a separate "low-observability recall" |

## 7. PPE: head protection

| State | Label when |
|---|---|
| Compliant | A rigid hard hat or safety helmet is worn on the head (brim or shell visible) |
| Non-compliant (`violation`) | The head is visible (`clear` or `partial`) and bare, or covered only by a soft cap, hood, balaclava or scarf, **and** the requirement is `evident` or `assumed` |
| Uncertain | Headwear cannot be identified (backlit, rigid vs soft unclear, helmet held over the head while being put on) |
| Not applicable | The person is not subject to the rule: member of the public on a street, office or studio interview, training room |
| Not observable | Head out of frame, behind an object, or too small |

Further rules:
- **A helmet carried in the hand is not worn.** Label from the head, not from objects nearby.
- **Religious headwear** (e.g. a turban) is labelled as what it is, never as a violation without a documented site rule. No such case occurs in the current footage.
- **Person-to-PPE association:** the headwear must be on the head of that person. A helmet on a shelf or on another worker does not count.
- **Partial occlusion:** if the top of the head is hidden by an object, label `uncertain`, not `violation`.

## 8. Zones

| Field | Rule |
|---|---|
| Zone identity and boundary | The polygon from the configuration being evaluated, drawn on every review frame |
| `real_restriction` | `true` only if the footage or site documentation shows the area is restricted; demo zones drawn for illustration are `false` |
| `authorization` | `unknown` unless documented. **Never invent authorisation.** |
| Episode | Starts when the person's **feet** (bottom-centre of the body) are first inside the polygon, ends when they are last inside |
| Observability | `clear` if the feet are visible; `partial` if hidden but the position is evident from the body; otherwise an `uncertain` event |
| Normal work vs violation | When `real_restriction` is false, a zone episode measures **geometric zone-entry detection**, not a safety violation. Results must say so. A normal walkway interaction is never a violation |

## 9. Label file format (`safesight.labels/1.0`)

One JSON file per clip, in `reports/validation/annotations/<label_set>/<clip_id>.json`:

```json
{
  "schema": "safesight.labels/1.0",
  "label_set": "m2-provisional-v1",
  "clip_id": "c01", "file": "data/demo/candidates/c01.webm", "sha256": "…",
  "fps": 29.97, "frames": 10851, "duration_s": 362.06,
  "split": "held-out", "source_group": "G01-moira-close",
  "status": "provisional",
  "annotators": [{"id": "…", "kind": "ai|human", "role": "first-pass", "date": "2026-11-05",
                  "blind_to_model_output": "yes|partial|no", "notes": "…"}],
  "scope": {"PPE.HEAD.MISSING": "evaluated", "ZONE.ENTRY": "not evaluable: no zone configured"},
  "zones": [{"name": "…", "polygon": [[0, 0], …], "kind": "restricted", "real_restriction": false,
             "basis": "…", "authorization": "unknown"}],
  "intervals": [{"hazard": "PPE.HEAD.MISSING", "start_s": 0, "end_s": 22, "state": "unobservable", "note": "…"}],
  "events": [{"id": "c01-E01", "hazard": "PPE.HEAD.MISSING", "kind": "violation", "start_s": 41.0, "end_s": 58.0,
              "start_unc_s": 1.0, "end_unc_s": 2.0, "zone": null, "worker": "…", "observability": "partial",
              "requirement": "evident", "evidence_frames": [1229, 1648], "status": "provisional", "annotator": "…",
              "reviews": [], "note": "…"}],
  "people": {"distinct_workers": "…", "basis": "…"},
  "attributes": {"lighting": "…", "distance": "…", "camera": "…", "density": "…", "image_quality": "…"}
}
```

A **lock manifest** (`<label_set>.lock.json`) records the SHA-256 of every label file and of their sorted concatenation, the date, and the status. The evaluation refuses to run if any file differs from its lock.

## 10. Scoring rules derived from the labels (pre-registered)

| Rule | Value |
|---|---|
| Match | Same hazard (and zone for zone events); alert time inside `[start − max(2 s, start_unc), end + max(2 s, end_unc)]` |
| Primary positives | `violation`, observability `clear` or `partial`, duration ≥ 1 s |
| Optional | `violation` with `low` observability or < 1 s; `uncertain` events: a matching alert is not a false alarm, a miss is not a miss |
| Context | `not_applicable` events and intervals: a matching alert is a **context false alarm** |
| Duplicate | Another alert matching an already-matched episode |
| False alarm | An alert in `monitorable` time matching nothing |
| Unscorable | An alert in `uncertain`, `unobservable` or `unusable` time matching nothing; counted and reported, never scored |
| Late detection | Matched, but more than 3 s after the episode start |
| Denominator | Monitorable hours per hazard |
| Requirement sensitivity | Metrics reported with `assumed`-requirement events included and excluded |

## 11. What future site datasets must add

- Two independent human annotators from the start, with at least 20 % double-labelled.
- Identity tracks (per-person boxes on sampled frames) where tracking metrics (HOTA, IDF1, ID switches) are needed. Event labels alone cannot measure tracking.
- Site documentation for zone restrictions, authorisation and PPE rules.
- A consent and privacy record for the footage (DPIA reference) before any frame leaves the camera network.

## 12. Amendments after the M2 evaluation (5 November 2026)

These came from the M2 error analysis ([`18_VALIDATION_RESULTS.md`](18_VALIDATION_RESULTS.md) §4.4). They do not
change label set `m2-provisional-v1`, which stays as locked.

| # | Amendment | Why |
|---|---|---|
| A1 | The merge rule in §5 applies to episodes of the **same kind**. An `uncertain` stretch next to a violation is not part of the violation. The code now does this (`intelligence/annotations.py`). | The code had merged them, scoring helmet_put_on as 3.8 s instead of 1.4 s. This is a clarification, not a rule change: §5 always spoke of episodes. |
| A2 | Head sizes in §6 stay at native resolution. Each event should also record the head size **at the model's input** (native size × inference size ÷ frame width). | The c08 heads were 23–39 px natively but 8–13 px at 640 px. Recall should be reported by both. |
| A3 | Each event should carry **identity anchors**: normalised points `{t, x, y}` on the labelled worker (body centre), at least one, and more where the worker moves near others. Implemented in M2.1: schema `safesight.labels/1.1`, recorded with the annotator's marker; used by identity-aware matching (`19` §6). | Identity-agnostic matching swapped per-event latency and duration between two workers twice in M2 (c01 at 200 s, roadworks_night). |
| A4 | A correction found by looking at a model alert is **post hoc**. It goes into a new label-set version with a `changes` list (`found_by`), and that version is reported beside the original, never instead of it. Judgement calls are left for human reviewers. | Version `m2-provisional-v1.1` is the first example. |
| A5 | Lock files are `<folder>.lock.json` built from the full folder name, and verification checks that the lock names its own label set. | Locking `…-v1.1` had overwritten `…-v1.lock.json`. |
| A6 | (M3, 6 November 2026) **Independent reviewers start from an empty label set**, not from a first pass: §2's "reviewers see the first-pass labels" applies to correction reviews only, never to the two independent reviews that make a verified set. Each event records the annotator's own `confidence` (`high`, `medium`, `low`; required on violations in review packages, optional elsewhere), and each clip may carry `reviewer_notes` for the adjudicator. Interval states remain the record of uncertainty and observability; `confidence` records how sure the annotator is of an event as labelled. | Independent agreement cannot be measured if both reviewers start from the same pass; confidence lets the adjudicator and the agreement analysis see where judgement calls were made (`reports/validation/human_review/M3_REVIEW_WORKFLOW.md`). |
