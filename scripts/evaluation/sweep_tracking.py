"""Sweep ByteTrack settings and stitching over cached detections. Saves stitch crops for a wrong-merge review."""
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from inference.detector import LOW_CONF, TRACKER_CFG, Detector  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "evaluation"))
from stitcher_experiment import TrackStitcher  # noqa: E402
from ultralytics.trackers.byte_tracker import BYTETracker  # noqa: E402
from ultralytics.utils import YAML, IterableSimpleNamespace  # noqa: E402

GRID = dict(track_buffer=[60, 120], match_thresh=[0.8, 0.9], new_track_thresh=[0.45, 0.6], stitch=[False, True])
OUT = ROOT / "reports" / "tracking_sweep"
OUT.mkdir(parents=True, exist_ok=True)
det = Detector()
clips = [c for c in json.loads((ROOT / "data/demo/demo_clips.json").read_text(encoding="utf-8"))]
cache = {}
for c in clips:
    cap = cv2.VideoCapture(str(ROOT / "data/demo" / c["file"]))
    rows = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        b = det.model.predict(f, conf=LOW_CONF, imgsz=640, device=0, verbose=False)[0].boxes.cpu().numpy()
        rows.append(b[b.cls.astype(int) == det.person_id])
    cap.release()
    cache[c["file"]] = (rows, c["fps"])


def run(rows, fps, p):
    a = {**YAML.load(TRACKER_CFG), **{k: v for k, v in p.items() if k != "stitch"}, "track_high_thresh": 0.35}
    tr = BYTETracker(IterableSimpleNamespace(**a))
    st = TrackStitcher() if p["stitch"] else None
    life, boxes = Counter(), []
    dummy = np.zeros((720, 1280, 3), np.uint8)
    for i, b in enumerate(rows):
        t = tr.update(b, dummy)
        ps = [(int(x[4]), np.asarray(x[:4]), float(x[5])) for x in t]
        if st:
            ps = st.update(i, ps)
        for w, *_ in ps:
            life[w] += 1
        boxes.append(ps)
    return dict(ids=len(life), confirmed_1s=sum(v >= fps for v in life.values()), track_frames=sum(life.values())), st, boxes


rows_out = []
for vals in itertools.product(*GRID.values()):
    p = dict(zip(GRID, vals))
    m = {k: run(*cache[k], p)[0] for k in cache}
    tot = {x: sum(m[k][x] for k in m) for x in ("ids", "confirmed_1s", "track_frames")}
    rows_out.append({**p, **tot, "per_clip": {k: (m[k]["ids"], m[k]["confirmed_1s"]) for k in m}})
    print(p, tot, {k.split("_")[0]: rows_out[-1]["per_clip"][k] for k in m}, flush=True)
(OUT / "sweep.json").write_text(json.dumps(rows_out, indent=1))

# review every stitch at the default tracker settings: the box before the break beside the box after it
p = dict(track_buffer=60, match_thresh=0.8, new_track_thresh=0.45, stitch=True)
cells = []
for k, (rows, fps) in cache.items():
    _, st, boxes = run(rows, fps, p)
    cap = cv2.VideoCapture(str(ROOT / "data/demo" / k))
    print(k, "stitches", len(st.merges))
    for mg in st.merges:
        after = next(b for w, b, _ in boxes[mg["frame"]] if w == mg["worker"])
        before_f = next(i for i in range(mg["frame"] - 1, -1, -1) if any(w == mg["worker"] for w, *_ in boxes[i]))
        before = next(b for w, b, _ in boxes[before_f] if w == mg["worker"])
        pair = []
        for fr, b in ((before_f, before), (mg["frame"], after)):
            cap.set(1, fr)
            _, im = cap.read()
            x1, y1, x2, y2 = np.clip(b.astype(int), 0, None)
            pair.append(cv2.resize(im[y1:y2, x1:x2], (110, 200)))
        cell = np.hstack(pair)
        cv2.putText(cell, f"{k[:5]} {before_f}>{mg['frame']}", (2, 195), 0, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cells.append(cv2.copyMakeBorder(cell, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    cap.release()
while cells and len(cells) % 5:
    cells.append(np.zeros_like(cells[0]))
if cells:
    cv2.imwrite(str(OUT / "stitch_review.jpg"), np.vstack([np.hstack(cells[i:i + 5]) for i in range(0, len(cells), 5)]))
