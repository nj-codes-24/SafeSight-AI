import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import cv2

from database.database import IncidentDB
from inference.detector import Detector
from inference.tracker import Pipeline, load_config, process_video

cfg = load_config(); print({k: cfg[k] for k in ("person_conf", "ppe_conf", "no_helmet_conf")})
# helmet transition timeline, in a throwaway DB
det = Detector(); db = IncidentDB(":memory:"); cap = cv2.VideoCapture("data/demo/helmet_put_on.mp4"); fps = cap.get(5)
p = Pipeline(det, fps, cfg, "helmet_put_on", db=db); prev = None; events = []; i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    p.process(f); st = dict(p.stats.tracked).get(1)
    if st != prev: events.append((round(i / fps, 2), st)); prev = st
    i += 1
print("transitions", events, "incident closed", [(r["incident_type"], r["status"]) for r in db.rows()])
real = IncidentDB()
for c in json.loads(Path("data/demo/demo_clips.json").read_text(encoding="utf-8")):
    s = Path(c["file"]).stem
    r = process_video(Path("data/demo") / c["file"], cfg=cfg, camera_id=s, db=real)
    print(s, r["track_ids"], r["confirmed_tracks"], r["incidents"], r["avg_fps"])
rows = real.rows(); print(len(rows), [r["status"] for r in rows].count("CLOSED"), all(Path(r["evidence_path"]).exists() for r in rows), real.to_csv().count("\n"))
print([(r["incident_type"], r["camera_id"], r["worker_id"], r["zone"]) for r in rows])
ss = real.sessions(); print(sum(x["unique_workers"] for x in ss), sum(x["compliant"] for x in ss), sum(x["violation"] for x in ss), sum(x["uncertain"] for x in ss))