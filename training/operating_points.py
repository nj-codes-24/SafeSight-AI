"""no_helmet operating points on validation data, for the candidate app thresholds."""
import json
import os
from pathlib import Path

ROOT = Path(".").resolve()
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO

SETS = {"common_all": "data/processed/common_val/all/d.yaml", "mendeley": "data/processed/common_val/mendeley/d.yaml", "cppe_fullhead": "data/processed/common_val_cppe_fullhead/d.yaml", "sh17_val": "data/processed/sh17_val/d.yaml"}
def op(w, d, c):
    r = YOLO(w).val(data=str(ROOT / d), split="val", imgsz=640, batch=16, device=0, plots=True, verbose=False, workers=2, conf=c, project=str(ROOT / "runs/_cv"), name="o", exist_ok=True)
    m = r.confusion_matrix.matrix; tp, gt, pred = m[2, 2], m[:, 2].sum(), m[2].sum()
    return dict(TP=int(tp), FN=int(gt - tp), FP=int(pred - tp), helmet_as_no_helmet=int(m[2, 1]), recall=round(float(tp / gt), 3), precision=round(float(tp / pred), 3) if pred else None)
if __name__ == "__main__":
    res = {}
    for n, w, cs in (("m2", "models/candidates/m2_fallback.pt", (.3,)), ("m5", "runs/m5_sh17_ft/checkpoints/best_good.pt", (.3, .5, .6))):
        for c in cs:
            for s, d in SETS.items():
                res[f"{n}@{c} {s}"] = op(w, d, c); print(n, c, s, res[f"{n}@{c} {s}"], flush=True)
    json.dump(res, open("reports/operating_points.json", "w"), indent=1)