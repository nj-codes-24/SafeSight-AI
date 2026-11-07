# Representative failures (local only)

`python scripts/validation/render_failures.py` writes one JPEG per false alarm, duplicate and context alert (the
runtime's own evidence frame), and two frames per missed episode (about 1 s after onset and the middle), into one
folder per category, plus a `_montage_<category>.jpg` overview for each.

The JPEGs are git-ignored on purpose. They show identifiable people from third-party footage and stay on this
machine. Do not publish them. The causes assigned after looking at them live in
`reports/validation/error_causes.json`, and the reports that use those causes are `false_alarm_analysis.csv` and
`missed_event_analysis.csv`.

To regenerate: run `scripts/validation/run_evaluation.py score` first, then this script.
