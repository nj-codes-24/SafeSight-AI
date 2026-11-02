"""Start, inspect and keep alive the watchdog.

    python watchdog_svc/supervisor.py start     launch the watchdog detached (via WMI, outside this shell's job)
    python watchdog_svc/supervisor.py ensure    restart the watchdog if it is dead and work remains
    python watchdog_svc/supervisor.py status    print the health summary
    python watchdog_svc/supervisor.py submit --exp NAME --config FILE --data YAML [--batch N]
    python watchdog_svc/supervisor.py install-task / remove-task    per-user 5-minute 'ensure' scheduled task
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "runs" / "control"
PY = str(Path(sys.executable))
TASK = "SafeSightWatchdogKeeper"


def watchdog_pid():
    try:
        pid = int((CONTROL / "watchdog.pid").read_text())
        if "watchdog.py" in " ".join(psutil.Process(pid).cmdline()):
            return pid
    except (OSError, ValueError, psutil.Error):
        pass
    return None


def start(extra=""):
    if pid := watchdog_pid():
        print(f"watchdog already running pid={pid}")
        return
    log = ROOT / "logs" / "watchdog" / "watchdog_stdout.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmdline = f'"{Path(PY).with_name("pythonw.exe")}" "{ROOT / "watchdog_svc" / "watchdog.py"}" {extra}'
    ps = (f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
          f"@{{CommandLine='{cmdline}'; CurrentDirectory='{ROOT}'}}; $r.ProcessId; $r.ReturnValue")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    print(out.stdout.strip(), out.stderr.strip())
    for _ in range(30):
        time.sleep(1)
        if pid := watchdog_pid():
            print(f"watchdog running pid={pid}")
            return
    print("watchdog did not start; see", log)


def work_remaining():
    try:
        state = json.loads((CONTROL / "state.json").read_text())
    except (OSError, ValueError):
        state = {}
    try:
        queue = json.loads((CONTROL / "queue.json").read_text())
    except (OSError, ValueError):
        queue = []
    return bool(state.get("job") or queue)


def submit(a):
    CONTROL.mkdir(parents=True, exist_ok=True)
    q = json.loads((CONTROL / "queue.json").read_text()) if (CONTROL / "queue.json").exists() else []
    q.append({"exp": a.exp, "cmd": ["training/train.py", "--exp", a.exp, "--config", a.config],
              "data": a.data, "batch": a.batch})
    (CONTROL / "queue.json").write_text(json.dumps(q, indent=1))
    print("queued", a.exp, "queue length", len(q))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "ensure", "status", "submit", "install-task", "remove-task"])
    ap.add_argument("--exp")
    ap.add_argument("--config")
    ap.add_argument("--data")
    ap.add_argument("--batch", type=int)
    a = ap.parse_args()
    if a.cmd == "start":
        start()
    elif a.cmd == "ensure":
        if work_remaining() and not watchdog_pid():
            start()
    elif a.cmd == "submit":
        submit(a)
    elif a.cmd == "status":
        print("watchdog pid:", watchdog_pid())
        p = ROOT / "logs" / "watchdog" / "latest_health_report.txt"
        print(p.read_text(encoding="utf-8") if p.exists() else "no report yet")
    elif a.cmd == "install-task":
        tr = f'"{Path(PY).with_name("pythonw.exe")}" "{ROOT / "watchdog_svc" / "supervisor.py"}" ensure'
        subprocess.run(["schtasks", "/Create", "/F", "/TN", TASK, "/SC", "MINUTE", "/MO", "5", "/TR", tr], check=True)
    elif a.cmd == "remove-task":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK], check=True)
