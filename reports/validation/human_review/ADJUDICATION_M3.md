# Adjudication instructions (third reviewer) — milestone M3

You resolve disagreements between reviewer 1 and reviewer 2. You must not be either of them, and you must not have seen
SafeSight output, the AI first-pass labels, or any evaluation result for these clips. You do not relabel clips from
scratch; you decide the listed disagreements from the footage.

## Before you start

1. Read `docs/product_research/17_ANNOTATION_PROTOCOL.md`, including §12 (A1–A6).
2. The coordinator has run `agreement` and `adjudicate`. You receive:
   - `agreement/disagreement_report.md` — a summary (read it, but decide each item from the footage);
   - `agreement/adjudication_worksheet.csv` — one row per disagreement;
   - `adjudication/labels/` — the merged starting point.
3. Open the workspace:
   `python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/adjudication`

## The merged starting point

For each clip:
- events both reviewers found, with the same hazard, kind, observability, requirement basis and zone: boundaries
  averaged, marked `"adjudication": "agreed"`;
- paired events that differ in an attribute: marked `pending`;
- events only one reviewer found: marked `pending`, with their origin in `from` (`1:<id>` or `2:<id>`);
- reviewer 1's intervals (the worksheet lists every interval-state difference of 1 s or more);
- `reviewer_confidence` on paired events, and each reviewer's clip notes in `reviewer_notes`.

## For every worksheet row and every pending event

1. Look at the footage at native resolution (zoom) around the times given.
2. Decide. Keep, correct or delete the event; fix interval states the worksheet lists; set the event's
   `adjudication` to `decided` and its `confidence` to your own.
3. In the worksheet fill `decision` (`1`, `2`, `both`, `neither` or `edited`), your id in `adjudicator`, and a short
   `reason` (for example "rigid shell visible at 231.4 s at native resolution").

Material disagreements, which must be decided individually (never averaged):
- an event found by only one reviewer;
- a different hazard or a different kind for the same stretch (violation vs uncertain);
- a boundary difference large enough to change matching (more than 2 s);
- any requirement-basis or zone difference.

Boundary differences of 2 s or less may be decided by averaging: record `both`.

Reviewer notes rows ("reviewer N note") need a decision too: `both` once you have read them.

## Then

The coordinator runs `lock-verified`. It refuses unless both packages pass their completion checks, reviewers 1 and 2
are different named humans, every worksheet row has a decision and an adjudicator who is neither reviewer, and no
event is pending. Only then is `m2-verified-v1` written with status `verified` and locked.
