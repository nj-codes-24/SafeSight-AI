# Instructions for reviewer 2 (package SSV-M3-R2-3E205120)

You are one of two independent reviewers. The other reviewer labels the same clips in a different order, from an
empty label set, without seeing your work. A third person resolves disagreements afterwards. Your labels become ground
truth only after that adjudication; until then they are `provisional`.

Allow roughly 2.6–4.3 hours: 15 clips, 26 minutes of video; labelling usually takes 6–10 times real time.
Work alone. Do not discuss clips with the other reviewer until both of you have finished.

## Before you start

1. Read `docs/product_research/17_ANNOTATION_PROTOCOL.md` in full, including §12 (amendments A1–A6). Its SHA-256 is
   `040CDE72166A5D512166B3169D0F09543ECA24763D47898E69EB90E170C5887D` (also in `package.json`). Tell the coordinator if the file you read differs.
2. Pick a reviewer id: initials or a pseudonym. Never use a worker's name. Use the same id for every clip.
3. Open only your own package:
   `python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_2`
4. `clip_manifest.csv` lists your clips in your order, with duration, the hazards to label and the zones drawn.

## Stay blind

Do not open, or ask anyone about, any of these:
- `reports/validation/annotations/` (the AI first pass and its versions)
- every other folder in `reports/validation/` except your own package: `eval_runs/`, `representative_failures/`,
  `m2_1_diagnostics/`, `m2_1_runtime_check/`, `m3_baseline/`, `sensitivity_v1.1/`, `traces/`, `review/`, the other
  reviewer's package
- any `*_analysis.csv`, `baseline_metrics.json`, `error_causes.json`, `validation_summary.md`
- `docs/product_research/18_…`, `19_…` and `21_…`
- the SafeSight dashboard, and any SafeSight runtime output

The tool never shows model output. If you see a box, label or alert from SafeSight anywhere while labelling, stop and
tell the coordinator. The safest setup is a separate copy of the repository that holds only `data/demo/`,
`scripts/validation/annotator.py`, `intelligence/`, `models/runtime_config.json` (zone outlines) and your package.

## For each clip, in your package's order

1. Watch the whole clip once without labelling.
2. Cover the **whole** clip with intervals for head protection (`PPE.HEAD.MISSING`) and, where the manifest lists
   zones, for `ZONE.ENTRY`. States: monitorable, uncertain, unobservable, unusable, not_applicable (protocol §4).
   Unlabelled time counts as unobservable, so leave no gaps by accident. Camera cuts, fades and title cards are
   `unusable`.
3. Record every event (protocol §5–8), each with its **hazard** and, for zone events, the **zone**:
   - a violation, from the first to the last frame it is true and visible;
   - an uncertain stretch (you cannot tell);
   - a not-applicable person (for example a passer-by on a public street).
4. For each event give: the worker (appearance and position only), the observability (judge at native resolution:
   tick "Zoom to native pixels"), the requirement basis for PPE (evident or assumed), the start and end uncertainty in
   seconds, and **your confidence** (high, medium, low). Low confidence is a valid, useful answer.
5. Put the purple marker on the worker and keep "Record the marker as this worker's position" ticked. Where several
   people could be confused, add more anchors as the worker moves.
6. A rigid hard hat is compliant. A soft cap, beanie, hood, balaclava or bare head is not. A hat in the hand is not
   worn. If you cannot tell rigid from soft, label `uncertain`, not violation (§7). Zoom before deciding.
7. The zones in these clips were drawn for a demonstration (`real_restriction: false`). Label geometric entry of the
   feet into the drawn polygon; do not decide whether the entry was allowed.
8. Write judgement calls into the event note, and anything the adjudicator should know about the clip into "Notes for
   the adjudicator". Validate and save. When the clip is fully done, tick "Clip complete" and save again.

## When you finish

Tell the coordinator. They run `python scripts/validation/human_review.py check`; your package's
`completion_check.json` must show `ready: true`. Problems are listed per clip; fix them and save again.
