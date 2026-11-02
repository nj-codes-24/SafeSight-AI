"""Model-health audit run by the watchdog in a throwaway CPU process, so it cannot disturb GPU training.

Checks that a checkpoint copy loads, has the expected classes and gives well-formed predictions.
Prints one JSON line.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))


def main(ckpt, data_yaml):
    from ultralytics import YOLO

    out = {"checkpoint": ckpt, "loaded": False, "names_match": None, "images": 0, "detections": 0, "malformed": 0}
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "audit.pt"
        shutil.copyfile(ckpt, copy)
        model = YOLO(str(copy))
        out["loaded"] = True
        d = yaml.safe_load(Path(data_yaml).read_text())
        names = d["names"]
        names = list(names.values()) if isinstance(names, dict) else names
        out["names_match"] = list(model.names.values()) == names
        base = Path(d.get("path") or Path(data_yaml).parent)
        val = d["val"][0] if isinstance(d["val"], list) else d["val"]
        vdir = base / val if not Path(val).is_absolute() else Path(val)
        imgs = sorted(p for p in vdir.iterdir() if p.is_file())[:20]
        for r in model.predict([str(p) for p in imgs], device="cpu", conf=0.1, verbose=False):
            out["images"] += 1
            b = r.boxes
            out["detections"] += len(b)
            xyxy = b.xyxy.numpy() if len(b) else []
            out["malformed"] += sum(1 for x in xyxy if not (x[2] > x[0] and x[3] > x[1]))
    out["ok"] = bool(out["loaded"] and out["names_match"] and out["images"] and not out["malformed"])
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
