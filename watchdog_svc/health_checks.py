"""Read-only health probes used by the watchdog. None of these import torch or touch training state."""
import csv
import json
import math
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

import psutil


def process_status(pid, create_time=None) -> str:
    """alive / dead / zombie. create_time guards against Windows reusing a dead PID."""
    if not pid:
        return "dead"
    try:
        p = psutil.Process(pid)
        if create_time and abs(p.create_time() - create_time) > 2:
            return "dead"
        return "zombie" if p.status() == psutil.STATUS_ZOMBIE else "alive"
    except psutil.Error:
        return "dead"


def kill_tree(pid) -> None:
    try:
        parent = psutil.Process(pid)
        procs = parent.children(recursive=True) + [parent]
    except psutil.Error:
        return
    for p in procs:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=20)


def read_heartbeat(exp_dir: Path):
    try:
        return json.loads((exp_dir / "heartbeat.json").read_text())
    except (OSError, ValueError):
        return None


def gpu_stats(pid=None) -> dict:
    fields = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        if out.returncode:
            return {"ok": False, "error": (out.stderr or out.stdout).strip()[:300]}
        v = [x.strip() for x in out.stdout.splitlines()[0].split(",")]
        return {"ok": True, "name": v[0], "util_pct": float(v[1]), "mem_used_mb": float(v[2]),
                "mem_total_mb": float(v[3]), "temp_c": float(v[4]), "power_w": v[5]}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def system_stats(path: Path) -> dict:
    vm = psutil.virtual_memory()
    return {"ram_free_gb": round(vm.available / 2**30, 1), "ram_pct": vm.percent,
            "cpu_pct": psutil.cpu_percent(interval=0.5),
            "disk_free_gb": round(shutil.disk_usage(path).free / 2**30, 1)}


def checkpoint_ok(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "ok": False}
    st = path.stat()
    res = {"exists": True, "size_mb": round(st.st_size / 2**20, 2), "age_s": round(time.time() - st.st_mtime)}
    try:
        with zipfile.ZipFile(path) as z:
            res["ok"] = z.testzip() is None
    except (zipfile.BadZipFile, OSError) as e:
        res.update(ok=False, error=repr(e))
    return res


def log_tail_errors(log: Path, n_bytes=20000) -> list[str]:
    """Known failure signatures in the end of a training log."""
    if not log.exists():
        return []
    with open(log, "rb") as f:
        f.seek(max(0, log.stat().st_size - n_bytes))
        tail = f.read().decode("utf-8", "replace")
    sigs = ["CUDA out of memory", "OutOfMemoryError", "CUDA error", "RuntimeError", "DataLoader worker",
            "Traceback (most recent call last)", "paging file", "MemoryError"]
    return [s for s in sigs if s in tail]


def results_summary(exp_dir: Path) -> dict:
    p = exp_dir / "results.csv"
    if not p.exists():
        return {}
    try:
        with open(p, newline="") as f:
            rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f)]
    except (OSError, ValueError):
        return {}
    if not rows:
        return {}
    key = "metrics/mAP50-95(B)"
    vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
    finite = all(math.isfinite(v) for v in vals)
    return {"epochs_logged": len(rows), "last": rows[-1].get(key), "best_mAP50_95": round(max(vals), 5) if vals else None,
            "best_mAP50": round(max(float(r["metrics/mAP50(B)"]) for r in rows), 5), "metrics_finite": finite,
            "regression": bool(len(vals) > 10 and vals[-1] < 0.6 * max(vals))}
