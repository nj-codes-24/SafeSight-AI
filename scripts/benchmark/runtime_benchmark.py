"""Multi-camera benchmark of the headless runtime, with the real M5 model on the demo clips.

Each configuration runs in its own process (clean GPU memory and CUDA state): N cameras replay demo clips in a loop,
either as fast as possible with every frame processed ("throughput", offline files) or paced at their own frame rate
with max_fps analysis ("live", simulating cameras with frame dropping). Rates are measured over a window after a
warm-up, from the runtime's own counters. GPU utilisation and clocks come from nvidia-smi samples.

These are video files on one workstation: a simulation of concurrent cameras, not a test of RTSP or of a site.

    python scripts/benchmark/runtime_benchmark.py                       full matrix -> reports/runtime/multicamera_benchmark.json
    python scripts/benchmark/runtime_benchmark.py --quick                1 and 2 cameras, batched only
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_OFFLINE", "true")
CLIPS = ["track_work_day", "roadworks_night", "ballast_train", "helmet_put_on"]
OUT = ROOT / "reports" / "runtime" / "multicamera_benchmark.json"


def gpu_sampler(samples, stop):
    q = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,clocks.sm", "--format=csv,noheader,nounits"]
    while not stop.is_set():
        try:
            u, m, c = (float(x) for x in subprocess.run(q, capture_output=True, text=True, timeout=3).stdout.split(","))
            samples.append((u, m, c))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        stop.wait(1.0)


def one(backend, n, mode, warmup, window, max_fps=15):
    """Run one configuration in this process; print one JSON line."""
    import psutil
    import torch

    from runtime import config as rconfig
    from runtime.service import Runtime

    tmp = Path(tempfile.mkdtemp(prefix="ssbench_"))
    app_zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    live = mode == "live"
    cams = []
    for i in range(n):
        clip = CLIPS[i % len(CLIPS)]
        path = clip if "/" in clip else f"data/demo/{clip}.mp4"
        clip = Path(clip).stem
        c = {"id": f"cam{i + 1}", "source": {"type": "file", "path": path, "loop": True, "realtime": live},
             "processing": {"max_fps": max_fps if live else None, "queue_size": 2 if live else 4}}
        if clip in app_zones:
            c["zones_from_app"] = clip
        cams.append(c)
    cfg = rconfig.parse({"runtime": {"database": str(tmp / "b.db"), "evidence_dir": str(tmp / "ev"),
                                     "status_file": str(tmp / "status.json"), "log_file": None, "status_interval_s": 1},
                         "inference": {"backend": backend}, "cameras": cams}, app_zones)
    proc = psutil.Process()
    t_load = time.perf_counter()
    rt = Runtime(cfg)
    rt.start()
    load_s = time.perf_counter() - t_load
    time.sleep(warmup)
    torch.cuda.reset_peak_memory_stats()
    a = {cid: w.health.snapshot() for cid, w in rt.workers.items()}
    samples, stop = [], threading.Event()
    th = threading.Thread(target=gpu_sampler, args=(samples, stop), daemon=True)
    th.start()
    proc.cpu_percent(None)
    rss, t0 = [], time.monotonic()
    while time.monotonic() - t0 < window:
        time.sleep(1)
        rss.append(proc.memory_info().rss / 2**20)
    cpu = proc.cpu_percent(None)
    el = time.monotonic() - t0
    b = {cid: w.health.snapshot() for cid, w in rt.workers.items()}
    states = {cid: s["state"] for cid, s in b.items()}
    stop.set()
    gpu_peak = torch.cuda.max_memory_allocated() / 2**20
    backend_stats = rt.backend.stats()
    rt.stop()
    per = {}
    for cid in b:
        fa, fb = a[cid]["frames"], b[cid]["frames"]
        proc_n = fb["processed"] - fa["processed"]
        drop_n = fb["dropped_backpressure"] - fa["dropped_backpressure"]
        lat = b[cid]["latency_ms"]
        per[cid] = {"processed_fps": round(proc_n / el, 2), "source_fps": b[cid]["source_fps"], "target_fps": b[cid]["target_fps"],
                    "drop_ratio": round(drop_n / (proc_n + drop_n), 4) if proc_n + drop_n else 0.0,
                    "inference_ms_p50": lat["inference_p50"], "inference_ms_p95": lat["inference_p95"],
                    "end_to_end_ms_p50": lat["end_to_end_p50"], "end_to_end_ms_p95": lat["end_to_end_p95"],
                    "incident_latency_ms_max": lat["incident_max"], "state": states[cid]}
    print(json.dumps({
        "backend": backend, "cameras": n, "mode": mode, "max_fps": max_fps if live else None,
        "window_s": round(el, 1), "startup_s": round(load_s, 1),
        "aggregate_fps": round(sum(p["processed_fps"] for p in per.values()), 1), "per_camera": per,
        "process_cpu_pct": round(cpu, 1), "rss_mb_max": round(max(rss), 1),
        "torch_cuda_peak_mb": round(gpu_peak, 1), "model": backend_stats,
        "gpu_util_pct_mean": round(statistics.mean(s[0] for s in samples), 1) if samples else None,
        "gpu_mem_used_mb_max": max((s[1] for s in samples), default=None),
        "gpu_sm_clock_mhz_mean": round(statistics.mean(s[2] for s in samples)) if samples else None,
        "all_streaming": set(states.values()) <= {"STREAMING"},
    }), flush=True)


def baseline():
    """The original single-camera path (process_video), three runs on the first clip, every frame."""
    import inference.incident_manager as im
    from database.database import IncidentDB
    from inference.tracker import load_config, process_video

    tmp = Path(tempfile.mkdtemp(prefix="ssbench_base_"))
    im.EVIDENCE_DIR = tmp / "ev"
    runs = []
    for i in range(3):
        db = IncidentDB(tmp / f"b{i}.db")
        r = process_video(ROOT / "data" / "demo" / f"{CLIPS[0]}.mp4", cfg=load_config(), camera_id=CLIPS[0], db=db)
        runs.append(r["avg_fps"])
        db.close()
    print(json.dumps({"baseline_process_video_fps": runs, "clip": CLIPS[0]}), flush=True)


def child(*args):
    r = subprocess.run([sys.executable, str(Path(__file__)), *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    line = [x for x in r.stdout.splitlines() if x.startswith("{")]
    if r.returncode or not line:
        return {"error": (r.stderr or r.stdout)[-2000:], "args": list(map(str, args))}
    return json.loads(line[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", nargs=4, metavar=("BACKEND", "N", "MODE", "MAX_FPS"))
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--warmup", type=float, default=6)
    ap.add_argument("--window", type=float, default=20)
    ap.add_argument("--clips", help="comma-separated video paths to use instead of the four demo clips")
    ap.add_argument("--out", help="result file (default reports/runtime/multicamera_benchmark.json)")
    ap.add_argument("--batched-only", action="store_true", help="batched backend only (1, 2, 4, 8 cameras)")
    a = ap.parse_args()
    global CLIPS, OUT
    if a.clips:
        CLIPS = a.clips.split(",")
    if a.out:
        OUT = ROOT / a.out
    if a.one:
        return one(a.one[0], int(a.one[1]), a.one[2], a.warmup, a.window, float(a.one[3]))
    if a.baseline:
        return baseline()
    import torch

    matrix = [("batched", n, "throughput", 15) for n in (1, 2)] if a.quick else \
        [(b, n, "throughput", 15) for b in ("shared", "batched", "per_camera") for n in (1, 2, 4)] + \
        [("batched", 8, "throughput", 15)] + [(b, n, "live", 15) for b in ("shared", "batched") for n in (1, 2, 4)] + \
        [("batched", 8, "live", 15), ("batched", 8, "live", 10)]
    results = {"date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "machine": {"gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                           "cpu": platform.processor(), "python": platform.python_version(), "torch": torch.__version__},
               "method": __doc__.strip().splitlines()[0:6], "clips": CLIPS,
               "baseline": child("--baseline") if not a.clips else "not run with --clips: the single-camera "
               "process_video reference is in reports/runtime/multicamera_benchmark.json", "runs": []}
    if a.batched_only:
        matrix = [("batched", n, m, 15) for m in ("throughput", "live") for n in (1, 2, 4, 8)] + [("batched", 8, "live", 10)]
    for backend, n, mode, fps in matrix:
        r = child("--one", backend, n, mode, fps, "--warmup", a.warmup, "--window", a.window,
                  *(["--clips", ",".join(CLIPS)] if a.clips else []))
        results["runs"].append(r)
        if "error" in r:
            print(f"{backend:<10} {n} {mode:<10} ERROR {r['error'][-300:]}", flush=True)
        else:
            print(f"{backend:<10} {n} {mode:<10} {fps if mode == 'live' else '':>4} aggregate {r['aggregate_fps']:>6} FPS  per camera "
                  f"{[p['processed_fps'] for p in r['per_camera'].values()]}  drop "
                  f"{[p['drop_ratio'] for p in r['per_camera'].values()]}  RSS {r['rss_mb_max']} MB  "
                  f"CUDA {r['torch_cuda_peak_mb']} MB  GPU {r['gpu_util_pct_mean']} % @ {r['gpu_sm_clock_mhz_mean']} MHz", flush=True)
    if not a.quick:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"written {OUT}")


if __name__ == "__main__":
    main()
