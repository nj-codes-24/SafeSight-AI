"""Check whether the two sources draw head boxes differently, and how much of the error is box geometry. Validation only."""
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO

sys.path.insert(0, str(ROOT / "training"))
from diagnose import NAMES, VAL, iou, load_gt

weights = sys.argv[1:] or ["b0=runs/b0_cppe_y26n/checkpoints/best_good.pt", "m2=models/best.pt"]
out = {}
geo = {}
for p in (ROOT / "data/processed/merged_raw/labels/train").iterdir():
    src = p.name.split("_")[0]
    for l in p.read_text().splitlines():
        v = l.split()
        if v and int(v[0]) in (1, 2):
            geo.setdefault((src, NAMES[int(v[0])]), []).append(float(v[3]) / max(float(v[4]), 1e-6))
for k, v in sorted(geo.items()):
    print("train label w/h", k, "n", len(v), "median", round(float(np.median(v)), 2), "p10-p90", np.round(np.percentile(v, [10, 90]), 2))
    out[f"wh_{k[0]}_{k[1]}"] = round(float(np.median(v)), 2)
for spec in weights:
    name, w = spec.split("=")
    m = YOLO(w)
    tally = {}
    for p in sorted((VAL / "images/val").iterdir()):
        src = p.name.split("_")[0]
        im = cv2.imread(str(p)); h, W = im.shape[:2]
        gt = load_gt(p, W, h)
        r = m.predict(im, conf=.3, imgsz=640, verbose=False, device=0)[0]
        pr = list(zip(r.boxes.cls.cpu().numpy().astype(int), r.boxes.xyxy.cpu().numpy()))
        for c, b in gt:
            if c == 0: continue
            same = max([iou(b, q) for pc, q in pr if pc == c] or [0])
            wrong = max([iou(b, q) for pc, q in pr if pc == 3 - c] or [0])
            t = tally.setdefault(f"{src}_{NAMES[c]}", {"n": 0, ".5": 0, ".3": 0, ".1": 0, "wrong_class_.3": 0, "ious": []})
            t["n"] += 1
            for th in (.5, .3, .1):
                t[str(th)[1:]] += same >= th
            t["wrong_class_.3"] += wrong >= .3 and same < .3
            t["ious"].append(float(same))
    for k, t in tally.items():
        hits = [i for i in t.pop("ious") if i >= .1]
        t["median_iou_of_hits"] = round(float(np.median(hits)), 2) if hits else None
        print(name, k, t)
    out[name] = tally
(ROOT / "reports/diagnostics/box_geometry.json").write_text(json.dumps(out, indent=1, default=int))
