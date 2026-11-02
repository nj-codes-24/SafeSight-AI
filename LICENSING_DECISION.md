# Licensing decision and analysis

**Decision (2 November 2026):** SafeSight AI is released as a **public, open-source academic project**.
- **The project's original source code and documentation** are licensed under the **GNU Affero General Public License v3.0 only** (AGPL-3.0-only); see [`LICENSE`](LICENSE).
- **Trained checkpoint files are not distributed.**
- **Third-party datasets, media and dependencies** keep their own licences. Applying AGPL-3.0 to this project's code does **not** relicense any of them.

> This is an engineering analysis written to support the maintainer's decision, using the official texts listed under [Sources checked](#sources-checked). It is not legal advice. Where an outcome depends on someone else's interpretation, it is listed as an open question rather than assumed.

## 1. What the licence covers and what it does not

| Material | Licence | In the public repository? |
|---|---|---|
| **Original source code:** `app/`, `inference/`, `database/`, `training/`, `watchdog_svc/`, `scripts/`, `tests/`, `presentation/make_figures.py`, `launch.py` | **AGPL-3.0-only** (this project) | Yes |
| **Original documentation, configuration, diagrams, wordmark** and evaluation results (`docs/`, `reports/`, `*.md`, `*.yaml`, `*.toml`, `assets/project_identity/`) | **AGPL-3.0-only** (this project) | Yes |
| Ultralytics library, YOLO26n and YOLO26l-pose base weights | AGPL-3.0 (Ultralytics), or Ultralytics Enterprise | No: installed from PyPI or downloaded by the user |
| **M5 weights** and every other trained checkpoint (B0, M1–M4) | **Not licensed by this project; not distributed** (see section 3) | **No** |
| Construction-PPE dataset | AGPL-3.0 (Ultralytics) | No |
| Mendeley PPE dataset v6 | CC BY 4.0 | No |
| SH17 dataset (images from Pexels) | CC BY-NC-SA 4.0 (Pexels terms also apply to the images) | No |
| SHWD (experiment M3 only) | MIT repository; SCUT-HEAD parts carry their own terms | No |
| Screenshots in `assets/screenshots/` | **CC BY-SA 3.0 / 4.0**, inherited from the Wikimedia Commons footage they show; **not AGPL** | Yes, with attribution |
| Demo videos | CC BY-SA (Commons); Mixkit Stock Video Free License | No: fetched by scripts |
| Python dependencies | Their own licences ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)) | No: installed by the user |

**Copyright notice for the project's own work:** Copyright (C) 2026 nj-codes-24 and SafeSight AI contributors.

## 2. Is AGPL-3.0 the right licence for the code?

**Yes.** The code imports and drives Ultralytics, which is AGPL-3.0, so licensing the whole project's code under AGPL-3.0 removes any question of incompatibility with its central dependency.

**It also matches Ultralytics' own published guidance.** Their licence page offers two routes:
- "Open-source your entire project under AGPL-3.0".
- An Enterprise licence.

It lists "Academic research and university coursework" and "Personal projects, learning, and experimentation" under the free AGPL-3.0 tier. Permissive licences (MIT, Apache-2.0) were ruled out by the maintainer, and would sit uneasily with an AGPL-3.0 dependency.

**Version: "AGPL-3.0-only".** This states exactly what was chosen. Switching to "or later" is possible in a future release if wanted.

## 3. M5 weights: AGPL-3.0 against SH17's CC BY-NC-SA 4.0

**The two claims on M5:**
- **Ultralytics:** "All Ultralytics YOLO trained models fall under the AGPL-3.0 License by default," and "The AGPL-3.0 License covers the training code and the models produced by that training code." M5 was produced by Ultralytics training code from Ultralytics base weights.
- **SH17:** "The SH17 dataset is released under CC BY-NC-SA 4.0 license." If M5 is an adaptation of SH17, then:
  - any sharing must be non-commercial;
  - any sharing must be under BY-NC-SA 4.0 or a compatible licence. Creative Commons states: "Currently, no non-CC licenses have been designated as compatible with BY-NC-SA 4.0." The one-way GPLv3 compatibility applies to BY-SA, not BY-NC-SA.

**The conflict:**
- AGPL-3.0 section 10 says: "You may not impose any further restrictions on the exercise of the rights granted or affirmed under this License." A non-commercial condition is such a restriction.
- SH17's ShareAlike forbids relicensing the adaptation under AGPL-3.0.
- **So if both claims hold, M5 cannot be shared under any licence that satisfies both,** publicly or privately, without permission from one side. Non-commercial or academic intent does **not** remove this. ShareAlike controls the licence of the adaptation, not only how it is used.

**Does withholding M5 make the code release compliant?** On the licence texts, yes:

| Clause | What it says | Effect here |
|---|---|---|
| AGPL-3.0 section 0 | To "convey" means propagation "that enables other parties to make or receive copies"; "Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying." | Keeping M5 on the maintainer's machine is not conveying |
| AGPL-3.0 section 2 | "You may make, run and propagate covered works that you do not convey, without conditions so long as your license otherwise remains in force." | Training and using M5 locally carries no AGPL distribution obligation |
| AGPL-3.0 section 13 | Applies only when a modified Program is offered to users "interacting with it remotely through a computer network" | Not triggered: there is no public network service |
| CC BY-NC-SA 4.0 | ShareAlike and NC attach to **sharing** Adapted Material, and SH17 is used here for non-commercial academic training | Nothing derived from SH17 is shared: no weights, no derived labels, no images. Only aggregate metrics, which are facts, appear in the reports. |

**Conclusion: no blocker to publishing the code under AGPL-3.0 while withholding M5.** Every artifact that is distributed (code, docs, reports, screenshots) has a clear licence, and nothing distributed is derived from SH17 in a way that triggers ShareAlike.

**Residual risk.** Ultralytics' guidance is broader than the licence text:
- **It says** AGPL compliance means publishing "the complete corresponding source code for the entire derivative work," which may include "model weights" "where applicable".
- **It lists** "R&D projects that are not fully open-sourced" as needing an Enterprise licence.
- **Ultralytics could therefore regard the project as incomplete without M5.** If they did, M5 still could not be released without SH17 permission.

**Remedies, if Ultralytics raises this:**
1. Release a model retrained **without SH17** under AGPL-3.0. The M2/M4 lineage uses only Construction-PPE (AGPL-3.0), Mendeley (CC BY 4.0) and AGPL-3.0 pseudo-labels.
2. Obtain SH17 authors' permission to license M5 under AGPL-3.0.
3. Obtain an Enterprise licence.

## 4. Conditions for staying compliant

| # | Rule | Why |
|---|---|---|
| 1 | Do not commit, attach to a release or link any `*.pt` checkpoint (M5, M2, M3, M4, B0) | Section 3, and the maintainer's decision |
| 2 | **Do not host a public live demo** (a web server reachable by others) that runs M5. Local demonstrations and screen recordings are fine. | A public service running M5 would arguably bring AGPL-3.0 section 13 and Ultralytics' guidance into play for the model, recreating the conflict |
| 3 | Do not publish the derived SH17 `no_helmet` labels or any SH17 images, crops or evidence frames | They would be Adapted Material of SH17 (and Pexels images) |
| 4 | Keep third-party attributions in THIRD_PARTY_NOTICES.md, and keep the screenshot licence notice | CC BY and CC BY-SA require attribution; BY-SA requires the licence to be indicated |
| 5 | Keep Mixkit clips and their frames out of the repository | Standalone redistribution is unconfirmed |
| 6 | Contributions are accepted under AGPL-3.0-only (inbound = outbound) | Keeps the code base under one licence ([CONTRIBUTING.md](CONTRIBUTING.md)) |

## 5. Questions to send for written clarification (recommended, not blocking)

**Ultralytics:**
- **U1.** Do you regard weights fine-tuned from YOLO26n with your training code as AGPL-3.0 works, and must they be published when the project's source is published, even if the weights are never distributed or served?
- **U2.** Is a project that publishes all of its code under AGPL-3.0 but withholds a fine-tuned checkpoint (because a training dataset is CC BY-NC-SA 4.0) compliant with your terms for academic use?
- **U3.** Do models trained on Construction-PPE inherit AGPL-3.0 from the dataset?

**SH17 authors (Hafiz Mughees Ahmad, Afshin Rahimi):**
- **S1.** Do you regard weights trained on SH17 as Adapted Material under CC BY-NC-SA 4.0?
- **S2.** Would you permit distributing a YOLO26n checkpoint fine-tuned on a 1,819-image SH17 subset under AGPL-3.0, with attribution, for research and education? Under what licence do you distribute your own released YOLOv8–v10 weights?
- **S3.** May derived `no_helmet` annotations be published under CC BY-NC-SA 4.0?

If both U2 and S2 come back favourable, M5 could later be published, but only with a fresh licensing review at that time.

## 6. Sources checked (2 November 2026)

| Source | Points used |
|---|---|
| Ultralytics licence page, https://www.ultralytics.com/license | Two routes (AGPL-3.0 or Enterprise); trained models AGPL-3.0 by default; academic and personal projects in the free tier; "entire derivative work" may include weights |
| GNU AGPL-3.0, official text https://www.gnu.org/licenses/agpl-3.0.txt (SHA-256 `0D96A4FF…ABCB0`, copied verbatim to `LICENSE`) | Sections 0 (convey), 2, 10, 13 |
| Creative Commons, *Compatible licenses*, https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/ | No non-CC licence compatible with BY-NC-SA 4.0; GPLv3 compatibility is one-way and for BY-SA only |
| SH17 repository, https://github.com/ahmadmughees/SH17dataset | CC BY-NC-SA 4.0; images scraped from Pexels (Pexels terms apply); authors' own YOLO weights released with no separate licence stated; citation DOI 10.1016/j.jnlssr.2024.09.002 |
