# 05 — Research papers and technology

Research date: 5 November 2026. Paper IDs (P01…) resolve in `14_SOURCE_REGISTER.md`. "Reported" numbers are the authors' figures on their benchmark, not reproductions. **Feasibility** refers to the development GPU (RTX 2000 Ada, 16 GB) and a realistic edge box (NVIDIA Jetson Orin class). **Licence** is the code/weights licence as published; re-check the repository LICENSE file before any use.

## 1. Guiding principle

Prefer the simplest method that can be validated. For SafeSight's priority hazards, **geometry + tracking + time** (ground-plane homography, zone logic, Kalman velocities, dwell times) is more reliable, explainable and testable than end-to-end video models. Learned temporal models are justified only where geometry cannot express the event (falls, person-down, reach-ins). Vision-language models are useful for labelling, search and review, not for real-time alerting.

## 2. Object detection

| ID | Paper | Venue / year | Core idea | Reported | Code / licence | Feasibility and fit |
|---|---|---|---|---|---|---|
| P06 | Zhao et al., *DETRs Beat YOLOs on Real-time Object Detection* (RT-DETR) | CVPR 2024 | Hybrid encoder and IoU-aware query selection make a DETR real-time and NMS-free | R50: 53.1 AP COCO at 108 FPS (T4) | Yes; Apache-2.0 | Runs on our GPU and on Orin with TensorRT. **Key value: an Apache-2.0 path away from Ultralytics AGPL** |
| P07 | Peng et al., *D-FINE: Redefine Regression Task in DETRs as Fine-grained Distribution Refinement* | ICLR 2025 | Box regression as iterative distribution refinement; self-distillation | L: 54.0 AP, X: 55.8 AP COCO (higher with Objects365 pre-training) | Yes; Apache-2.0 | Same as RT-DETR; strong small-object behaviour helps distant workers |
| P08 | Robinson et al., *RF-DETR: Neural Architecture Search for Real-Time Detection Transformers* | ICLR 2026 | DINOv2 backbone + weight-sharing NAS for accuracy/latency trade-offs; tuned for fine-tuning on new domains | 2XL: 60.1 AP COCO; nano: 48.0 AP; evaluated on the 100-dataset RF100-VL | Yes; Apache-2.0 per Roboflow (check per-size terms) | Designed for exactly our use: fine-tuning a specialist detector on small domain data |
| — | Ultralytics YOLO26n (current) | 2025–2026 | Small NMS-free YOLO | M5: 2.5 M params, 5.4 GFLOPs, ~10 ms/frame here | AGPL-3.0 or Enterprise | Proven in this repo; licensing is the constraint, not performance |

**Open-vocabulary detection (for labelling and discovery, not alerting):**

| ID | Paper | Venue / year | Use for SafeSight | Licence |
|---|---|---|---|---|
| P09 | Cheng et al., *YOLO-World: Real-Time Open-Vocabulary Object Detection* | CVPR 2024 | Bootstrapping labels for new classes (forklift, pallet jack, cone) | GPL-3.0 |
| P10 | Liu et al., *Grounding DINO* | ECCV 2024 | Text-prompted box proposals for annotation; 52.5 AP zero-shot COCO (reported) | Apache-2.0 |
| P11 | Minderer et al., *Scaling Open-Vocabulary Object Detection* (OWLv2) | NeurIPS 2023 | Self-training at web scale; good long-tail proposals | Apache-2.0 |
| P12 | Wang et al., *YOLOE: Real-Time Seeing Anything* | ICCV 2025 | Real-time text/visual prompts | AGPL-3.0 |
| P13 | Ravi et al., *SAM 2: Segment Anything in Images and Videos* | ICLR 2025 | Mask propagation for fast video annotation (spills, zones, equipment outlines) | Apache-2.0 |

**Verdict:** keep a closed-set detector for production alerts (validated per class), use Grounding DINO / OWLv2 / SAM 2 in an annotation pipeline to cut labelling cost, and retire the AGPL dependency for any commercial build by moving to RT-DETR, D-FINE or RF-DETR **after** a like-for-like comparison on our validation sets.

## 3. Multi-object tracking

| ID | Paper | Venue / year | Core idea | Reported | Licence | Fit |
|---|---|---|---|---|---|---|
| P01 | Zhang et al., *ByteTrack: Multi-Object Tracking by Associating Every Detection Box* | ECCV 2022 | Associate low-score boxes in a second pass to survive occlusion | MOT17: 80.3 MOTA, 77.3 IDF1, 63.1 HOTA | MIT | **In use.** Fast, simple, good baseline |
| P02 | Cao et al., *Observation-Centric SORT* (OC-SORT) | CVPR 2023 | Re-anchors the Kalman filter on observations after occlusion; handles non-linear motion | MOT17 63.2 HOTA; DanceTrack 55.1 HOTA | MIT | Better for workers who stop/turn; cheap drop-in |
| P03 | Aharon et al., *BoT-SORT: Robust Associations Multi-Pedestrian Tracking* | arXiv 2022 | Camera-motion compensation + appearance re-ID | MOT17 65.0 HOTA (reported) | MIT (check) | Camera motion compensation matters for construction poles that sway |
| P04 | Somers et al., *CAMELTrack: Context-Aware Multi-cue ExpLoitation for Online MOT* | arXiv 2025 | Learned association over multiple cues instead of hand-tuned heuristics | MOT17 62.4 HOTA; DanceTrack 69.3 HOTA; ~13 FPS | check | Research; heavier |
| P05 | Gao et al., *Multiple Object Tracking as ID Prediction* (MOTIP) | CVPR 2025 | End-to-end tracking as ID classification | DanceTrack 67.5 HOTA (as compared in P04) | check | Research; end-to-end trackers still trail on crowded MOT17-like scenes |

**Verdict:** the bottleneck is not the tracker algorithm but **measurement**: SafeSight has never measured ID switches against ground truth. First label 10–20 minutes of site footage with identities and compute HOTA/IDF1; then compare ByteTrack, OC-SORT and BoT-SORT. Choose on site data. For safety events, ID switches matter mainly through duplicate incidents and broken dwell-time counts, which the event-level metrics in `09` measure directly.

## 4. Pose estimation and skeleton-based action recognition

| ID | Paper | Venue / year | Reported | Licence | Fit |
|---|---|---|---|---|---|
| P14 | Jiang et al., *RTMPose: Real-Time Multi-Person Pose Estimation based on MMPose* | arXiv 2023 | RTMPose-m 75.8 AP COCO; 90+ FPS on a laptop CPU, 430+ FPS on a GTX 1660 Ti (reported) | Apache-2.0 | **Best practical choice** for person-down, reach-in and ergonomic screening on the edge |
| P15 | Lu et al., *RTMO: Towards High-Performance One-Stage Real-Time Multi-Person Pose Estimation* | CVPR 2024 | ~74.8 AP COCO val at about 141 FPS on V100 (RTMO-l, reported) | Apache-2.0 | One-stage; cost does not grow with the number of people |
| P16 | Xu et al., *ViTPose: Simple Vision Transformer Baselines for Human Pose Estimation* | NeurIPS 2022 | Up to 80.9 AP COCO test-dev (largest model) | Apache-2.0 | Accurate but heavy; use as a teacher for pseudo-labels (as the repo already did with a pose teacher) |
| P18 | Yan et al., *Spatial Temporal Graph Convolutional Networks for Skeleton-Based Action Recognition* (ST-GCN) | AAAI 2018 | NTU RGB+D X-Sub 81.5 % | open implementations | Classic baseline for skeleton actions |
| P17 | Duan et al., *Revisiting Skeleton-based Action Recognition* (PoseC3D) | CVPR 2022 | Heatmap-volume 3D-CNN; robust to pose noise | Apache-2.0 (MMAction2) | Better than graph models under noisy 2D poses |

**Ergonomics evidence (P37).** Studies comparing 2D-pose-derived RULA with IMU or expert scores report moderate agreement for total scores but poor agreement for body-part scores; most high-agreement REBA results use multi-view 3D capture. **Conclusion:** ergonomic output must be framed as *screening and trend analytics* for tasks and stations, never as an individual assessment.

## 5. Video understanding and temporal events

| ID | Paper | Venue / year | Relevance | Verdict |
|---|---|---|---|---|
| P19 | Wang et al., *VideoMAE V2: Scaling Video Masked Autoencoders with Dual Masking* | CVPR 2023 | Strong video backbone (90.0 % top-1 Kinetics-400 at the largest size, reported) | Too heavy for multi-camera edge; useful as an offline teacher |
| P39 | Wang et al., *InternVideo2* | ECCV 2024 | Video foundation model (billions of parameters) | Offline search and review only |
| P24 | *OmniFall: A Unified Staged-to-Wild Benchmark for Human Fall Detection* | arXiv 2025 | Unifies eight staged fall datasets, adds genuine accident videos; pretrained I3D/VideoMAE lose **over 40 %** accuracy on real-world data | **The key warning:** staged fall data does not transfer. Person-down must be validated on site footage and framed as "possible person down, confirm" |
| P35 | *Toolbox Spotter: A Computer Vision System for Real World Situational Awareness in Heavy Industries* | arXiv 2021 | Deployed heavy-industry system; documents the trade-off between alert delay and false-positive frequency | Confirms SafeSight's confirmation-time design; delay must be a per-hazard policy parameter |

## 6. Vehicle–pedestrian interaction, trajectory and time-to-collision

| ID | Paper | Venue / year | Core idea | Fit |
|---|---|---|---|---|
| P45 | Gettman & Head, *Surrogate Safety Measures from Traffic Simulation Models* (FHWA-RD-03-050) | FHWA 2003 | Defines and operationalises TTC, PET and related conflict measures | **Method foundation** for near-miss analytics |
| P21 | Manglik, Weng, Ohn-Bar, Kitani, *Forecasting Time-to-Collision from Monocular Video* | IROS 2019 | Learned TTC from egocentric video; 13,658 clips; ~0.75 s mean error (reported) | Shows learned TTC is possible; for fixed cameras, geometric TTC on a calibrated floor is simpler and auditable |
| P44 | Kataoka et al., *Drive Video Analysis for the Detection of Traffic Near-Miss Incidents* | ICRA 2018 | Near-miss anticipation in traffic video (~3.65 s ahead, reported) | Evidence that near misses are learnable events; traffic domain |
| P36 | Kaina, Azmani, Amami, *YOLOv8-Based Near-Miss Detection in Smart Warehouses: A Geometric Proximity Framework with Driver Filtering* | ICAIIS 2026 | Vision-only forklift–pedestrian near misses with geometric distance and driver filtering | Directly relevant; tiny evaluation ("perfect" on one held-out sequence) means unproven |
| P20 | Salzmann et al., *Trajectron++* | ECCV 2020 | Graph-structured, dynamics-aware probabilistic trajectory forecasting | Only if it beats constant-velocity on site data (it often does not on short horizons) |
| P43 | Alahi et al., *Social LSTM* | CVPR 2016 | Social pooling for pedestrian trajectories | Historical baseline |
| P33 | Cai et al., *A context-augmented deep learning approach for worker trajectory prediction on unstructured and dynamic construction sites* | Advanced Engineering Informatics 2020 | Context (site layout) improves worker trajectory prediction | Construction-specific evidence that layout context helps |
| P31 | Son, Seong, Choi, Kim, *Real-time vision-based warning system for prevention of collisions between workers and heavy equipment* | J. Computing in Civil Engineering 2019 | Detection + distance warnings around equipment | Precedent for C4/C6 hazards |
| P32 | Yan, Zhang, Li, *Computer vision-based recognition of 3D relationship between construction entities for monitoring struck-by accidents* | Computer-Aided Civil and Infrastructure Engineering 2020 | 3D spatial relations from monocular images for struck-by risk | Supports ground-plane reasoning instead of image-space overlap |

**Verdict:** build ground-plane calibration (homography from four floor points, with an error estimate) and compute separation, closing speed, TTC and PET from tracked footprints. This is cheap, explainable and directly testable. It is also what most "proximity" products skip.

## 7. Construction-safety computer vision (domain literature)

| ID | Paper | Venue / year | Contribution |
|---|---|---|---|
| P27 | Fang, Ding, Love, et al., *Computer vision applications in construction safety assurance* | Automation in Construction 2020 | Review; identifies the gap between detection accuracy and site-level usefulness |
| P28 | Nath, Behzadan, Paal, *Deep learning for site safety: Real-time detection of personal protective equipment* | Automation in Construction 2020 | Pictor-PPE; compares worker-level vs. object-level PPE reasoning (worker-level association is the right approach, as SafeSight does) |
| P30 | Fang, Li, Luo, et al., *Detecting non-hardhat-use by a deep learning method from far-field surveillance videos* | Automation in Construction 2018 | Far-field hard-hat detection; directly relevant to SafeSight's distant-worker failure |
| P29 | Fang, Ding, Luo, Love, *Falls from heights: A computer vision-based approach for safety harness detection* | Automation in Construction 2018 | Harness detection; does not establish tie-off |
| P34 | Yu, Yang, Li, et al., *Joint-level vision-based ergonomic assessment tool for construction workers* | J. Construction Engineering and Management 2019 | Pose-based ergonomics |
| P23 | Chen & Zou, *Are Large Pre-trained Vision Language Models Effective Construction Safety Inspectors?* (ConstructionSite 10k) | arXiv 2025 | 10,013 images with captions, rule-violation VQA and grounding; VLMs generalise in zero/few-shot but need training for real sites |
| P22 | Adil et al., *Using Vision Language Models for Safety Hazard Identification in Construction* | arXiv 2025 | 1,100 site images; GPT-4o and Gemini 1.5 Pro best (BERTScore 0.906 / 0.888); latency limits real-time use |

## 8. Vision-language models (VLMs)

| ID | Model | Licence | Realistic role |
|---|---|---|---|
| P40 | Qwen2.5-VL (3B/7B/72B), technical report 2025 | 7B Apache-2.0; 3B licence disputed across sources (check the model card); 72B own licence | Offline: incident summaries, natural-language search over events, review assistance |
| P41 | Florence-2 (Xiao et al., CVPR 2024) | MIT | Small (0.23–0.77 B); captioning and grounding for annotation pipelines on the edge |

**Rules for VLM use (analysis):** never the sole basis of an alert; outputs labelled as AI-generated drafts; every claim in a generated report must link to the event record and evidence; evaluate hallucination rate on SafeSight's own incident set before shipping; keep inference on-premises when evidence contains people.

## 9. Spills, fire and environmental detection

| ID | Paper | Contribution | Verdict |
|---|---|---|---|
| P25 | *SynSpill: Improved Industrial Spill Detection With Synthetic Data* (ICCV-W 2025) | 2,000 synthetic images plus real CCTV; improves detectors and VLMs on spills | Promising; P3 |
| P26 | *Detecting spills using thermal imaging, pretrained deep learning models, and a robotic platform* (2025) | RGB struggles to separate water from floor; thermal helps until temperature equalises | Confirms spill detection is hard with CCTV |
| D12 | D-Fire dataset (de Venâncio et al., Neural Computing and Applications 2022) | 21,527 images, fire and smoke boxes, many hard negatives | Supplemental fire/smoke indicator only; NFPA 72 listing rules apply to real detection [L12] |

## 10. Sensor fusion

| Source | Contribution | Fit |
|---|---|---|
| ViPER+ (Applied Sciences 2023) | Vehicle pose from multiple UWB tags on heavy equipment, robust to non-line-of-sight | Dynamic exclusion zones from equipment telemetry |
| Everguard Sentri360 (industry) | CV + RTLS + wearables | Confirms the market direction; SafeSight should accept RTLS/telemetry as zone and context inputs rather than build hardware |
| ONVIF Profile M [L13], MQTT Sparkplug 3.0 (ISO/IEC 20237:2023) [L14], OPC UA (IEC 62541) | Standard metadata/event and machine-state channels | Native protocol support is the cheapest route to context |

## 11. Edge inference

| Option | Notes |
|---|---|
| TensorRT FP16/INT8 on NVIDIA GPUs and Jetson | Standard route; INT8 needs calibration data from site footage and re-validation |
| ONNX Runtime / OpenVINO | CPU and Intel iGPU sites; licence-friendly |
| Jetson Orin Nano Super (67 sparse INT8 TOPS, 7–25 W, about USD 399 dev kit as of 2026) / Orin NX / AGX Orin (275 sparse TOPS) | Prices rose sharply in 2026 (AGX Orin dev kit reported at USD 3,499) [hardware sources in `14`]; plan on Orin NX-class boxes for 4–8 streams; must be measured |
| Current workstation | One stream at 52–82 FPS without UI. **(analysis)** Batched multi-stream at 5–10 FPS per camera is plausible for 8–16 cameras on one RTX 2000 Ada; this is an estimate to measure in milestone M1, not a claim |

## 12. Opportunities for genuinely novel work

These are research bets, not features; each is assessed in `13`.

1. **Conformal risk control for per-camera alert thresholds.** Angelopoulos et al., *Conformal Risk Control* (ICLR 2024, P46), gives finite-sample guarantees on expected loss (for example a bound on the false-alarm rate) when calibration and deployment data are exchangeable. Applying it per camera, with operator-reviewed alerts as calibration data, would turn "we tuned a threshold" into "this camera is calibrated to at most X false alarms per hour on comparable footage, with a stated assumption". No competitor publishes anything similar.
2. **Ground-plane surrogate safety measures with uncertainty.** TTC/PET from monocular tracked footprints, with error propagated from calibration and detection jitter, reported as intervals.
3. **Automated HECA-style exposure accounting.** Count high-energy exposures and whether a direct control (barrier, closed gate, machine locked out via PLC) was present, aligned with the EEI method.
4. **Operator feedback as a data engine.** Every "false alarm" review becomes a labelled hard negative with camera and context; drift appears as a rising false-alarm rate per camera.
5. **Skeleton-only and redacted evidence.** Store pose and boxes by default and keep full frames only for confirmed high-risk events, reducing privacy impact while preserving investigability.
