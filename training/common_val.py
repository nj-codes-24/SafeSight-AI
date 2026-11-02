"""Build the common validation set and compare candidates on it.

All candidates are scored on the same images. The set is merged_clean val, whose person labels include teacher
pseudo-labels; helmet and no_helmet labels are human annotations. Unlabelled heads exist in val, so precision is a
lower bound. no_helmet is the deciding class. Also reports the Construction-PPE and Mendeley slices separately.

    python training/common_val.py NAME=WEIGHTS [NAME=WEIGHTS ...]
"""
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402

SRC = ROOT / "data" / "processed" / "merged_clean"
OUT = ROOT / "data" / "processed" / "common_val"
OPERATING_CONF = 0.3


def build():
    if OUT.exists():
        return
    for src in ("all", "cppe", "mendeley"):
        root = OUT / src
        (root / "images" / "val").mkdir(parents=True)
        (root / "labels" / "val").mkdir(parents=True)
        for p in (SRC / "images" / "val").iterdir():
            if src == "all" or p.name.startswith(src + "_"):
                shutil.copyfile(p, root / "images" / "val" / p.name)
                shutil.copyfile(SRC / "labels" / "val" / f"{p.stem}.txt", root / "labels" / "val" / f"{p.stem}.txt")
        (root / "d.yaml").write_text(yaml.safe_dump({"path": str(root), "train": "images/val", "val": "images/val",
                                                     "names": {0: "person", 1: "helmet", 2: "no_helmet"}}))


def score(weights, data):
    m = YOLO(weights)
    r = m.val(data=str(data), split="val", imgsz=640, batch=16, device=0, plots=False, verbose=False, workers=2,
              project=str(ROOT / "runs" / "_cv"), name="v", exist_ok=True)
    per = {}
    for i, c in enumerate(r.box.ap_class_index):
        p, rc = float(r.box.p[i]), float(r.box.r[i])
        per[r.names[int(c)]] = dict(P=round(p, 3), R=round(rc, 3), F1=round(2 * p * rc / (p + rc + 1e-9), 3),
                                    AP50=round(float(r.box.ap50[i]), 3), AP50_95=round(float(r.box.ap[i]), 3))
    r2 = m.val(data=str(data), split="val", imgsz=640, batch=16, device=0, plots=True, verbose=False, workers=2,
               conf=OPERATING_CONF, project=str(ROOT / "runs" / "_cv"), name="v", exist_ok=True)
    cm = r2.confusion_matrix.matrix
    ops = {}
    for i, n in r2.names.items():
        tp, gt = float(cm[i, i]), float(cm[:, i].sum())
        pred = float(cm[i].sum())
        ops[n] = dict(TP=int(tp), FN_missed=int(cm[-1, i]), FP_background=int(cm[i, -1]),
                      confused=int(gt - tp - cm[-1, i]), recall=round(tp / gt, 3) if gt else None,
                      precision=round(tp / pred, 3) if pred else None)
    return dict(map50=round(float(r.box.map50), 3), map=round(float(r.box.map), 3), per_class=per, at_conf_0_3=ops,
                ms_per_image=round(r.speed["inference"], 2))


def main():
    build()
    res = {}
    for arg in sys.argv[1:]:
        name, w = arg.split("=", 1)
        res[name] = {s: score(w, OUT / s / "d.yaml") for s in ("all", "cppe", "mendeley")}
        res[name]["sh17_val"] = score(w, ROOT / "data" / "processed" / "sh17_val" / "d.yaml")  # complete labels: real precision
        a = res[name]["all"]
        b = res[name]["sh17_val"]["per_class"]["no_helmet"]
        print(f"{name:22s} SH17 val mAP50={res[name]['sh17_val']['map50']:.3f} no_helmet P={b['P']} R={b['R']} AP50={b['AP50']}", flush=True)
        nh, no = a["per_class"]["no_helmet"], a["at_conf_0_3"]["no_helmet"]
        print(f"{name:22s} mAP50={a['map50']:.3f} mAP={a['map']:.3f} | no_helmet P={nh['P']} R={nh['R']} AP50={nh['AP50']} "
              f"AP={nh['AP50_95']} | conf.3 TP={no['TP']} FN={no['FN_missed']} FP={no['FP_background']} "
              f"conf={no['confused']} | {a['ms_per_image']}ms", flush=True)
    p = ROOT / "reports" / "common_val.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    p.write_text(json.dumps({**old, **res}, indent=1))


if __name__ == "__main__":
    main()
