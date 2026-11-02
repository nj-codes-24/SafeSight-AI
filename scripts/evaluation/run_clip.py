"""Run the full pipeline over demo clips and report tracking stability and incidents. Uses a throwaway DB."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from database.database import IncidentDB  # noqa: E402
from inference.tracker import load_config, process_video  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--weights", default=str(ROOT / "models" / "best.pt"))
ap.add_argument("--clips", nargs="*")
ap.add_argument("--out", default=str(ROOT / "reports" / "demo_runs"))
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
cfg = load_config()
clips = a.clips or [c["file"] for c in json.loads((ROOT / "data/demo/demo_clips.json").read_text(encoding="utf-8"))]
all_res = {}
for c in clips:
    stem = Path(c).stem
    with tempfile.TemporaryDirectory() as td:
        db = IncidentDB(Path(td) / "x.db")
        r = process_video(ROOT / "data" / "demo" / c, a.weights, out / f"{stem}_annotated.mp4", cfg, camera_id=stem, db=db)
        r["incident_list"] = [{k: i[k] for k in ("incident_type", "worker_id", "zone", "video_time_s", "confidence")} for i in db.rows()]
        r["final_states"] = db.sessions()[-1]
        db.conn.close()
    all_res[stem] = r
    print(stem, json.dumps({k: r[k] for k in ("frames", "track_ids", "confirmed_tracks", "avg_fps", "incidents")}), r["incident_list"], flush=True)
(out / "summary.json").write_text(json.dumps(all_res, indent=1))
