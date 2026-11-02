"""Measure the frozen M5 pipeline on the five demo clips, now, on this machine. No training, no UI.

Each clip runs 3 times through the same Pipeline the app uses, with the app's config (no_helmet_conf 0.60) and an
in-memory database, so the real incident database is untouched. Records full-pipeline FPS, detector+tracker
latency, raw model inference latency, peak GPU memory, tracks and incidents, and whether repeats agree.
"""
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import inference.incident_manager as im  # noqa: E402
from database.database import IncidentDB  # noqa: E402
from inference.detector import Detector  # noqa: E402
from inference.tracker import Pipeline, load_config  # noqa: E402

CLIPS = ["helmet_put_on.mp4", "roadworks_night.mp4", "track_work_day.mp4", "ballast_train.mp4", "framing_bare_head.mp4"]
REPEATS = 3


def main():
    cfg = load_config()
    im.EVIDENCE_DIR = ROOT / ".qa" / "perf_evidence"
    torch.cuda.reset_peak_memory_stats()
    det = Detector()
    out = {"weights": str(det.model.ckpt_path if hasattr(det.model, "ckpt_path") else "models/best.pt"),
           "no_helmet_conf": cfg.get("no_helmet_conf"), "person_conf": cfg["person_conf"], "ppe_conf": cfg["ppe_conf"],
           "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "clips": {}}
    # warm-up so the first clip is not charged for CUDA initialisation
    cap = cv2.VideoCapture(str(ROOT / "data/demo" / CLIPS[0]))
    ok, f = cap.read()
    for _ in range(10):
        det.model.predict(f, imgsz=640, verbose=False)
    cap.release()
    for clip in CLIPS:
        runs = []
        for rep in range(REPEATS):
            cap = cv2.VideoCapture(str(ROOT / "data/demo" / clip))
            fps_src = cap.get(cv2.CAP_PROP_FPS) or 25
            frames = []
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                frames.append(f)
            cap.release()
            db = IncidentDB(":memory:")
            p = Pipeline(det, fps_src, {**cfg}, Path(clip).stem, db=db)
            track_ms, infer_ms = [], []
            orig = det.track

            def timed(*a, **k):
                t = time.perf_counter()
                r = orig(*a, **k)
                torch.cuda.synchronize()
                track_ms.append(1000 * (time.perf_counter() - t))
                return r
            det.track = timed
            t0 = time.perf_counter()
            for f in frames:
                p.process(f)
            wall = time.perf_counter() - t0
            det.track = orig
            p.finish(clip)
            # raw model latency on every 5th frame (preprocess + inference + NMS), separate from tracking
            for f in frames[::5]:
                r = det.model.predict(f, imgsz=640, verbose=False)[0]
                infer_ms.append(sum(r.speed.values()))
            s = db.sessions()[-1]
            rows = db.rows()
            runs.append({"frames": len(frames), "pipeline_fps": round(len(frames) / wall, 1),
                         "detect_track_ms_median": round(statistics.median(track_ms), 2),
                         "detect_track_ms_p95": round(sorted(track_ms)[int(0.95 * len(track_ms))], 2),
                         "model_ms_median": round(statistics.median(infer_ms), 2),
                         "track_ids": len(p.stats.seen_ids), "confirmed_tracks": len(p.stats.confirmed()),
                         "max_in_frame": None,
                         "final": {"compliant": s["compliant"], "violation": s["violation"], "uncertain": s["uncertain"]},
                         "incidents": sorted((r["incident_type"], r["worker_id"], r["video_time_s"]) for r in rows)})
        same = all(r["incidents"] == runs[0]["incidents"] and r["final"] == runs[0]["final"] for r in runs)
        out["clips"][clip] = {"runs": runs, "repeats_identical": same}
        print(clip, [(r["pipeline_fps"], r["detect_track_ms_median"], r["model_ms_median"], len(r["incidents"])) for r in runs],
              "identical" if same else "DIFFERENT", flush=True)
    out["gpu_peak_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20)
    out["gpu_peak_reserved_mb"] = round(torch.cuda.max_memory_reserved() / 2**20)
    (ROOT / "reports" / "runtime").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "runtime" / "performance.json").write_text(json.dumps(out, indent=1))
    print("peak GPU allocated MB", out["gpu_peak_allocated_mb"], "reserved MB", out["gpu_peak_reserved_mb"])


if __name__ == "__main__":
    main()
