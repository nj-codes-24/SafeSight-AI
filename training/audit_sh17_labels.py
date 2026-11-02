"""Visual audit of derived SH17 labels before training. Writes a random sample and every M2 disagreement as crop sheets."""
import json
import os
import random
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402

DS = ROOT / "data" / "processed" / "merged_h_sh17"
OUT = ROOT / "reports" / "diagnostics" / "sh17_audit"
OUT.mkdir(parents=True, exist_ok=True)


def iou(a, b):
    i = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def crop(im, b):
    x1, y1, x2, y2 = np.asarray(b).astype(int)
    pad = int(max(x2 - x1, y2 - y1) * 0.4)
    c = im[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
    return cv2.resize(c, (120, 120)) if c.size else np.zeros((120, 120, 3), np.uint8)


def sheet(cells, name, per=12):
    if not cells:
        return
    while len(cells) % per:
        cells.append(np.zeros((120, 120, 3), np.uint8))
    cv2.imwrite(str(OUT / name), np.vstack([np.hstack(cells[i:i + per]) for i in range(0, len(cells), per)]))


m = YOLO(str(ROOT / "models" / "candidates" / "m2_fallback.pt"))
random.seed(7)
bare, helm, disagree, order = [], [], [], []
sizes = []
for lbl in sorted((DS / "labels" / "train").glob("sh17_*.txt")):
    im = cv2.imread(str(DS / "images" / "train" / f"{lbl.stem}.jpg"))
    h, w = im.shape[:2]
    gt = []
    for line in lbl.read_text().splitlines():
        c, x, y, bw, bh = line.split()
        if c in "12":
            x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
            gt.append((int(c), [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2]))
    if not gt:
        continue
    r = m.predict(im, conf=0.4, imgsz=640, verbose=False, device=0)[0]
    pr = list(zip(r.boxes.cls.cpu().numpy().astype(int), r.boxes.xyxy.cpu().numpy()))
    for c, b in gt:
        sizes.append((b[3] - b[1]) * 640 / max(h, w))
        (bare if c == 2 else helm).append((lbl.stem, im[:0], b))
        if c == 2 and any(pc == 1 and iou(b, q) > 0.3 for pc, q in pr):
            disagree.append(crop(im, b))
            order.append(lbl.stem)
        if (c == 2 and random.random() < 0.02) or (c == 1 and random.random() < 0.08):
            (bare if c == 2 else helm)[-1] = (lbl.stem, crop(im, b), b)
s_bare = [x[1] for x in bare if x[1].size]
s_helm = [x[1] for x in helm if x[1].size]
sheet(s_bare[:96], "random_no_helmet.jpg")
sheet(s_helm[:60], "random_helmet.jpg")
sheet(disagree[120:], "no_helmet_where_m2_sees_helmet_rest.jpg")
sheet(disagree[:120], "no_helmet_where_m2_sees_helmet.jpg")
(OUT / "disagree_order.json").write_text(json.dumps(order))
res = {"no_helmet_labels": len(bare), "helmet_labels": len(helm), "m2_says_helmet_on_no_helmet_label": len(disagree),
       "median_head_height_640": round(float(np.median(sizes)), 1), "under_16px_640": int(sum(s < 16 for s in sizes))}
(OUT / "audit.json").write_text(json.dumps(res, indent=1))
print(res, len(s_bare), len(s_helm))
