"""Diagnose a model on the common validation set only: per-source domain stats, FP and FN by size, error montages.

    python training/diagnose.py --weights models/best.pt --name m2
"""
import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402

VAL = ROOT / "data" / "processed" / "common_val" / "all"
NAMES = ["person", "helmet", "no_helmet"]
BINS = [(0, 32), (32, 64), (64, 128), (128, 9999)]  # head box height in the 640 px network input


def load_gt(p, w, h):
    out = []
    lb = VAL / "labels" / "val" / f"{p.stem}.txt"
    for line in lb.read_text().splitlines():
        v = line.split()
        if v:
            c, x, y, bw, bh = int(v[0]), *map(float, v[1:5])
            out.append((c, np.array([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h])))
    return out


def iou(a, b):
    i = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def crop(im, b, col, text):
    x1, y1, x2, y2 = b.astype(int)
    pad = int(max(x2 - x1, y2 - y1) * 0.5)
    c = im[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
    c = cv2.resize(c, (150, 150)) if c.size else np.zeros((150, 150, 3), np.uint8)
    cv2.rectangle(c, (0, 0), (149, 149), col, 3)
    cv2.putText(c, text, (4, 144), 0, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    return c


def sheet(cells, path, per=10, limit=60):
    cells = cells[:limit]
    if not cells:
        return
    while len(cells) % per:
        cells.append(np.zeros((150, 150, 3), np.uint8))
    cv2.imwrite(str(path), np.vstack([np.hstack(cells[i:i + per]) for i in range(0, len(cells), per)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--conf", type=float, default=0.3)
    a = ap.parse_args()
    out = ROOT / "reports" / "diagnostics" / a.name
    out.mkdir(parents=True, exist_ok=True)
    m = YOLO(a.weights)
    st = {s: {"images": 0, "brightness": [], "contrast": [], "img_h": [], "head_h_640": {n: [] for n in NAMES[1:]},
              "persons_per_image": [], "fn": {n: {str(b): 0 for b in BINS} for n in NAMES[1:]},
              "tp": {n: {str(b): 0 for b in BINS} for n in NAMES[1:]}, "fp_no_helmet": 0, "fp_helmet": 0,
              "fp_no_helmet_on_labelled_helmet": 0} for s in ("cppe", "mendeley")}
    cells = {"fn_no_helmet": [], "fp_no_helmet": [], "fp_helmet": [], "fn_helmet": []}
    for p in sorted((VAL / "images" / "val").iterdir()):
        src = p.name.split("_")[0]
        s = st[src]
        im = cv2.imread(str(p))
        h, w = im.shape[:2]
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        s["images"] += 1
        s["brightness"].append(float(g.mean()))
        s["contrast"].append(float(g.std()))
        s["img_h"].append(h)
        gt = load_gt(p, w, h)
        s["persons_per_image"].append(sum(c == 0 for c, _ in gt))
        r = m.predict(im, conf=a.conf, imgsz=640, verbose=False, device=0)[0]
        preds = list(zip(r.boxes.cls.cpu().numpy().astype(int), r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()))
        scale = 640 / max(h, w)
        used = set()
        for c, b in gt:
            if c == 0:
                continue
            n = NAMES[c]
            hh = (b[3] - b[1]) * scale
            s["head_h_640"][n].append(float(hh))
            key = str(next(x for x in BINS if x[0] <= hh < x[1]))
            best, bi = 0, None
            for i, (pc, pb, _) in enumerate(preds):
                if pc == c and i not in used and iou(b, pb) > best:
                    best, bi = iou(b, pb), i
            if best >= 0.5:
                used.add(bi)
                s["tp"][n][key] += 1
            else:
                s["fn"][n][key] += 1
                cells[f"fn_{n}"].append(crop(im, b, (0, 0, 255), f"{src[:1]} {hh:.0f}px"))
        for i, (pc, pb, pf) in enumerate(preds):
            if pc == 0 or i in used:
                continue
            n = NAMES[pc]
            s[f"fp_{n}"] += 1
            other = [iou(pb, b) for c, b in gt if c == 3 - pc]
            if pc == 2 and other and max(other) > 0.3:
                s["fp_no_helmet_on_labelled_helmet"] += 1
            cells[f"fp_{n}"].append(crop(im, pb, (0, 165, 255), f"{src[:1]} {pf:.2f}"))
    res = {}
    for k, s in st.items():
        res[k] = {"images": s["images"], "brightness_mean": round(np.mean(s["brightness"]), 1),
                  "contrast_mean": round(np.mean(s["contrast"]), 1), "image_height_median": int(np.median(s["img_h"])),
                  "persons_per_image": round(np.mean(s["persons_per_image"]), 2),
                  "head_height_median_640": {n: round(float(np.median(v)), 1) if v else None for n, v in s["head_h_640"].items()},
                  "fp_no_helmet": s["fp_no_helmet"], "fp_helmet": s["fp_helmet"],
                  "fp_no_helmet_on_labelled_helmet": s["fp_no_helmet_on_labelled_helmet"],
                  "recall_by_head_size": {n: {b: f"{s['tp'][n][b]}/{s['tp'][n][b] + s['fn'][n][b]}" for b in s["tp"][n]} for n in NAMES[1:]}}
    (out / "diagnostics.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    for k, c in cells.items():
        print(k, len(c))
        sheet(c, out / f"{k}.jpg")


if __name__ == "__main__":
    main()
