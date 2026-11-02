"""Check that this machine can run SafeSight AI, without starting the app or loading data.

    python scripts/verify_installation.py

Reports, in order: Python version, required packages, CUDA, the model weights and their checksum against
models/model_config.yaml, the demo clips, and the runtime configuration. Exit code 0 means ready to run the app;
1 means something required is missing (each line says what to do).
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["torch", "ultralytics", "cv2", "numpy", "pandas", "streamlit", "plotly", "yaml", "psutil", "lap"]
ok = True


def report(status: str, what: str, detail: str = "") -> None:
    global ok
    if status == "FAIL":
        ok = False
    print(f"[{status:4}] {what}" + (f" - {detail}" if detail else ""))


def recorded_sha() -> str:
    cfg = ROOT / "models" / "model_config.yaml"
    for line in cfg.read_text(encoding="utf-8").splitlines() if cfg.exists() else []:
        if line.startswith("sha256:"):
            return line.split(":", 1)[1].strip().upper()
    return ""


def main() -> int:
    v = sys.version_info
    report("OK" if (v.major, v.minor) == (3, 11) else "WARN", f"Python {v.major}.{v.minor}.{v.micro}",
           "" if (v.major, v.minor) == (3, 11) else "tested with Python 3.11 only")

    missing = [m for m in REQUIRED if importlib.util.find_spec(m) is None]
    report("FAIL" if missing else "OK", "Python packages",
           f"missing {', '.join(missing)}; run: pip install -r requirements.txt" if missing else "all present")

    if "torch" not in missing:
        import torch

        if torch.cuda.is_available():
            report("OK", "CUDA", f"{torch.cuda.get_device_name(0)}, torch {torch.__version__}")
        else:
            report("WARN", "CUDA", "not available; the app runs on CPU at much lower FPS")

    weights = ROOT / "models" / "best.pt"
    if not weights.exists():
        report("FAIL", "Model weights", "models/best.pt not found; see models/README.md")
    else:
        sha = hashlib.sha256(weights.read_bytes()).hexdigest().upper()
        want = recorded_sha()
        if want and sha == want:
            report("OK", "Model weights", f"models/best.pt matches the recorded M5 checksum {sha[:12]}...")
        else:
            report("WARN", "Model weights", f"models/best.pt checksum {sha[:12]}... differs from models/model_config.yaml")

    manifest = ROOT / "data" / "demo" / "demo_clips.json"
    if manifest.exists():
        clips = json.loads(manifest.read_text(encoding="utf-8"))
        have = [c["file"] for c in clips if (ROOT / "data" / "demo" / c["file"]).exists()]
        status = "OK" if len(have) == len(clips) else ("WARN" if have else "WARN")
        report(status, "Demo clips", f"{len(have)} of {len(clips)} present; see data/README.md to fetch them"
               if len(have) < len(clips) else f"all {len(clips)} present")
    else:
        report("WARN", "Demo clips", "data/demo/demo_clips.json missing")

    rc = ROOT / "models" / "runtime_config.json"
    if rc.exists():
        try:
            cfg = json.loads(rc.read_text(encoding="utf-8"))
            report("OK", "Runtime configuration", f"{sum(len(v) for v in cfg.get('zones', {}).values())} zones; "
                   f"no-helmet threshold {cfg.get('no_helmet_conf', 0.60)} (default 0.60)")
        except json.JSONDecodeError as e:
            report("FAIL", "Runtime configuration", f"models/runtime_config.json is not valid JSON: {e}")
    else:
        report("WARN", "Runtime configuration", "models/runtime_config.json missing; defaults apply and no zones are set")

    print("\nReady to run: python launch.py" if ok else "\nNot ready: fix the FAIL lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
