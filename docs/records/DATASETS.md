# Datasets and footage: sources, licences, use

## Training and evaluation datasets

| Dataset | Licence | Images downloaded | Used for | Result |
|---|---|---|---|---|
| Construction-PPE (Ultralytics) | AGPL-3.0 | 1,416 | Train, val, official test | Used. Baseline source. |
| PPE dataset v6, Mendeley Data, DOI 10.17632/zkzghjvpn2.6 | CC BY 4.0 | 2,286 | Train, val, separate test | Used. Decisive for bare-head detection. |
| SHWD (Safety Helmet Wearing Dataset) | MIT repository; its SCUT-HEAD parts carry their own terms | 7,581 | Train only, experiment M3 | Tried and rejected. Not in the final model. |
| SH17 (Ahmad et al., [github.com/ahmadmughees/SH17dataset](https://github.com/ahmadmughees/SH17dataset), images from Pexels) | CC BY-NC-SA 4.0 | 8,099 | 1,819-image audited train subset; official val as a fully labelled check | Used in the final model (M5). Makes the model non-commercial. |

Pose-teacher: Ultralytics `yolo26l-pose.pt` (AGPL-3.0) generated person pseudo-labels and head locations.

The final model is derived from AGPL-3.0 code, weights and data. Check AGPL obligations before any distribution.

## Data problems found

- **Construction-PPE official splits leak.** 989 train-to-test near-duplicate pairs (ResNet18 cosine above 0.93), frames of the same videos. I dropped 449 train and 47 val images linked to test, and 13 train images linked to val. Test stays verbatim at 141 images.
- **Construction-PPE labels.** Person labels are incomplete. `no_helmet` is mostly non-industrial heads: portraits, children, sport, head-wraps. The `none` class was junk and is unused.
- **Mendeley has no person class** and labels only some heads per image. Vest classes are unused because Construction-PPE has no `no_vest`.
- **SHWD** labels look clean, but its bare heads skew to classrooms and children, with repeated frames.

## Final splits

| Set | Construction-PPE | Mendeley | Total |
|---|---|---|---|
| Train | 670 | 1,711 | 2,381 |
| Val | 96 | 212 | 308 |
| Test | 141 | 360 | 501 |

Mendeley was split 75/10/15 by near-duplicate cluster (seed 42), so duplicates cannot cross splits.

Test instances:

| Slice | person | helmet | no_helmet |
|---|---|---|---|
| Construction-PPE | 236 | 192 | 40 |
| Mendeley (human labels only) | none labelled | 383 | 185 |

Training set adjustments in `merged_clean`: 6,670 pseudo-person boxes added and 3,575 unlabelled heads masked on 1,201 images. A visual audit of a sample found about 94 of 96 pseudo-persons were real people, and nearly all masks were real heads.

The M3 set (`merged_shwd`) had 6,013 train images with instances person 17,911, helmet 11,433 and no_helmet 5,737, using all 3,219 SHWD helmet images plus 500 sampled heads-only images.

## Contribution to performance

Common validation set (308 images, partial labels) and SH17 val (1,618 images, complete labels).

| Experiment | Data change | Common val no_helmet AP50 | Common val person AP50 | SH17 val no_helmet AP50 | Verdict |
|---|---|---|---|---|---|
| B0 | Construction-PPE only | 0.133 | 0.811 | 0.166 | Baseline. Misses worksite bare heads. |
| M1 | + Mendeley, plain union | 0.611 | 0.235 | not scored | Partial labels taught it to ignore people. |
| M2 | + pose-teacher persons and masks | 0.579 | 0.939 | 0.513 | Previous model; now the fallback. |
| M3 | + SHWD | 0.545 | 0.953 | 0.723 | Rejected on day 1 for extra false positives. SH17 later showed many were unlabelled real heads; not revisited. |
| M4 | M2 fine-tuned, Construction-PPE boxes extended to full heads | 0.551 | 0.931 | 0.439 | The box fix alone did not help. |
| M5 | M4 fine-tuned + audited SH17 subset | 0.545 | 0.942 | **0.827** | **Selected.** |

- **Pseudo-labels:** these took person recall at confidence 0.3 from 0.146 to 0.896.
- **SH17's contribution:** M5 against M4 isolates SH17. It raised SH17 val no_helmet AP50 by 0.39 and person AP50 by 0.08, and left Mendeley unchanged (0.744 against 0.739).

## SH17 use and label derivation

SH17 is CC BY-NC-SA 4.0: attribution required, non-commercial use only, and adaptations must share alike. Any model trained on it must be treated as non-commercial.

SH17 has no `no_helmet` class, so labels were derived in `training/add_sh17.py`:

- A head holding at least 40% of a helmet box becomes `helmet`, using the full-head box.
- Any other head becomes `no_helmet`. Caps, hats and scarves count as no hard hat, which is the intended meaning.
- Images with an overlap of 5 to 40%, or a loose helmet beside a bare head, are rejected rather than guessed: 13 train images.
- Near-duplicates at cosine 0.90 against every existing train, val and test image and SH17 val were removed: 200 train, 2 val.
- A visual audit (`reports/diagnostics/sh17_audit/`) found about 1 in 66 random `no_helmet` labels wrong. In 125 cases where M2 saw a helmet, most were caps or scarves and 12 crops were real helmets or face shields. Those 10 images were removed by hand.

SH17 val used here: 1,618 images, instances person 2,721, helmet 152, no_helmet 2,291. It has few helmets, so its helmet figures are less reliable, and it also includes a small remaining share of wrong `no_helmet` labels.

## Demo footage

| Clip | Source | Author | Licence | Distribution |
|---|---|---|---|---|
| track_work_day | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Gen%C3%A8ve_Cornavin_travaux_voie_4,_2023-23.webm) | MHM55 | CC BY-SA 4.0 | Allowed with attribution; derivatives share alike |
| roadworks_night | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Jackhammer-japan-july2013.ogv) | Nesnad | CC BY-SA 3.0 | Allowed with attribution; derivatives share alike |
| ballast_train | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Nowe_tory_na_odcinku_%C5%81%C3%B3d%C5%BA_Fabr.-_Widzew.webm) | Stevenlodz | CC BY-SA 4.0 | Allowed with attribution; derivatives share alike |
| helmet_put_on | Mixkit clip 1440 | Mixkit | Mixkit Stock Video Free License | Standalone redistribution unconfirmed. Fetch with `training/fetch_mixkit.py`; do not ship. |
| framing_bare_head | Mixkit clip 1459 | Mixkit | Mixkit Stock Video Free License | Same as above |

All clips show people at work, are used for technical demonstration only, and no identification of anyone is performed. Annotated outputs of the Commons clips are derivatives under the same CC BY-SA terms.

Three other Mixkit clips (23407, 23170, 49024) were removed because their pages state a Restricted personal-use licence.
