"""Evaluate a checkpoint on one split: per-class P/R/F1/mAP, confusion matrix, FP/FN counts and error crops.

    python training/evaluate.py --weights W --data D --split val --name b0_val [--conf 0.25]

Writes reports/eval/<name>/metrics.json. Use --split test only for frozen, final candidates.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--name", required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--classes", type=int, nargs="*", help="score only these class ids (sources without person labels)")
    a = ap.parse_args()
    out = ROOT / "reports" / "eval" / a.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    m = YOLO(a.weights)
    r = m.val(data=a.data, split=a.split, imgsz=a.imgsz, batch=16, device=0, plots=True, save_json=False,
              project=str(out), name="val", exist_ok=True, verbose=False, workers=4, classes=a.classes)
    names = r.names
    res = {"weights": a.weights, "data": a.data, "split": a.split, "overall": {
        "precision": float(r.box.mp), "recall": float(r.box.mr), "mAP50": float(r.box.map50), "mAP50_95": float(r.box.map)},
        "speed_ms": r.speed, "per_class": {}}
    ap_idx = list(r.box.ap_class_index)
    for i, c in enumerate(ap_idx):
        p, rc = float(r.box.p[i]), float(r.box.r[i])
        res["per_class"][names[int(c)]] = {
            "precision": p, "recall": rc, "f1": 2 * p * rc / (p + rc + 1e-9),
            "AP50": float(r.box.ap50[i]), "AP50_95": float(r.box.ap[i])}
    # mAP needs the near-zero default threshold; error counts must come from a real operating threshold.
    r2 = m.val(data=a.data, split=a.split, imgsz=a.imgsz, batch=16, device=0, plots=True, conf=a.conf,
               project=str(out), name="operating", exist_ok=True, verbose=False, workers=4, classes=a.classes)
    cm = r2.confusion_matrix.matrix  # rows predicted, columns true; last index is background
    res["operating_conf"] = a.conf
    res["confusion_matrix"] = {
        "labels": [names[i] for i in range(len(names))] + ["background"], "rows_pred_cols_true": cm.tolist()}
    res["errors"] = {
        names[i]: {"false_negative_missed": float(cm[-1, i]), "false_positive_background": float(cm[i, -1]),
                   "confused_as_other_class": float(cm[:-1, i].sum() - cm[i, i]), "true_positive": float(cm[i, i])}
        for i in range(len(names))}
    (out / "metrics.json").write_text(json.dumps(res, indent=1))
    o = res["overall"]
    print(f"{a.name}: P={o['precision']:.3f} R={o['recall']:.3f} mAP50={o['mAP50']:.3f} mAP50-95={o['mAP50_95']:.3f}")
    for k, v in res["per_class"].items():
        print(f"  {k:10s} P={v['precision']:.3f} R={v['recall']:.3f} F1={v['f1']:.3f} AP50={v['AP50']:.3f} AP={v['AP50_95']:.3f}")
    print(json.dumps(res["errors"]))


if __name__ == "__main__":
    sys.exit(main())
