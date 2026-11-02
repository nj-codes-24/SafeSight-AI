"""Holdout worksite check: footage not used for any tuning. Evidence screenshots are kept for review by eye."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import inference.incident_manager as im
from database.database import IncidentDB
from inference.tracker import load_config, process_video

C = [("c00.webm"), ("c01.webm"), ("c02.webm"), ("c03.ogv"), ("c07.webm"), ("c08.webm"), ("c09.ogv"), ("c10.ogv"), ("c11.ogv"), ("c12.ogv")]
RUNS = {"m2": ("models/candidates/m2_fallback.pt", .3), "m5": ("runs/m5_sh17_ft/checkpoints/best_good.pt", .6)}
OUT = Path("reports/holdout_worksite"); res = {}
for n, (w, nc) in RUNS.items():
    im.EVIDENCE_DIR = OUT / n
    for c in C:
        d = OUT / n; d.mkdir(parents=True, exist_ok=True)
        db = IncidentDB(d / f"{c}.db")
        r = process_video(f"data/demo/candidates/{c}", w, None, {**load_config(), "no_helmet_conf": nc, "zones": {}}, camera_id=c, db=db, max_frames=1500)
        rows = [x for x in db.rows() if x["incident_type"] == "NO_HELMET"]
        s = db.sessions()[-1]
        res[f"{n}/{c}"] = dict(frames=r["frames"], no_helmet=len(rows), evidence=[x["evidence_path"] for x in rows], confirmed=r["confirmed_tracks"], compliant=s["compliant"], violation=s["violation"], uncertain=s["uncertain"], fps=r["avg_fps"])
        print(n, c, {k: v for k, v in res[f"{n}/{c}"].items() if k != "evidence"}, flush=True)
        db.conn.close()
json.dump(res, open(OUT / "summary.json", "w"), indent=1)