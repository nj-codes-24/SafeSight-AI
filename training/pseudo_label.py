"""Run a large COCO pose teacher over the raw images; store person boxes and visible-head regions for merging."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
sys.path.insert(0, str(ROOT / "training"))
from prepare_data import collect  # noqa: E402
from ultralytics import YOLO  # noqa: E402

KP_CONF = 0.5  # face keypoints: nose, eyes, ears are indices 0-4


def head_box(box_h, kps):
    pts = [(x, y) for x, y, c in kps[:5] if c >= KP_CONF]
    if len(pts) < 2:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w = max((max(xs) - min(xs)) * 1.8, box_h * 0.10)
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    return [cx - w * 0.7, cy - w * 0.9, cx + w * 0.7, cy + w * 0.7]


def run_teacher(paths):
    teacher = YOLO(str(ROOT / "models" / "pretrained" / "yolo26l-pose.pt"))
    out = {}
    for i in range(0, len(paths), 16):
        chunk = paths[i:i + 16]
        for p, r in zip(chunk, teacher.predict(chunk, conf=0.3, imgsz=960, device=0, verbose=False)):
            rows = []
            if r.keypoints is not None and len(r.boxes):
                kp = r.keypoints.data.cpu().numpy()
                for b, c, k in zip(r.boxes.xywhn.cpu().numpy(), r.boxes.conf.cpu().numpy(), kp):
                    h, w = r.orig_shape
                    kn = [(float(x) / w, float(y) / h, float(s)) for x, y, s in k]
                    rows.append({"box": [float(v) for v in b], "conf": float(c), "head": head_box(float(b[3]), kn)})
            out[p] = rows
    return out


if __name__ == "__main__":
    res = run_teacher([str(x[2]) for x in collect() if x[1] != "test"])
    (ROOT / "data" / "processed" / "teacher_persons.json").write_text(json.dumps(res))
    print(len(res), "images,", sum(len(v) for v in res.values()), "persons,",
          sum(1 for v in res.values() for x in v if x["head"]), "visible heads")
