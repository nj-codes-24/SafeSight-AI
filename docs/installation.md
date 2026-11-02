# Installation

## Requirements

| | |
|---|---|
| OS | Windows 10/11 (development and testing). Core Python code is portable, but the watchdog keeper and some test helpers use Windows tools (WMI, `schtasks`, `taskkill`). |
| Python | **3.11** |
| GPU (recommended) | NVIDIA GPU with drivers that support **CUDA 12.6**. Developed on an RTX 2000 Ada (16 GB). The app itself needs well under 1 GB of VRAM. |
| Disk | About 6 GB for the virtual environment. Retraining needs about 40 GB more for datasets and runs. |
| Browser | Any current Chromium-based browser, or Firefox |

## 1. Clone and create an environment (PowerShell)

```powershell
git clone https://github.com/nj-codes-24/SafeSight-AI.git
cd SafeSight-AI
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## 2. Install dependencies

**GPU (CUDA 12.6):**

```powershell
pip install -r requirements.txt
```

**CPU only:** install the CPU builds of PyTorch first, then the rest without the CUDA index:

```powershell
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
Get-Content requirements.txt | Where-Object { $_ -notmatch '^(--extra-index-url|torch|torchvision)' } | Set-Content requirements-cpu.local.txt
pip install -r requirements-cpu.local.txt
```

**Development tools** (Ruff and pytest):

```powershell
pip install -r requirements-dev.txt
```

## 3. Model weights

The trained M5 weights are **not distributed** ([LICENSING_DECISION.md](../LICENSING_DECISION.md)). If you lawfully hold them, place them at `models\best.pt` and verify the SHA-256. Otherwise, train a model ([training.md](training.md)).

```powershell
(Get-FileHash models\best.pt -Algorithm SHA256).Hash
# E9B2583DCAE39613FFD94B907FB216A07C7039C304AC026700BCC364CC3C7534
```

## 4. Demo footage (optional)

```powershell
python training\fetch_demo_candidates.py
python training\fetch_mixkit.py
python training\prepare_demo.py
```

This needs internet access. Without clips, use **Upload video** or **Webcam** in the app. See [data/README.md](../data/README.md).

## 5. Verify

```powershell
python scripts\verify_installation.py
```

This checks the Python version, packages, CUDA, the weights' checksum, the demo clips and the runtime configuration.

## 6. Run

```powershell
python launch.py
```

Then open http://localhost:8501. The launcher sets `YOLO_CONFIG_DIR` (to the git-ignored `.ultralytics/`) and `YOLO_OFFLINE=true`, so nothing is fetched at runtime. Theme settings are read from `.streamlit/config.toml`.

## Other platforms

Linux and macOS are not tested. The app and inference modules use only portable Python, OpenCV and PyTorch. Replace the PowerShell commands with their shell equivalents (`python3.11 -m venv .venv`, `source .venv/bin/activate`), and on macOS use the CPU or MPS build of PyTorch. The watchdog keeper task (`supervisor.py install-task`) is Windows-only.
