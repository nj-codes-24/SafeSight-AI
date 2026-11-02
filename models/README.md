# Model weights

This folder holds the model **configuration**. The weights themselves are **not** in the repository.

| File | Tracked | Purpose |
|---|---|---|
| `model_config.yaml` | yes | Frozen record of the selected model: source run, checksum, classes, thresholds, licence note, fallback |
| `runtime_config.json` | yes | The app's editable settings (zones; thresholds when changed). Written by the settings menu. |
| `best.pt` | **no** | M5 weights used by the app and the tests |
| `candidates/*.pt` | no | Preserved alternatives (M2 fallback, M3, a copy of M5) |
| `pretrained/*.pt` | no | Ultralytics base weights (YOLO26n, YOLO26l-pose teacher) |

## Why the weights are not published

M5 was fine-tuned on a subset of **SH17** (CC BY-NC-SA 4.0), so the weights are an adaptation of non-commercial, share-alike data. It was trained with **Ultralytics** (AGPL-3.0), starting from Ultralytics base weights. SH17's ShareAlike non-commercial terms and AGPL-3.0's "no further restrictions" rule may be impossible to satisfy together, and we do not assume the weights escape either. So **M5 is not distributed in any form**: there is no download link, and no checkpoint (M5, M2, M3, M4, B0) is attached to any release. The project's AGPL-3.0 licence covers the code, not these weights. The open questions are in [LICENSING_DECISION.md](../LICENSING_DECISION.md).

## Using the weights if you already hold them

If you lawfully hold the M5 file (for example on the original development machine):

1. Save the file as `models\best.pt`.
2. Verify the checksum:

   ```powershell
   (Get-FileHash models\best.pt -Algorithm SHA256).Hash
   # expected: E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534
   ```

3. Run `python scripts\verify_installation.py`. It checks the same hash against `model_config.yaml`.

| Property | Value |
|---|---|
| File | `models/best.pt` (about 24.9 MB) |
| Model | M5, YOLO26n, 3 classes: `person`, `helmet`, `no_helmet` |
| Parameters | 2,534,858 (2,390,221 fused) |
| Input size | 640 px |
| SHA-256 | `E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534` |
| Application thresholds | person 0.35, helmet 0.30, no_helmet 0.60 |

## Training your own weights

Without the M5 file you can reproduce a model with the training pipeline. See [docs/training.md](../docs/training.md). A model you train yourself will not match M5's checksum, and its results will differ.
