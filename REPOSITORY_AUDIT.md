# Repository audit and release checklist (v0.1.0)

Prepared on 2 November 2026 from the local project folder `D:\safesight-AI`, for the **first public open-source academic release** of `nj-codes-24/SafeSight-AI`.
- At audit time the GitHub repository was **private and empty**.
- Nothing has been committed or pushed.
- Repository visibility has not been changed.

## 1. Initial state

- **Git:** there was no local repository. `git init -b main` was run so the release set could be audited; nothing is staged or committed.
- **Total size:** about 42 GB, nearly all data (35 GB), the virtual environment (4.9 GB), training runs (1.6 GB), and demo and QA media.
- **Release set:** **295 files, about 15.5 MB** of code, configuration, documentation, JSON results, charts, screenshots and the licence.

## 2. Reorganisation

| From | To | Note |
|---|---|---|
| 10 evaluation scripts in `tests/` | `scripts/evaluation/` | Root paths fixed; `tests/` now holds only tests |
| `watch_training.py` | `scripts/watch_training.py` | Root path fixed |
| Browser QA tools (`design/`, `demo_audit/`) | `scripts/qa/` with a shared `cdp.py` | Outputs go to the git-ignored `.qa/` |
| Root records (`PROJECT_STATUS`, `DATASETS`, demo guides, readiness audit, freeze manifest) | `docs/records/` | Kept unchanged as snapshots |
| UI design docs | `docs/design/` | |
| `pytest.ini` | `pyproject.toml` | Also holds project metadata, the licence expression and the Ruff configuration |

**Unchanged:** `inference/`, `database/` and `models/best.pt` (SHA-256 `E9B2583D…CC3C7534`).

**New files:**
- Licensing and notices: `LICENSE` (verbatim AGPL-3.0), `LICENSING_DECISION.md`, `THIRD_PARTY_NOTICES.md`
- Policies and metadata: `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`
- Configuration: `.gitignore`, `.gitattributes`, `.env.example`, `requirements-dev.txt`, `requirements-ci.txt`
- GitHub: `.github/` (CI workflow, issue and PR templates)
- Documentation: 11 files in `docs/`
- Assets: `assets/` (7 screenshots, 2 wordmarks)
- Folder guides: `models/README.md`, `data/README.md`
- Tooling: `scripts/verify_installation.py`

## 3. Excluded from the repository, and why

| Excluded | Reason |
|---|---|
| All `*.pt` (M5, M2, M3, M4, B0 and the Ultralytics base weights) | M5 may be bound by both AGPL-3.0 and SH17's CC BY-NC-SA 4.0, which conflict; by decision, no checkpoint is distributed ([LICENSING_DECISION.md](LICENSING_DECISION.md)) |
| `data/` except two manifests | Dataset licences (SH17 NC-SA, Construction-PPE AGPL-3.0, Pexels terms); size (SH17 alone is 14 GB) |
| `runs/` | Training checkpoints and caches |
| `logs/`, `*.db`, the CSV export | Incident records and evidence frames showing people |
| `*.mp4`, `*.webm`, `*.ogv`, `*.jpg`, `*.jpeg`, `*.zip` | Third-party footage (Mixkit redistribution unconfirmed), dataset images, evidence crops |
| `demo_audit/`, `design/` | Local QA captures, recordings and UI backups |
| `research_notes/`, `reports/Footfall*` | An unrelated project |
| `.venv/`, `.uv-python/`, `.ultralytics/`, `.claude/`, `.qa/`, caches | Machine-local state |

**SH17-related files that are included contain only facts:** counts in `reports/diagnostics/sh17_build.json` and `sh17_audit/audit.json`, lists of image file names in `sh17_audit/*.json`, a precision-recall chart, and code. No images, labels or coordinates are included.

## 4. Security and privacy

- **No credentials** were found in the release set. A pattern scan covered GitHub and AWS tokens, private keys, `api_key`, `password`, e-mail addresses and the Windows user name.
- **History is clean:** the Git history is new and empty, and the remote is empty. Gitleaks is not installed; optionally run `gitleaks detect --no-git -s .` before pushing.
- **Absolute local paths were removed** from three result files. Their numbers are unchanged.

  | File | SHA-256 before | SHA-256 after |
  |---|---|---|
  | `reports/unseen_compare/summary.json` | `84EE3DAF…EE9D` | `6D3E1A61…6E81` |
  | `reports/watchdog_real_kill_drill.json` | `75AFC07D…B28B` | `B3D1E5DB…A81F` |

  The "after" hashes include a line-ending repair: the first sanitisation wrote CR CR LF line endings. Parsed values were verified identical before and after.
  | `reports/runtime/performance.json` | weights path made relative | — |

- **Remaining path mentions:** the folder name `D:\safesight-AI` appears only in this file's commands and in the historical freeze manifest, deliberately.
- **Screenshots** show only CC BY-SA Wikimedia Commons footage, attributed in `assets/screenshots/README.md`. No evidence frames or Mixkit frames are included.

## 5. Licensing: decided and applied

Full analysis: **[LICENSING_DECISION.md](LICENSING_DECISION.md)**.

- **Code and docs:** the project's own code and docs are **AGPL-3.0-only**. `LICENSE` is the verbatim official text from gnu.org (SHA-256 `0D96A4FF…ABCB0`, 34,523 bytes). The licence expression is also set in `pyproject.toml` and `CITATION.cff`.
- **Sources:** verified against Ultralytics' licence page, the official AGPL-3.0 text, Creative Commons' compatibility list and the SH17 repository.
- **Third-party items keep their own licences:** datasets, screenshots (CC BY-SA), footage and dependencies. The README and THIRD_PARTY_NOTICES say so explicitly.
- **No blocker for a code-only AGPL-3.0 public release.**
  - Under AGPL-3.0 sections 0 and 2, models that are not conveyed carry no distribution obligation.
  - Nothing derived from SH17's content is distributed, so ShareAlike is not triggered.
- **Residual item, not blocking.** Ultralytics' guidance (trained models are AGPL "by default"; "entire project" may include weights) is broader than the licence text. Questions U1–U3 and S1–S3 are drafted for written clarification. Remedies are listed in case Ultralytics asks for the weights: a SH17-free retrain, SH17 permission, or an Enterprise licence.
- **Conditions to keep:** no checkpoint is ever published or linked; **no public live demo running M5**; no SH17-derived labels or images; attributions are kept.

## 6. Dependencies

- **Runtime:** `requirements.txt` pins the CUDA 12.6 build, unchanged. A CPU route is documented.
- **Development:** `requirements-dev.txt` adds Ruff 0.15.4.
- **CI:** `requirements-ci.txt` is a minimal set (NumPy, OpenCV headless, PyYAML, psutil, pytest, Ruff), with no PyTorch.
- **No dependency was removed.** SciPy and Matplotlib remain: Ultralytics and the report and presentation scripts use them.

## 7. Tests and checks performed (after all edits)

| Check | Result |
|---|---|
| `ruff check .` | **PASS** |
| Byte-compilation of all sources | **PASS** |
| Full suite with weights, clips and data (`pytest -rs`) | **PASS**: 32 passed |
| Clean minimal Python 3.11 environment, simulating CI | **PASS**: 21 passed, 1 module skipped with its reason |
| App without weights (simulated in `AppTest`, real file untouched) | **PASS**: message shown, play disabled, no exceptions |
| `scripts/verify_installation.py` | **PASS** on the development machine |
| Browser end-to-end flow (gallery, run, incidents, settings, CSV, upload, webcam, lock) | **PASS** before the release preparation ([docs/design/REDESIGN_QA.md](docs/design/REDESIGN_QA.md)) |
| Release-set audit: no weights, video, frame images, databases, files over 2 MB or secrets | **PASS** |
| `models/best.pt` checksum | **Unchanged** |

## 8. Public-release checklist

| Requirement | Status |
|---|---|
| Licensing analysis against official sources; no blocker | PASS |
| `LICENSE` (AGPL-3.0-only, verbatim) and scope statements in README, THIRD_PARTY_NOTICES and LICENSING_DECISION | DONE |
| Curated, licence-safe file set; secret scan; staged-file audit (in the script) | PASS |
| README for recruiters, researchers and developers; architecture diagrams; screenshots; model card | DONE |
| Docs: datasets, evaluation, training, installation, deployment, demo, limitations, troubleshooting | DONE |
| CHANGELOG, CONTRIBUTING (inbound = outbound), CODE_OF_CONDUCT, SECURITY, CITATION | DONE |
| CI workflow (lint and CPU tests on Windows) | READY; must be green on GitHub **before** visibility changes (stage B below) |
| Repository description and topics | Command in stage C |
| Clean-machine install from the README | NOT TESTED (documented as untested) |
| Data-preparation scripts re-run from a clean checkout | NOT TESTED (documented as untested) |

## 9. After publication

1. **Send** the clarification questions in LICENSING_DECISION.md section 5 to Ultralytics and the SH17 authors, and record the answers there.
2. **If Ultralytics expects weights to be published,** release a SH17-free retrained model under AGPL-3.0, or obtain SH17 permission. Do not publish M5 without one of these.
3. **In GitHub settings, enable** private vulnerability reporting (Security), so that SECURITY.md's reporting route works.

## 10. Commands (Windows PowerShell)

### Stage A: commit and push while the repository is still private

Copy the whole block, from `& {` to the final `}`. It runs as one script block, so the first failed check aborts every later step. It never force-pushes and never changes visibility.

```powershell
& {
Set-Location D:\safesight-AI
$repo = 'https://github.com/nj-codes-24/SafeSight-AI.git'

# 1. Repository and remote checks
if (-not (Test-Path .git)) { git init -b main }
$branch = git branch --show-current
if ($branch -ne 'main') { throw "Expected branch 'main', found '$branch'. Stop and check." }
if (git rev-parse --verify --quiet HEAD) { throw 'Local commits already exist. Stop and inspect git log.' }
if (@(git remote) -notcontains 'origin') { git remote add origin $repo }
$remote = git remote get-url origin
if ($remote -ne $repo) { throw "origin points elsewhere: $remote" }
$visibility = gh repo view nj-codes-24/SafeSight-AI --json visibility --jq .visibility
if ($LASTEXITCODE -ne 0 -or $visibility -ne 'PRIVATE') { throw "Repository visibility is '$visibility', not PRIVATE (or gh is not signed in). Stop." }
$heads = git ls-remote --heads origin
if ($LASTEXITCODE -ne 0) { throw 'Could not reach the remote. Check your GitHub sign-in.' }
if ($heads) { throw 'The remote already has branches. Stop and inspect before pushing.' }
if (-not (Test-Path LICENSE) -or (Get-FileHash LICENSE).Hash -ne '0D96A4FF68AD6D4B6F1F30F713B18D5184912BA8DD389F86AA7710DB079ABCB0') { throw 'LICENSE missing or not the verbatim AGPL-3.0 text.' }

# 2. Quality gates
.venv\Scripts\ruff.exe check .
if ($LASTEXITCODE -ne 0) { throw 'Lint failed.' }
.venv\Scripts\python.exe -m pytest -q -rs
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

# 3. Stage and audit what is staged
git add -A
$staged = @(git diff --cached --name-only)
"Staged files: $($staged.Count)"
$blocked = $staged | Where-Object { $_ -match '\.(pt|pth|onnx|engine|safetensors|mp4|webm|ogv|avi|mov|mkv|jpg|jpeg|db|db-wal|db-shm|sqlite|zip|npz)$' -or $_ -match '^(data/(raw|processed|cache|demo/uploads)|runs|logs|demo_audit|design|research_notes|\.venv|\.uv-python|\.ultralytics|\.claude|\.qa)/' -or $_ -match '(^|/)\.env$' }
if ($blocked) { $blocked; git reset; throw 'Restricted files were staged. Nothing committed.' }
$large = $staged | Where-Object { (Get-Item -LiteralPath $_).Length -gt 2MB }
if ($large) { $large; git reset; throw 'Unexpectedly large files were staged. Nothing committed.' }
$secrets = $staged | Where-Object { $_ -notmatch '\.png$' } | ForEach-Object { Select-String -LiteralPath $_ -Pattern 'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY' }
if ($secrets) { $secrets; git reset; throw 'Possible secret found. Nothing committed.' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { git reset; throw 'Whitespace errors or conflict markers found. Nothing committed.' }
git diff --cached --stat | Select-Object -Last 1
$staged | Out-GridView -Title 'Review the staged files, then close this window to continue (Ctrl+C in the terminal to abort)' -Wait

# 4. Commit and push
git commit -m "feat: initial open-source release of SafeSight AI v0.1.0 (AGPL-3.0)" -m "Monitoring app, CV pipeline, training and watchdog code, evaluation results, documentation and CI under AGPL-3.0-only. Trained model weights, datasets and restricted footage are not included (see LICENSING_DECISION.md)."
if ($LASTEXITCODE -ne 0) { throw 'Commit failed.' }
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Push failed. Nothing was forced; fix the cause and run git push -u origin main again.' }
git log --oneline -1
git ls-remote --heads origin
}
```

### Stage B: confirm CI passed on GitHub (still private)

```powershell
gh run list --repo nj-codes-24/SafeSight-AI --limit 3
$runId = gh run list --repo nj-codes-24/SafeSight-AI --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --repo nj-codes-24/SafeSight-AI --exit-status
```

Open the repository on GitHub and check that:
- the README renders, including the Mermaid diagrams and screenshots;
- `LICENSE` is detected as AGPL-3.0;
- no weights, video or data appear in the file list.

### Stage C: make the repository public (only when stages A and B have passed)

Before running this, confirm the CI run succeeded. This is the only step that changes visibility.

```powershell
& {
$ci = gh run list --repo nj-codes-24/SafeSight-AI --limit 1 --json conclusion --jq '.[0].conclusion'
if ($ci -ne 'success') { throw "Latest CI run is '$ci', not success. Do not publish yet." }
gh repo edit nj-codes-24/SafeSight-AI --description "AI-powered industrial safety monitoring using computer vision for PPE compliance, worker tracking and restricted-zone intrusion detection." --add-topic computer-vision,industry-4-0,industrial-safety,object-detection,yolo,pytorch,opencv,ppe-detection,worker-safety,bytetrack,machine-learning,streamlit
gh repo edit nj-codes-24/SafeSight-AI --visibility public --accept-visibility-change-consequences
gh repo view nj-codes-24/SafeSight-AI --json visibility,licenseInfo | ConvertFrom-Json | Format-List
}
```

**Authentication:** Git and `gh` use your existing GitHub sign-in (Git Credential Manager or the `gh` keyring). Do not put a token in any command.
