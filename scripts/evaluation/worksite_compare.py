"""Full pipeline over the worksite clips for several model and threshold settings; throwaway DBs. True NO_HELMET incidents
by eye: 1 roadworks_night (passer-by), 1 helmet_put_on, 2 framing_bare_head, 0 others."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from database.database import IncidentDB
from inference.tracker import load_config, process_video

M = {"m2": "models/candidates/m2_fallback.pt", "m5": "runs/m5_sh17_ft/checkpoints/best_good.pt", "m4": "runs/m4_harmonised_ft/checkpoints/best_good.pt"}
SET = [("m2", .3), ("m5", .3), ("m5", .4), ("m5", .5), ("m5", .6), ("m4", .4)]
EXPECT = {"roadworks_night": 1, "helmet_put_on": 1, "framing_bare_head": 2, "track_work_day": 0, "ballast_train": 0}
res = {}
for m, nc in SET:
    cfg = {**load_config(), "no_helmet_conf": nc}; row = {}
    for stem in EXPECT:
        with tempfile.TemporaryDirectory() as td:
            db = IncidentDB(Path(td) / "x.db")
            r = process_video(f"data/demo/{stem}.mp4", M[m], None, cfg, camera_id=stem, db=db)
            rows = db.rows()
            row[stem] = dict(no_helmet=[(i["worker_id"], i["video_time_s"], i["confidence"]) for i in rows if i["incident_type"] == "NO_HELMET"],
                             zone=sum(i["incident_type"] != "NO_HELMET" for i in rows), ids=r["track_ids"], confirmed=r["confirmed_tracks"], final=db.sessions()[-1]["uncertain"], fps=r["avg_fps"])
            db.conn.close()
    res[f"{m}@{nc}"] = row
    print(m, nc, {k[:6]: (len(v["no_helmet"]), v["zone"], v["confirmed"], v["final"]) for k, v in row.items()}, flush=True)
json.dump(res, open("reports/worksite_compare.json", "w"), indent=1)