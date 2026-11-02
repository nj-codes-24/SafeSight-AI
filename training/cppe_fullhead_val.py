"""Check how much of the Construction-PPE drop is box style: same images, labels extended to full heads. Validation only."""
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
sys.path.insert(0, str(ROOT / "training"))
from add_sh17 import harmonised_lines
from common_val import score

if __name__ == "__main__":
    SRC = ROOT / "data/processed/common_val/cppe"
    OUT = ROOT / "data/processed/common_val_cppe_fullhead"
    (OUT / "images/val").mkdir(parents=True, exist_ok=True); (OUT / "labels/val").mkdir(parents=True, exist_ok=True)
    for p in (SRC / "images/val").iterdir():
        shutil.copyfile(p, OUT / "images/val" / p.name)
        (OUT / "labels/val" / f"{p.stem}.txt").write_text("\n".join(harmonised_lines(SRC / "labels/val" / f"{p.stem}.txt", p)))
    (OUT / "d.yaml").write_text(yaml.safe_dump({"path": str(OUT), "train": "images/val", "val": "images/val", "names": {0: "person", 1: "helmet", 2: "no_helmet"}}))
    res = {}
    for spec in sys.argv[1:]:
        n, w = spec.split("=")
        r = score(w, OUT / "d.yaml"); res[n] = r
        pc, op = r["per_class"], r["at_conf_0_3"]
        print(n, "mAP50", r["map50"], "mAP", r["map"], "helmet AP50", pc["helmet"]["AP50"], "NH", pc["no_helmet"], op["no_helmet"], flush=True)
    (ROOT / "reports/cppe_fullhead_val.json").write_text(json.dumps(res, indent=1))