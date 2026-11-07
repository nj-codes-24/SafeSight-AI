# Instructions for reviewers A and B

Allow roughly 3–4.5 hours. There are 15 clips and 26 minutes of video; labelling usually takes 6–10 times real time.
Work alone. Do not discuss clips with the other reviewer until both of you have finished.

## Before you start

1. Read `docs/product_research/17_ANNOTATION_PROTOCOL.md` in full, including §12 (amendments). Its SHA-256 is recorded in your `package.json`. Tell the coordinator if the file you read differs.
2. Pick a reviewer id: initials or a pseudonym. Never use a worker's name.
3. Open only your own package:
   `python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_A` (or `reviewer_B`).

## Stay blind

Do not open, or ask anyone about, any of these:
- `reports/validation/annotations/` (the AI first pass and its versions)
- `reports/validation/eval_runs/`, `representative_failures/`, `m2_1_diagnostics/`, `sensitivity_v1.1/`, `traces/`, `review/`
- any `*_analysis.csv`, `baseline_metrics.json`, `error_causes.json`
- `docs/product_research/18_…` and `19_…`
- the SafeSight dashboard

The tool never shows model output. If you see a box, label or alert from SafeSight anywhere while labelling, stop and
tell the coordinator. The safest setup is a separate copy of the repository that holds only `data/demo/`,
`scripts/validation/annotator.py`, `intelligence/`, `models/runtime_config.json` (zone outlines) and your package.

## For each clip, in your package's order

1. Watch the whole clip once without labelling.
2. Cover the whole clip with intervals for head protection (`PPE.HEAD.MISSING`) and, on the two clips whose zones are drawn, for `ZONE.ENTRY`. Use the five states: monitorable, uncertain, unobservable, unusable, not_applicable (protocol §4). Unlabelled time counts as unobservable, so leave no gaps by accident.
3. Record every event (protocol §5–8):
   - a violation, from the first to the last frame it is true and visible;
   - an uncertain stretch;
   - a not-applicable person (for example a passer-by).

   For each event give the worker (appearance and position only), the observability (judge it at native resolution: tick "Zoom to native pixels"), the requirement basis for PPE (evident or assumed), and the start and end uncertainty in seconds.
4. Put the purple marker on the worker and keep "Record the marker as this worker's position" ticked. That anchor tells the scorer which worker you meant. Where several people could be confused, add more anchors as the worker moves ("Add the marker as another anchor to the last event").
5. A rigid hard hat is compliant. A soft cap, beanie, hood, balaclava or bare head is not. A hat in the hand is not worn. If you cannot tell rigid from soft, label `uncertain`, not violation (§7). Dark hard hats and soft caps can look alike at a distance: zoom before deciding.
6. Validate and save. When the clip is fully done, tick "Clip complete" and save again.

## Record disagreements with yourself

If a decision is a judgement call, say so in the event's note (for example "rigid or soft unclear at 30 px"). These
notes go to the adjudicator. You cannot set a file's status: verification happens only after adjudication.

## When you finish

Tell the coordinator. They run `human_review.py status` to check that every clip shows `done`, and `agreement` once both
reviewers are finished.
