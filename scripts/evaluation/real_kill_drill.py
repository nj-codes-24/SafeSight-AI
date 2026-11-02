"""Hard-kill a real, watchdog-managed training run mid-way and report whether it resumed. Uses exp drill_real only."""
import json
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
exp = ROOT / "runs" / "drill_real"
state = ROOT / "runs" / "control" / "state.json"
out = {}
deadline = time.time() + 900
while time.time() < deadline:
    try:
        hb = json.loads((exp / "heartbeat.json").read_text())
    except (OSError, ValueError):
        hb = {}
    if hb.get("last_good_epoch", -1) >= 2 and hb.get("status") == "running":
        pid = hb["pid"]
        out["killed_pid"], out["killed_at_good_epoch"] = pid, hb["last_good_epoch"]
        psutil.Process(pid).kill()
        out["kill_time"] = time.time()
        break
    time.sleep(2)
print("killed", out, flush=True)
while time.time() < deadline + 600:
    try:
        hb = json.loads((exp / "heartbeat.json").read_text())
    except (OSError, ValueError):
        hb = {}
    if hb.get("pid") != out.get("killed_pid") and hb.get("status") == "running" and "resumed_at" not in out:
        out["resumed_at"] = time.time()
        out["resume_delay_s"] = round(out["resumed_at"] - out["kill_time"])
        out["resume_epoch"] = hb.get("epoch")
        out["new_pid"] = hb["pid"]
        print("resumed", out, flush=True)
    if hb.get("status") == "completed" and hb.get("pid") != out.get("killed_pid"):
        out["final_epoch"] = hb["epoch"]
        break
    time.sleep(2)
out["events"] = [e for e in json.loads(state.read_text())["events"] if e["kind"] in ("failure", "recovery", "launch")][-5:]
(ROOT / "reports" / "watchdog_real_kill_drill.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
