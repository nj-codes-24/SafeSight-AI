"""Start the SafeSight AI dashboard: python launch.py  (opens http://localhost:8501)"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
env = {**os.environ, "PYTHONPATH": str(ROOT), "YOLO_CONFIG_DIR": str(ROOT / ".ultralytics"), "YOLO_OFFLINE": "true"}
# The visual theme lives in .streamlit/config.toml, which Streamlit reads from this working directory.
sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "main.py"),
                          "--browser.gatherUsageStats", "false",
                          "--server.address", "localhost", "--client.toolbarMode", "viewer",
                          "--server.fileWatcherType", "none", "--server.maxUploadSize", "1024", *sys.argv[1:]],
                         cwd=ROOT, env=env))
