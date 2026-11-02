"""Run M2, M3 and M5 through the full pipeline on unseen footage at thresholds fixed from validation (reports/pr_curves.json).

Frame-level errors use clip-level ground truth (reports/unseen_gt/ground_truth.json): on helmet-only clips every no_helmet
detection is false; on clips where nobody wears a hard hat every helmet detection is false. Incident evidence is kept for
judging by eye.
"""
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402

import inference.incident_manager as im  # noqa: E402
from database.database import IncidentDB  # noqa: E402
from inference.detector import Detector  # noqa: E402
from inference.tracker import Pipeline, load_config  # noqa: E402

MODELS = {"m2": "models/candidates/m2_fallback.pt", "m3": "runs/m3_shwd_y26n/checkpoints/best_good.pt",
          "m5": "runs/m5_sh17_ft/checkpoints/best_good.pt", "m5_at_0.6": "runs/m5_sh17_ft/checkpoints/best_good.pt"}
CLIPS = ["c00.webm", "c01.webm", "c02.webm", "c03.ogv", "c09.ogv", "c10.ogv", "c12.ogv", "c07.webm", "c08.webm", "c11.ogv"]
HELMET_ONLY, NO_HARD_HATS = {"c02.webm", "c03.ogv"}, {"c09.ogv", "c10.ogv"}
MAX_FRAMES = 1500
OUT = ROOT / "reports" / "unseen_compare"


def main():
    thresholds = {k: v["threshold"]["value"] for k, v in json.loads((ROOT / "reports" / "pr_curves.json").read_text()).items()}
    thresholds["m5_at_0.6"] = 0.6  # the setting already in the app, fixed before this footage was run
    res = {}
    for name, w in MODELS.items():
        det = Detector(ROOT / w)
        cfg = {**load_config(), "no_helmet_conf": thresholds[name], "zones": {}}
        im.EVIDENCE_DIR = OUT / name
        res[name] = {"no_helmet_conf": thresholds[name]}
        for clip in CLIPS:
            torch.cuda.reset_peak_memory_stats()
            cap = cv2.VideoCapture(str(ROOT / "data/demo/candidates" / clip))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            db = IncidentDB(":memory:")
            p = Pipeline(det, fps, cfg, clip, db=db)
            heads = {"helmet": 0, "no_helmet": 0}
            orig = det.track

            def counted(*a, **k):
                persons, hs = orig(*a, **k)
                for h in hs:
                    heads[h.cls] += 1
                return persons, hs
            det.track = counted
            n, t0 = 0, time.perf_counter()
            while n < MAX_FRAMES:
                ok, f = cap.read()
                if not ok:
                    break
                p.process(f)
                n += 1
            wall = time.perf_counter() - t0
            det.track = orig
            p.finish(clip)
            rows = [r for r in db.rows() if r["incident_type"] == "NO_HELMET"]
            s = db.sessions()[-1]
            res[name][clip] = {
                "frames": n, "fps": round(n / wall, 1), "gpu_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20),
                "no_helmet_incidents": len(rows), "evidence": [r["evidence_path"] for r in rows],
                "track_ids": len(p.stats.seen_ids), "confirmed_tracks": len(p.stats.confirmed()),
                "short_ids": len(p.stats.seen_ids) - len(p.stats.confirmed()),
                "final_compliant": s["compliant"], "final_violation": s["violation"], "final_uncertain": s["uncertain"],
                "helmet_dets": heads["helmet"], "no_helmet_dets": heads["no_helmet"],
                "false_no_helmet_dets_per_100_frames": round(100 * heads["no_helmet"] / n, 1) if clip in HELMET_ONLY else None,
                "false_helmet_dets_per_100_frames": round(100 * heads["helmet"] / n, 1) if clip in NO_HARD_HATS else None}
            print(name, clip, {k: v for k, v in res[name][clip].items() if k != "evidence"}, flush=True)
            cap.release()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
