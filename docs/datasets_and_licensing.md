# Datasets and licensing

**No dataset, image or video is redistributed in this repository.** This page documents where every input came from, how it was used and what its licence requires. The original working record is [`records/DATASETS.md`](records/DATASETS.md).

## Training and evaluation datasets

| Dataset | Source | Purpose | Images used | Splits | Annotation | Licence | Attribution | Known limitations |
|---|---|---|---|---|---|---|---|---|
| **Construction-PPE** | Ultralytics ([docs](https://docs.ultralytics.com/datasets/detect/construction-ppe/)) | Worksite helmets and people; baseline source | 1,416 downloaded; after leakage cleaning: train 670, val 96, official test 141 (verbatim) | Train · val · test | Boxes: person, helmet, no_helmet (the `none` class was unused) | **AGPL-3.0** | Ultralytics | Helmet-only "shell" boxes; incomplete person labels; no_helmet mostly non-industrial heads; official splits leaked near-duplicates |
| **PPE dataset v6** | Mendeley Data, DOI [10.17632/zkzghjvpn2.6](https://data.mendeley.com/datasets/zkzghjvpn2/6) | Bare and helmeted heads | 2,286 downloaded: train 1,711, val 212, test 360 | Train · val · test | Head boxes (helmet / no_helmet); vest classes unused | **CC BY 4.0** | Dataset authors, Mendeley Data | No person class; only some heads labelled per image |
| **SH17** | Ahmad et al., [github.com/ahmadmughees/SH17dataset](https://github.com/ahmadmughees/SH17dataset) (images from Pexels) | Varied, fully labelled people and heads | 8,099 downloaded (about 14 GB): an audited **1,819-image** training subset, and the official val (1,618 images) as a check | Train subset · separate val | 17 classes, including person, head and helmet; **no `no_helmet` class** | **CC BY-NC-SA 4.0** | Ahmad et al., SH17 | Few helmets in val (152); derived labels contain a small error rate |
| SHWD | Safety Helmet Wearing Dataset (GitHub) | Experiment M3 only | 3,219 helmet images + 500 head-only images | Train only | Helmet / head boxes | MIT repository; SCUT-HEAD parts have their own terms | Dataset authors | Bare heads skew to classrooms; repeated frames. **Not in the final model.** |

**Generated labels:**
- **Person pseudo-labels:** 6,670 person boxes were added by the Ultralytics `yolo26l-pose.pt` teacher (AGPL-3.0) where datasets left people unlabelled. A visual audit found about 94 of 96 sampled boxes were real people.
- **Masked heads:** 3,575 unlabelled heads were masked on 1,201 images, so the model is not trained to ignore them.

## SH17 `no_helmet` labels are derived, not original

SH17 labels heads and helmets but has no "bare head" class. The `no_helmet` labels used for M5 were derived in `training/add_sh17.py`:

1. **Helmeted heads:** a head box that holds at least **40%** of a helmet box becomes `helmet`, using the full-head box.
2. **Bare heads:** any other head becomes `no_helmet`. Caps, hats and scarves count as "no hard hat", which is the intended meaning.
3. **Ambiguous images are rejected,** not guessed. These are images with a head/helmet overlap of 5–40%, or a loose helmet beside a bare head: 13 training images.
4. **Visual audit** (`training/audit_sh17_labels.py`, `training/reject_sh17.py`):
   - About **1 in 66** random `no_helmet` labels was wrong.
   - Of 125 cases where the earlier model saw a helmet, most were caps or scarves. 12 crops were real helmets or face shields, and those 10 images were removed by hand.
5. **Balancing:** the training subset was capped at 1,819 images.

## Leakage prevention and near-duplicates

- **Construction-PPE:** 989 near-duplicate train-to-test pairs (ResNet18, cosine above 0.93). 449 train and 47 val images linked to test were removed, plus 13 train images linked to val. The test set is untouched.
- **Mendeley:** split 75/10/15 by near-duplicate cluster (seed 42), so duplicates cannot cross splits.
- **SH17:** checked at cosine 0.90 against **every** existing train, val and test image and SH17 val. 200 train and 2 val images were removed.
- **Tests enforce the separation:** `tests/test_pipeline.py` checks that SHWD never reaches val or test and that the official test set keeps 141 images.

## Demo and evaluation footage

| Clip | Source | Author | Licence | Redistributed here? |
|---|---|---|---|---|
| track_work_day | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Gen%C3%A8ve_Cornavin_travaux_voie_4,_2023-23.webm) | MHM55 | CC BY-SA 4.0 | Video: no (fetched). A gallery thumbnail appears in one screenshot. |
| roadworks_night | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Jackhammer-japan-july2013.ogv) | Nesnad | CC BY-SA 3.0 | Video: no (fetched). Annotated frames appear in the screenshots under CC BY-SA 3.0. |
| ballast_train | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Nowe_tory_na_odcinku_%C5%81%C3%B3d%C5%BA_Fabr.-_Widzew.webm) | Stevenlodz | CC BY-SA 4.0 | Video: no. A gallery thumbnail appears in one screenshot. |
| helmet_put_on | Mixkit clip 1440 | Mixkit | Mixkit Stock Video Free License | **No.** Standalone redistribution is unconfirmed; fetch with `training/fetch_mixkit.py`. |
| framing_bare_head | Mixkit clip 1459 | Mixkit | Mixkit Stock Video Free License | **No**, same reason |
| Unseen set (10 clips) | Wikimedia Commons; licences in `data/demo/candidates.json` | various | CC licences per clip | No |

Three further Mixkit clips were dropped because their pages state a restricted personal-use licence. **No one in the footage is identified;** worker IDs are temporary track numbers.

## What the licences mean for this project

| Artifact | Constraint |
|---|---|
| **M5 weights** | Potentially an adaptation of SH17 (**non-commercial, attribution, share-alike**), and, per Ultralytics, AGPL-3.0 by default. The two may conflict, so the weights are **not distributed**, nor is any other checkpoint. |
| **Source code in this repository** | **AGPL-3.0-only** ([LICENSE](../LICENSE)), consistent with Ultralytics. It covers this project's own work only. |
| **Screenshots** | Contain CC BY-SA frames, so they are shared under the same licences with attribution ([assets/screenshots/README.md](../assets/screenshots/README.md)) |
| **Reports** | Numbers, charts and JSON summaries; no dataset images are included |

**Whether M5 can be distributed at all** is analysed in [LICENSING_DECISION.md](../LICENSING_DECISION.md): SH17's ShareAlike non-commercial terms may conflict with AGPL-3.0, and the open questions for Ultralytics and the SH17 authors are listed there.

**Commercial use of the trained model is not permitted** under SH17's terms. Commercial use of the code or a retrained model would need a licensing review of AGPL-3.0 (Ultralytics) and of every dataset used.

**Required attribution and citations:** [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
