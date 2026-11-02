# Presentation assets

Everything here is drawn from saved results. No model was run to make it.

| File | Shows | No-helmet threshold |
|---|---|---|
| `figures/thresholds_sh17.png` | SH17-val precision-recall for M2, M3 and M5, with M5's comparison (0.50) and application (0.60) thresholds marked | Both, labelled |
| `figures/benchmark_vs_site.png` | SH17 no_helmet AP50 beside alerts on unseen worksite clips | AP: none. Alerts: M2 0.65, M3 0.50, M5 0.50 and 0.60 |
| `figures/tracking_unseen.png` | Track IDs and IDs lasting under 1 s on ten unseen clips | As above; tracking uses persons only |
| `figures/false_no_helmet_c02.png` | False no_helmet detections per 100 frames on the helmeted clip c02 | As above |
| `figures/*_evidence.jpg` | Incident screenshots from the unseen comparison, by configuration | `m5_at_0.6` = application threshold |
| `deck_source/` | Source of the 14-slide deck | Every slide names its threshold |

Rebuild the charts with `.venv\Scripts\python.exe presentation\make_figures.py`.

The evidence sheets show identifiable people from public clips. They are kept out of the online deck and should be shown only locally.

The deck itself is a private claude.ai artifact: https://claude.ai/artifact/J3YT676k1uSt8xmrT35giu. It can be exported to PowerPoint or PDF from its Share menu, which is the copy to use offline.
