# Troubleshooting

Start with `python scripts\verify_installation.py`. It reports most problems below directly.

| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` is `False`; very low FPS | CPU build of PyTorch installed, or the driver is too old for CUDA 12.6 | `pip install -r requirements.txt` (it uses the cu126 index); update the NVIDIA driver; check with `nvidia-smi` |
| `No model at models/best.pt` / the player shows no play button | Weights missing | M5 is not distributed. If you lawfully hold it, place it at `models\best.pt` and verify the SHA-256 ([models/README.md](../models/README.md)); otherwise train a model ([training.md](training.md)) |
| `verify_installation.py` warns that the checksum differs | Different or retrained weights | Expected for your own models; the app still runs, but the documented results apply only to M5 |
| Gallery shows no demo clips | Clips not fetched | Run the three commands in [data/README.md](../data/README.md), or use **Upload video** |
| "No webcam is available on this computer" | No camera at device 0, or it is in use | Connect or free the camera; other indices need a code change in `app/sources.py` |
| Play is greyed out and the player says **Busy** | Another browser tab is running a clip (server-wide lock) | Stop it in that tab, or wait; the lock frees itself 4 s after a tab closes |
| "Starting · loading the detection model" for about 10 s | First run loads PyTorch and the model | Normal; later runs start within about 1 s |
| `Port 8501 is already in use` | An earlier server is still running | Close it, or run `python launch.py --server.port 8502` |
| Streamlit opens but the page is blank | Browser cache or extensions | Hard refresh (Ctrl+F5) or another browser; check the terminal for a Python traceback |
| `ModuleNotFoundError: inference` when running a script | Run from another folder | Run scripts from the repository root |
| Settings changes do not apply | Settings apply from the **next** run | Stop and start the clip again |
| `Activate.ps1 cannot be loaded` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Tests skip `test_pipeline.py` | Weights, clips or processed data absent | Expected on a clean machine; the skip reason says what is missing |
