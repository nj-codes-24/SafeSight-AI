# Model card: SafeSight AI M5

## Model details

| | |
|---|---|
| Name | M5 (frozen 2 November 2026) |
| Type | Single-stage object detector |
| Architecture | Ultralytics YOLO26n: 2,534,858 parameters (2,390,221 after layer fusion), 5.4 GFLOPs at 640 px |
| Classes | `0 person`, `1 helmet`, `2 no_helmet` (head boxes; `helmet` means a hard hat is worn) |
| Input | RGB image, letterboxed to 640 px |
| Weights | `models/best.pt`, SHA-256 `E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534`; record in `models/model_config.yaml` |
| Lineage | COCO YOLO26n, then M2 (120-epoch budget), then M4 (fine-tune, 40-epoch budget, stopped at epoch 29), then M5 (fine-tune, 40-epoch budget, stopped at epoch 19) |
| Framework | Ultralytics 8.4.197, PyTorch 2.14.1 |
| Companion components | ByteTrack (person boxes only) and a multi-frame helmet-state vote in `inference/` |

## Intended use

**For:**
- **Research and education:** detecting whether visible workers wear hard hats in recorded or live video, as a decision aid for a human safety supervisor.
- **Demonstrating a full pipeline,** from detection through tracking, temporal confirmation and incident records with evidence.

**Out of scope:**
- **Sole basis for safety enforcement,** discipline or any decision about an individual.
- **Identifying people.** The model detects heads and helmets; it does not recognise anyone.
- **Other PPE** such as vests, gloves or harnesses. These were not trained.
- **Commercial use** while the SH17 non-commercial licence applies (see below).
- **Settings far from the training data:** very distant or low-resolution workers, aerial views, thermal cameras.

## Training data

| Source | Role | Licence |
|---|---|---|
| Construction-PPE (Ultralytics) | Worksite helmets; boxes harmonised to full heads for M4/M5 | AGPL-3.0 |
| Mendeley PPE dataset v6 | Bare and helmeted heads | CC BY 4.0 |
| SH17, audited 1,819-image subset | Varied, fully labelled heads; `no_helmet` labels derived (see below) | CC BY-NC-SA 4.0 |
| Pose-teacher pseudo-labels (`yolo26l-pose.pt`) | Person boxes where datasets left people unlabelled | Generated with AGPL-3.0 weights |

**Derived labels.** SH17 has no `no_helmet` class, so labels were derived from head/helmet overlap:
- A head holding at least 40% of a helmet box becomes `helmet`.
- Any other head becomes `no_helmet`.
- Ambiguous images (5–40% overlap, or a loose helmet beside a bare head) were rejected.
- Visual audits removed further errors. About 1 in 66 derived `no_helmet` labels in a random sample remains wrong.

Details: [datasets_and_licensing.md](datasets_and_licensing.md).

## Evaluation

| Data | Metric | M5 |
|---|---|---|
| SH17 val (1,618 images, complete labels) | no_helmet AP50 | **0.827** |
| SH17 val | no_helmet P / R at best-F1 confidence | 0.944 / 0.704 |
| SH17 val | no_helmet P / R at the application threshold 0.60 | 0.981 / 0.615 |
| SH17 val | person AP50 · all-class mAP50 / mAP50-95 | 0.859 · 0.770 / 0.526 |
| Common val (308 images, partial labels) | mAP50 / mAP50-95 | 0.656 / 0.449 (M2: 0.703 / 0.489) |
| Construction-PPE official test (141) | mAP50 | 0.427 (M2: 0.583) |
| Mendeley test (360) | mAP50 | 0.671 (M2: 0.667) |
| Demo clips, full pipeline, threshold 0.60 | true / false no-helmet incidents | 4 of 4 / 0 |
| 10 unseen Commons clips, full pipeline, 0.60 | true / false alerts on worksite clips | 2 / 0; distant workers on 2 clips all missed |

**Methodology:**
- **Selection** used validation data and worksite footage only.
- **The test sets were run once,** after selection.
- **The unseen footage** was labelled by eye before any run, and no threshold was tuned on it.

Full analysis: [evaluation.md](evaluation.md).

## Operating point

**no_helmet confidence 0.60** (helmet 0.30, person 0.35). A worker's state is decided only after head evidence agrees over about 0.5 s (at least 70% of votes); otherwise the worker stays UNCERTAIN.

**A site should re-tune these values on its own footage.**

## Limitations, bias and robustness

- **Domain.** Trained largely on public photographs and short clips. **Not validated on any real site's cameras.**
- **Scale.** Small, distant or low-resolution heads are missed: on one distant rooftop clip, 0 of 5–7 bare heads were found.
- **Context.** Any bare head is flagged; the model has no notion of whether a scene is a worksite.
- **Label conventions.** Shell boxes and full-head boxes conflict across datasets. Scores on Construction-PPE-style labels are depressed.
- **Headwear.** Caps, hoods and scarves count as "no hard hat" by design. Unusual helmets, such as white shells seen from behind or face shields, can be confused.
- **Fairness.** No evaluation by skin tone, hair type or religious headwear. Errors may not be evenly distributed.
- **Lighting.** Night footage was tested on one clip only.

## Deployment considerations

- **Hardware.** Runs at about 10 ms per frame on an RTX 2000 Ada. A CPU is possible but much slower.
- **Privacy.** Evidence frames show identifiable people, so deployment needs consent, a privacy notice and a retention policy.
- **Human oversight.** Use it as a decision aid with human review of incidents. Statuses exist for that: Reviewed, False alarm.

See [deployment.md](deployment.md).

## Licence considerations

- **The weights are an adaptation trained on SH17 (CC BY-NC-SA 4.0),** so treat them as **non-commercial**. Any redistribution must keep attribution and share-alike terms.
- **The weights also derive from Ultralytics YOLO26n base weights and code (AGPL-3.0).**
- **The weights are not distributed in any form.** The two sets of terms may conflict, so distribution waits on written clarification ([LICENSING_DECISION.md](../LICENSING_DECISION.md)).

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
