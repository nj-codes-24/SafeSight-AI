# Third-party notices

SafeSight AI builds on the software, datasets and media below. Each keeps its own licence. This file lists them and states their main obligations; it is a summary, not legal advice. The licences listed for Python packages are taken from each package's installed metadata (versions as pinned in `requirements.txt`).

## Licensing status of this repository

**This project's original source code and documentation are licensed under AGPL-3.0-only ([LICENSE](LICENSE)).** That licence does **not** extend to anything listed in this file: each item keeps its own licence. The component-by-component position is in [LICENSING_DECISION.md](LICENSING_DECISION.md). The main points:

- **Ultralytics (AGPL-3.0)** is a core dependency, and is the source of the base weights and the Construction-PPE dataset. Distributing a combined work, or offering it as a network service, can trigger AGPL-3.0 obligations, including providing the corresponding source under AGPL-3.0. Ultralytics also offers a commercial Enterprise licence.
- **The trained M5 weights** are an adaptation trained on **SH17 (CC BY-NC-SA 4.0)** and Ultralytics base weights (AGPL-3.0). Treat them as **non-commercial**, with attribution and share-alike. They are **not distributed** in this repository.

## Software dependencies (runtime)

| Package | Version | Licence (package metadata) | Notes |
|---|---|---|---|
| Ultralytics | 8.4.197 | **AGPL-3.0** | Detection, training, ByteTrack implementation, YOLO26 base weights |
| PyTorch (`torch`) | 2.14.1 (cu126) | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND further components (see the package) | The CUDA build bundles NVIDIA libraries under NVIDIA's terms |
| torchvision | 0.29.1 (cu126) | BSD | |
| lap | 0.5.13 | BSD-2-Clause | Linear assignment for ByteTrack |
| OpenCV (`opencv-python`) | 5.0.0.93 | Apache-2.0 | |
| NumPy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | |
| SciPy | 1.17.1 | BSD-3-Clause | |
| pandas | 3.1.0 | BSD-3-Clause | |
| Pillow | 13.0.0 | MIT-CMU | |
| Matplotlib | 3.11.2 | Matplotlib licence (PSF-based) | Report and presentation charts |
| PyYAML | 6.0.3 | MIT | |
| psutil | 7.2.2 | BSD-3-Clause | Watchdog |
| Streamlit | 1.66.1 | Apache-2.0 | Includes the Material Symbols icon font (Apache-2.0) |
| watchdog | 6.0.0 | Apache-2.0 | Streamlit file watching |
| Plotly | 7.1.0 | MIT | |
| gdown | 6.5.1 | MIT | Dataset download helper |

**Development:** pytest 9.2.0 (MIT), Ruff 0.15.4 (MIT).

## Model weights used

| Weights | Licence | Use |
|---|---|---|
| `yolo26n.pt` (Ultralytics, COCO-pretrained) | AGPL-3.0 | Starting point for training |
| `yolo26l-pose.pt` (Ultralytics) | AGPL-3.0 | Teacher for person pseudo-labels |

## Datasets

| Dataset | Licence | Attribution / citation |
|---|---|---|
| Construction-PPE | AGPL-3.0 | Ultralytics, Construction-PPE dataset, https://docs.ultralytics.com/datasets/detect/construction-ppe/ |
| PPE dataset v6 | CC BY 4.0 | Mendeley Data, DOI 10.17632/zkzghjvpn2.6 (cite the dataset authors as listed on the DOI page) |
| SH17 | **CC BY-NC-SA 4.0** | H. M. Ahmad and A. Rahimi, *SH17: A dataset for human safety and personal protective equipment detection in manufacturing industry*, Journal of Safety Science and Resilience (2024), DOI 10.1016/j.jnlssr.2024.09.002, https://github.com/ahmadmughees/SH17dataset. Images were scraped from Pexels; the Pexels licence also applies to them. |
| SHWD (experiment M3 only; not in the final model) | MIT (repository); SCUT-HEAD components carry their own terms | Safety Helmet Wearing Dataset, https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset |

No dataset images are included in this repository.

## Video footage

| Clip | Author | Licence | In this repository |
|---|---|---|---|
| [Genève Cornavin travaux voie 4, 2023-23](https://commons.wikimedia.org/wiki/File:Gen%C3%A8ve_Cornavin_travaux_voie_4,_2023-23.webm) | MHM55 | CC BY-SA 4.0 | One gallery thumbnail in `assets/screenshots/01-source-gallery.png` |
| [Jackhammer-japan-july2013](https://commons.wikimedia.org/wiki/File:Jackhammer-japan-july2013.ogv) | Nesnad | CC BY-SA 3.0 | Annotated frames in all screenshots in `assets/screenshots/` |
| [Nowe tory na odcinku Łódź Fabr.–Widzew](https://commons.wikimedia.org/wiki/File:Nowe_tory_na_odcinku_%C5%81%C3%B3d%C5%BA_Fabr.-_Widzew.webm) | Stevenlodz | CC BY-SA 4.0 | One gallery thumbnail in `assets/screenshots/01-source-gallery.png` |
| Mixkit clips 1440 and 1459 | Mixkit | Mixkit Stock Video Free License | **Not included**; fetched by `training/fetch_mixkit.py` |
| Unseen-evaluation clips (Wikimedia Commons) | various | per `data/demo/candidates.json` | Not included |

**Screenshot licence.** The screenshots in `assets/screenshots/` contain adapted frames of CC BY-SA works and are therefore shared under the same CC BY-SA licences, with the attribution above.
