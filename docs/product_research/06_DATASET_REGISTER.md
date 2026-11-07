# 06 — Dataset register

Research date: 5 November 2026. **Nothing was downloaded for this research.** Licence statements come from the dataset's own page where found; where only third-party mirrors state a licence, the entry says **unverified** and must be checked against the original before any use. "Commercial" means: may a model trained on it be used in a commercial product? That question is not settled law for model weights; the column states the conservative reading.

## 1. Rules for using any dataset in SafeSight

1. **Licence first.** No dataset enters a training set until its licence, any image-source terms (Flickr, Pexels, web-scraped) and any request-form conditions are recorded here.
2. **Two model lines.** *Research models* may use non-commercial data (as M5 does with SH17) and are never distributed or deployed commercially. *Product models* use only data whose terms allow commercial use, plus customer-owned site data under contract.
3. **Leakage control** as already practised in this repo: near-duplicate clustering across splits (embedding cosine), no frames from the same video across train and test, and site-level splits for site data.
4. **Site data is the most valuable data.** Public datasets get a model to "plausible"; only labelled footage from the customer's cameras gets it to "validated".

## 2. Datasets already used by SafeSight

| Dataset | Size / labels | Licence | Commercial | Relevance |
|---|---|---|---|---|
| **Construction-PPE** (Ultralytics) [D02] | Construction images; helmet-only (shell) boxes; official splits contained near-duplicates (989 train–test pairs found by this project) | AGPL-3.0 | Usable under AGPL terms; whether trained models inherit AGPL is an open question to Ultralytics (U3 in `LICENSING_DECISION.md`) | Core PPE; box-style mismatch with full-head data |
| **PPE dataset v6** (Mendeley Data, DOI 10.17632/zkzghjvpn2.6) [D03] | Helmet / no-helmet heads, partial labels, no person class | CC BY 4.0 | **Yes**, with attribution | Core PPE; partial labels need masking |
| **SH17** (Ahmad & Rahimi 2024) [D01] | 8,099 images, 17 classes incl. person, head, helmet, gloves, glasses, safety vest, face mask/guard, ear mufs, shoes, tools (manufacturing focus) | **CC BY-NC-SA 4.0**; images from Pexels (Pexels terms also apply) | **No** | Fully labelled bare-head check; research-only line |
| **SHWD** (experiment M3 only) [D10] | Helmet / head | MIT repository; SCUT-HEAD parts have own terms | Partly unclear | Not in M5 |

## 3. Candidate datasets by capability

### 3.1 PPE and construction scenes

| Dataset | Source | Size and labels | Environment | Licence | Commercial | Relevance |
|---|---|---|---|---|---|---|
| **SODA** [D04] | Duan et al., Automation in Construction 2022 (arXiv 2202.09554) | 19,846 images, 15 classes (workers, materials, machines, layout), VOC format | Construction | **Not found**; described as freely accessible to researchers | Unknown, assume no | Workers, helmets, vests, machines; strong candidate for research line |
| **MOCS** [D05] | An et al., Automation in Construction 2021 | 41,668 images from 174 sites, 13 classes (workers, tower cranes, excavators, …) | Construction | **CC BY-NC 4.0** plus request-form terms: non-commercial research only, no sharing, no derived datasets without written consent | **No** | Construction machines; research only |
| **ACID** [D06] | Xiao & Kang, J. Computing in Civil Engineering 2021 | Construction machine images, 10 machine classes | Construction | Not verified | Unknown | Excavators, loaders, cranes |
| **Pictor-PPE** [D07] | Nath, Behzadan, Paal 2020 | Hat, Vest, Worker | Construction | Not verified | Unknown | Hi-vis vests |
| **CHV** [D08] | Color Helmet and Vest dataset | Helmets by colour, vests, persons | Construction | Not verified at source (third-party re-uploads list CC BY 4.0) | Unknown | Hi-vis vests |
| **SHEL5K** [D09] | Extension of Safety Helmet Detection | 5,000 images, 75,570 instances, 6 classes | Construction | Not verified | Unknown | Helmets |
| **ConstructionSite 10k** [D15] | Chen & Zou 2025 | 10,013 images; captions (~2,000 manual), rule-violation VQA, grounding | Construction | Gated on Hugging Face; licence per paper (not verified here) | Unknown | VLM evaluation, not detector training |

### 3.2 Logistics, vehicles and equipment

| Dataset | Source | Size and labels | Licence | Commercial | Relevance |
|---|---|---|---|---|---|
| **LOCO — Logistics Objects in Context** [D11] | Mayershofer et al., TUM, ICMLA 2020; github.com/tum-fml/loco | 39,101 images, 5,593 annotated; classes: small load carrier, pallet, stillage, **forklift**, **pallet truck**; vehicles are a small share of labels | Repository states copying, modification and distribution **including commercial use** are permitted (check the LICENSE file for exact terms) | **Likely yes** | **Highest-value public set for the logistics wedge**; forklift class is under-represented and needs site data |
| **COCO** [D18] | cocodataset.org | 118k train images; person, car, truck, … | Annotations CC BY 4.0; images under their Flickr terms | Commonly used commercially for pre-training; image terms vary | Pre-training only |
| **Open Images V7** [D19] | Google | ~9 M images; boxes for 600 classes incl. person, forklift-like vehicles | Annotations CC BY 4.0; images CC BY 2.0 (per-image attribution) | **Yes**, with attribution | Extra person/vehicle data, hard negatives |
| **Objects365** [D20] | Shao et al. 2019 | 2 M images, 365 classes | Aggregators list a custom research-only licence (unverified) | Assume no | Pre-training only for research line |

### 3.3 People, crowds and tracking

| Dataset | Licence | Commercial | Relevance |
|---|---|---|---|
| **CrowdHuman** [D21] | Non-commercial research (per dataset terms; verify) | No | Occluded persons; research line |
| **MOT17 / MOT20** [D22] | CC BY-NC-SA 3.0 (per MOTChallenge; verify) | No | Tracker benchmarking only |
| **SCUT-HEAD** [D24] | Research terms | No/unclear | Heads in classrooms |

### 3.4 Falls, person-down and actions

| Dataset | Source | Notes | Licence | Relevance |
|---|---|---|---|---|
| **OmniFall** [D13] | arXiv 2505.19889 (2025) | Unifies eight staged fall datasets (~14 h; v2 expands to ~80 h, 16 classes) plus genuine accident videos (OOPS-Fall / in-the-wild) | Mixed: each component keeps its own licence | Evaluation of staged-to-wild gap; not a commercial training source |
| **UR Fall Detection** [D23] | Kwolek & Kepski 2014 | Staged falls, Kinect + accelerometer | Not verified | Historical baseline |
| **InHARD** [D14] | Dallel et al. 2020, Zenodo 4003541 | 13 industrial assembly actions, 4,800+ samples, skeleton + RGB | Not verified at source | Industrial action recognition (assembly, not hazards) |

### 3.5 Fire, smoke and spills

| Dataset | Source | Notes | Licence | Commercial |
|---|---|---|---|---|
| **D-Fire** [D12] | de Venâncio, Lisboa, Barbosa 2022; github.com/gaiasd/DFireDataset | 21,527 images; 14,692 fire and 11,865 smoke boxes; 9,838 hard-negative images | Conflicting: mirrors and a survey say CC0, the repository metadata says "other", a survey also mentions GNU GPL | **Unverified**; resolve before use |
| **SynSpill** [D16] | ICCV-W 2025 | 2,000 synthetic spill images; proprietary factory set not released | Not verified | Unknown |
| **Infinity AI Spills Basic** [D17] | Synthetic, 150 videos, 15 settings, pixel labels | Not verified | Unknown |

### 3.6 Ergonomics and pose

| Dataset | Notes | Licence | Relevance |
|---|---|---|---|
| **COCO-Keypoints** | Human pose | As COCO | Pose model pre-training |
| **Site footage with ergonomist labels** | Does not exist publicly in a usable form | — | Required for any ergonomic claim |

## 4. Gaps that block capabilities

| Capability | Gap | How to close it |
|---|---|---|
| Hi-vis (P1) | Public vest datasets have unverified licences | Label site footage + Open Images persons; verify CHV/Pictor licences with authors |
| Forklift–pedestrian (P1) | LOCO has few forklift labels; no public near-miss ground truth with timestamps | Partner-site footage; label episodes (start/end, closest approach) for event-level evaluation |
| Person under suspended load (P2) | No public dataset of loads with ground-plane footprints | Site data + crane telemetry |
| Person-down (P2) | Staged data does not transfer (OmniFall) | Site staging with consent + rare real events; human confirmation required |
| Spills (P3) | No credible public benchmark | Synthetic data + thermal; research project |
| Event-level evaluation (all) | No public industrial dataset labels *episodes* with timestamps | Create SafeSight's own episode ground truth (format in `09` and `intelligence/event_metrics.py`) |

## 5. Synthetic data

Synthetic rendering (game engines, NVIDIA Omniverse/Isaac Sim, procedural spills as in SynSpill) is a legitimate way to cover rare, dangerous scenarios (person under a load, falls) that cannot be staged. **Rule:** synthetic data may be used for training, never as the sole evidence of performance; validation must be on real footage. Tool licences (for example Omniverse) must be checked for the commercial line.

## 6. Storage and bandwidth note

Current local data already occupies about 35 GB (`REPOSITORY_AUDIT.md` §1). Downloading SODA (~20k images), LOCO (~39k images) or D-Fire (~21k images) is feasible in size, but **none should be downloaded until** its licence row above is resolved and a specific experiment needs it.
