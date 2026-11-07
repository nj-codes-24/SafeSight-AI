# Adjudication and locking (third reviewer)

The adjudicator must not be reviewer A or B, and must not have seen model output for these clips. They resolve
material disagreements; they do not relabel clips from scratch.

1. The coordinator runs `python scripts/validation/human_review.py agreement`. This writes:
   - `agreement/agreement.json`: every measure, with flags;
   - `agreement/disagreement_report.md`: a readable summary;
   - `agreement/adjudication_worksheet.csv`: one row per disagreement.

   Disagreements cover:
   - events found by only one reviewer (violation, uncertain or not applicable);
   - paired events whose boundaries differ by more than 1 s, or whose observability or requirement basis differs;
   - interval-state differences lasting at least 1 s.
2. The coordinator runs `python scripts/validation/human_review.py adjudicate`, which writes `adjudication/labels/`. For each clip, it holds:
   - agreed events, with boundaries averaged;
   - events with attribute differences, marked `"adjudication": "pending"`;
   - single-reviewer events, marked `pending`, with their origin in `from`;
   - reviewer A's intervals.
3. The adjudicator opens the workspace with `python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/adjudication`, then for every pending item:
   - looks at the footage at native resolution;
   - keeps, corrects or deletes the event, and sets `adjudication` to `decided`;
   - fixes interval states the worksheet lists.

   In the worksheet the adjudicator fills `decision` (A, B, both, neither or edited), their id in `adjudicator`, and a short `reason`.
4. Material disagreements are ones that change a score:
   - any event found by only one reviewer;
   - a boundary difference large enough to change matching (more than 2 s);
   - any requirement-basis difference.

   These must be adjudicated. Smaller boundary differences may be decided by averaging; record `both` in the worksheet.
5. The coordinator runs `python scripts/validation/human_review.py lock-verified`. It refuses unless all of these hold:
   - both reviewers marked every clip complete;
   - A and B are different, named humans;
   - every worksheet row has a decision and an adjudicator;
   - the adjudicator is neither A nor B;
   - no event is still pending.

   Only then does it write `reports/validation/annotations/m2-verified-v1/` with status `verified`, list all three people as annotators, and lock it. A verified set is never overwritten; corrections make a new version.
6. Re-score the existing frozen-model run against `m2-verified-v1` (see `README.md`), and report the agreement figures alongside the scores.
