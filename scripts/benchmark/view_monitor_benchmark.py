"""Overhead of camera view monitoring in the headless runtime: the same configuration with view monitoring off and on.

Each run is its own process (clean GPU state): N cameras replay demo clips in a loop with the real M5 model on the
batched backend, either paced at the clip's frame rate with max_fps analysis ("live") or as fast as possible with every
frame processed ("throughput"). Rates come from the runtime's own counters over a window after a warm-up.

Every camera replays framing_bare_head, the only demo clip from a fixed camera (with real workers), at the default
thresholds: the other clips are hand-held and genuinely change view, so view monitoring would suspend their inference
and the "on" arm would do less work. Suspended frames are reported (expected 0): this measures cost, not detection.
Video files on one workstation simulate cameras.

    python scripts/benchmark/view_monitor_benchmark.py            -> reports/runtime/view_monitor_benchmark.json
    python scripts/benchmark/view_monitor_benchmark.py --micro    per-check cost by frame size only
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_OFFLINE", "true")
CLIPS = ["framing_bare_head"]
OUT = ROOT / "reports" / "runtime" / "view_monitor_benchmark.json"


def one(n, mode, view, warmup, window, max_fps=15):
    import psutil

    from runtime import config as rconfig
    from runtime.service import Runtime

    tmp = Path(tempfile.mkdtemp(prefix="ssviewbench_"))
    app_zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    live = mode == "live"
    cams = []
    for i in range(n):
        clip = CLIPS[i % len(CLIPS)]
        c = {"id": f"cam{i + 1}", "source": {"type": "file", "path": f"data/demo/{clip}.mp4", "loop": True, "realtime": live},
             "processing": {"max_fps": max_fps if live else None, "queue_size": 2 if live else 4},
             "view_monitor": {"enabled": view}}
        if clip in app_zones:
            c["zones_from_app"] = clip
        cams.append(c)
    cfg = rconfig.parse({"runtime": {"database": str(tmp / "b.db"), "evidence_dir": str(tmp / "ev"),
                                     "status_file": str(tmp / "status.json"), "log_file": None, "status_interval_s": 1},
                         "inference": {"backend": "batched"}, "cameras": cams}, app_zones)
    proc = psutil.Process()
    rt = Runtime(cfg)
    rt.start()
    time.sleep(warmup)
    a = {cid: w.health.snapshot() for cid, w in rt.workers.items()}
    calls0 = rt.backend.stats()["calls"]
    proc.cpu_percent(None)
    gpu, rss, states, t0 = [], [], [], time.monotonic()
    while time.monotonic() - t0 < window:
        time.sleep(1)
        rss.append(proc.memory_info().rss / 2**20)
        states.append({cid: (w.health.snapshot().get("view") or {}).get("state", "DISABLED") for cid, w in rt.workers.items()})
        g = _gpu()
        if g:
            gpu.append(g)
    cpu = proc.cpu_percent(None)
    el = time.monotonic() - t0
    b = {cid: w.health.snapshot() for cid, w in rt.workers.items()}
    inferred = rt.backend.stats()["calls"] - calls0
    rt.stop()
    per = {}
    for cid in b:
        fa, fb = a[cid]["frames"], b[cid]["frames"]
        lat = b[cid]["latency_ms"]
        per[cid] = {"processed_fps": round((fb["processed"] - fa["processed"]) / el, 2),
                    "read": fb["read"] - fa["read"], "dropped": fb["dropped_backpressure"] - fa["dropped_backpressure"],
                    "view_suspended": fb["view_suspended"] - fa["view_suspended"],
                    "processing_ms_p50": lat["processing_p50"], "processing_ms_p95": lat["processing_p95"],
                    "inference_ms_p50": lat["inference_p50"],
                    "end_to_end_ms_p50": lat["end_to_end_p50"], "end_to_end_ms_p95": lat["end_to_end_p95"],
                    "view_check_ms_p50": lat["view_check_p50"], "view_check_ms_p95": lat["view_check_p95"],
                    "view_states_seen": sorted({s[cid] for s in states})}
    seen = {x for p in per.values() for x in p["view_states_seen"]}
    suspended = sum(p["view_suspended"] for p in per.values())
    # clean: with monitoring on, every camera was VIEW_STABLE at every sample and no frame was withheld from inference
    clean = suspended == 0 and (seen == {"VIEW_STABLE"} if view else seen == {"DISABLED"})
    print(json.dumps({"cameras": n, "mode": mode, "view_monitor": view, "max_fps": max_fps if live else None,
                      "window_s": round(el, 1), "clean": clean, "view_states_seen": sorted(seen),
                      "view_suspended_frames": suspended, "inferred_frames": inferred,
                      "inferred_fps": round(inferred / el, 1),
                      "aggregate_fps": round(sum(p["processed_fps"] for p in per.values()), 1),
                      "dropped_frames": sum(p["dropped"] for p in per.values()),
                      "process_cpu_pct": round(cpu, 1), "rss_mb_max": round(max(rss), 1),
                      "e2e_ms_p50_mean": _mean(per, "end_to_end_ms_p50"), "e2e_ms_p95_mean": _mean(per, "end_to_end_ms_p95"),
                      "processing_ms_p50_mean": _mean(per, "processing_ms_p50"),
                      "view_check_ms_p50_mean": _mean(per, "view_check_ms_p50"),
                      "view_check_ms_p95_max": max((p["view_check_ms_p95"] or 0 for p in per.values()), default=None),
                      "gpu_util_pct_mean": round(statistics.mean(g[0] for g in gpu), 1) if gpu else None,
                      "gpu_sm_clock_mhz_mean": round(statistics.mean(g[1] for g in gpu)) if gpu else None,
                      "gpu_sm_clock_mhz_min": min((g[1] for g in gpu), default=None),
                      "gpu_sm_clock_mhz_max": max((g[1] for g in gpu), default=None),
                      "per_camera": per}), flush=True)


def _gpu():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,clocks.sm", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3).stdout.strip().splitlines()[0]
        return tuple(float(x) for x in out.split(","))
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _mean(per, k):
    v = [p[k] for p in per.values() if p[k] is not None]
    return round(statistics.mean(v), 2) if v else None


def micro():
    """Cost of one check by frame size, on a real frame, single thread of the caller (no runtime)."""
    import cv2

    from inference.view_monitor import ViewMonitor

    cap = cv2.VideoCapture(str(ROOT / "data" / "demo" / "framing_bare_head.mp4"))
    frames = [cap.read()[1] for _ in range(60)]
    out = {}
    for w, h in ((640, 360), (1280, 720), (1920, 1080), (3840, 2160)):
        fs = [cv2.resize(f, (w, h)) for f in frames]
        m = ViewMonitor()
        for i in range(10):  # warm up and establish the reference
            m.observe(fs[i], i * 0.5)
        ts = []
        for i in range(10, 60):
            t0 = time.perf_counter()
            m.observe(fs[i], i * 0.5)
            ts.append(1000 * (time.perf_counter() - t0))
        ts.sort()
        out[f"{w}x{h}"] = {"p50_ms": round(ts[len(ts) // 2], 2), "p95_ms": round(ts[int(0.95 * (len(ts) - 1))], 2),
                           "state": m.state}
    return out


def child(*args):
    r = subprocess.run([sys.executable, str(Path(__file__)), *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    line = [x for x in r.stdout.splitlines() if x.startswith("{")]
    if r.returncode or not line:
        return {"error": (r.stderr or r.stdout)[-2000:], "args": list(map(str, args))}
    return json.loads(line[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", nargs=3, metavar=("N", "MODE", "VIEW"))
    ap.add_argument("--micro", action="store_true")
    ap.add_argument("--warmup", type=float, default=8)
    ap.add_argument("--window", type=float, default=20)
    ap.add_argument("--repeats", type=int, default=2, help="paired repetitions of every configuration")
    ap.add_argument("--retries", type=int, default=2, help="re-runs of a run that was not clean before giving up")
    a = ap.parse_args()
    if a.one:
        return one(int(a.one[0]), a.one[1], a.one[2] == "on", a.warmup, a.window)
    if a.micro:
        print(json.dumps(micro(), indent=1))
        return
    import cv2
    import torch

    results = {"date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "machine": {"gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                           "cpu": platform.processor(), "cpu_count": os.cpu_count(), "python": platform.python_version(),
                           "opencv": cv2.__version__},
               "method": __doc__.strip().splitlines()[:10], "clips": CLIPS, "warmup_s": a.warmup, "window_s": a.window,
               "micro_check_cost": micro(), "runs": [], "rejected_runs": []}
    for rep in range(a.repeats):
        for mode in ("live", "throughput"):
            for n in (1, 4, 8):
                for view in ("off", "on"):  # paired: off then on, back to back, same inputs and settings
                    for attempt in range(a.retries + 1):
                        r = child("--one", n, mode, view, "--warmup", a.warmup, "--window", a.window)
                        r.update(repeat=rep, attempt=attempt)
                        if r.get("clean"):
                            break
                        results["rejected_runs"].append(r)  # kept for the record, never in the comparison
                    results["runs"].append(r)
                    print(json.dumps({k: r.get(k) for k in ("repeat", "cameras", "mode", "view_monitor", "clean", "attempt",
                                                             "inferred_fps", "aggregate_fps", "process_cpu_pct",
                                                             "e2e_ms_p50_mean", "view_check_ms_p50_mean",
                                                             "gpu_sm_clock_mhz_mean", "error")}), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
