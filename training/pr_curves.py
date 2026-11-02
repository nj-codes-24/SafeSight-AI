"""no_helmet precision-recall by confidence on validation data, and the threshold rule fixed before looking at results.

Rule: the lowest confidence at which SH17-val no_helmet precision reaches 0.95 (SH17 val is the only fully labelled set);
if a model never reaches it, the confidence with the best F1 on SH17 val.
"""
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402

SETS = {"sh17_val": ROOT / "data/processed/sh17_val", "mendeley": ROOT / "data/processed/common_val/mendeley",
        "common_all": ROOT / "data/processed/common_val/all"}
TARGET_P = 0.95
GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)


def iou(a, b):
    i = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def curve(model, root):
    """Per threshold: TP, FP, FN for no_helmet, and helmets predicted as no_helmet."""
    stats = {t: [0, 0, 0, 0] for t in GRID}
    for p in sorted((root / "images" / "val").iterdir()):
        im = cv2.imread(str(p))
        h, w = im.shape[:2]
        gt = {1: [], 2: []}
        for line in (root / "labels" / "val" / f"{p.stem}.txt").read_text().splitlines():
            c, x, y, bw, bh = line.split()
            if c in "12":
                x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
                gt[int(c)].append([x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2])
        r = model.predict(im, conf=0.05, imgsz=640, verbose=False, device=0)[0]
        keep = r.boxes.cls.cpu().numpy().astype(int) == 2
        boxes, confs = r.boxes.xyxy.cpu().numpy()[keep], r.boxes.conf.cpu().numpy()[keep]
        order = np.argsort(-confs)
        for t in GRID:
            used, tp, fp, on_helmet = set(), 0, 0, 0
            for i in order:
                if confs[i] < t:
                    break
                best, bj = 0.0, None
                for j, g in enumerate(gt[2]):
                    if j not in used and iou(boxes[i], g) > best:
                        best, bj = iou(boxes[i], g), j
                if best >= 0.5:
                    used.add(bj)
                    tp += 1
                else:
                    fp += 1
                    on_helmet += any(iou(boxes[i], g) >= 0.3 for g in gt[1])
            s = stats[t]
            s[0] += tp
            s[1] += fp
            s[2] += len(gt[2]) - len(used)
            s[3] += on_helmet
    return {float(t): {"TP": s[0], "FP": s[1], "FN": s[2], "helmet_called_no_helmet": s[3],
                       "precision": round(s[0] / max(s[0] + s[1], 1), 3), "recall": round(s[0] / max(s[0] + s[2], 1), 3)}
            for t, s in stats.items()}


def pick(c):
    ok = [t for t, v in sorted(c.items()) if v["precision"] >= TARGET_P and v["TP"] > 0]
    if ok:
        return ok[0], "lowest confidence with SH17-val precision >= 0.95"
    f1 = {t: 2 * v["precision"] * v["recall"] / max(v["precision"] + v["recall"], 1e-9) for t, v in c.items()}
    return max(f1, key=f1.get), "best F1 on SH17 val (0.95 precision never reached)"


def main():
    res = {}
    for spec in sys.argv[1:]:
        name, w = spec.split("=")
        m = YOLO(w)
        res[name] = {s: curve(m, r) for s, r in SETS.items()}
        t, why = pick(res[name]["sh17_val"])
        res[name]["threshold"] = {"value": t, "rule": why}
        print(name, "threshold", t, why, flush=True)
        for s in SETS:
            v = res[name][s][t]
            print(f"   {s:10s} at {t}: P {v['precision']} R {v['recall']} TP {v['TP']} FP {v['FP']} FN {v['FN']} helmet->no_helmet {v['helmet_called_no_helmet']}", flush=True)
    (ROOT / "reports" / "pr_curves.json").write_text(json.dumps(res, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    colours = {"m2": "#3987e5", "m3": "#d95926", "m5": "#199e70"}
    for ax, s in zip(axes, SETS):
        for name in res:
            c = res[name][s]
            ax.plot([c[t]["recall"] for t in c], [c[t]["precision"] for t in c], marker="o", ms=3, lw=2, color=colours.get(name), label=name)
            t = res[name]["threshold"]["value"]
            ax.plot(c[t]["recall"], c[t]["precision"], "k*", ms=12)
        ax.set_title(f"no_helmet, {s}" + (" (partial labels: precision is a lower bound)" if s != "sh17_val" else ""), fontsize=9)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.legend()
    fig.suptitle("no_helmet precision-recall over confidence 0.05-0.95; star = chosen threshold")
    fig.tight_layout()
    fig.savefig(ROOT / "reports" / "pr_curves_no_helmet.png", dpi=120)


if __name__ == "__main__":
    main()
