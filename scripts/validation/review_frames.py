"""Detail review sheets: full-resolution crops of one clip over a time range, timestamped, with zones drawn.

    python scripts/validation/review_frames.py CLIP START END EVERY [--crop X0 Y0 X1 Y1] [--width 480] [--cols 4]

CLIP is a clip id from reports/validation/clip_manifest.csv; the crop is in fractions of the frame. Output goes to
reports/validation/review/detail/ (JPEG, git-ignored). No model output is ever drawn.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "reports" / "validation" / "review" / "detail"


def clip_path(clip_id):
    with open(ROOT / "reports" / "validation" / "clip_manifest.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["clip_id"] == clip_id:
                return ROOT / r["file"]
    raise SystemExit(f"unknown clip {clip_id}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("start", type=float)
    ap.add_argument("end", type=float)
    ap.add_argument("every", type=float)
    ap.add_argument("--crop", nargs=4, type=float, default=[0, 0, 1, 1])
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"].get(a.clip, [])
    cap = cv2.VideoCapture(str(clip_path(a.clip)))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    thumbs = []
    for t in np.arange(a.start, a.end + 1e-9, a.every):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * fps))
        ok, f = cap.read()
        if not ok:
            continue
        h, w = f.shape[:2]
        for z in zones:
            pts = (np.array(z["polygon"]) * [w, h]).astype(np.int32)
            cv2.polylines(f, [pts], True, (0, 200, 255), max(1, w // 640), cv2.LINE_AA)
        x0, y0, x1, y1 = (int(a.crop[0] * w), int(a.crop[1] * h), int(a.crop[2] * w), int(a.crop[3] * h))
        c = f[y0:y1, x0:x1]
        c = cv2.resize(c, (a.width, int(c.shape[0] * a.width / c.shape[1])), interpolation=cv2.INTER_AREA)
        cv2.rectangle(c, (0, 0), (a.width, 20), (0, 0, 0), -1)
        cv2.putText(c, f"{a.clip} {t:6.2f}s f{round(t * fps)}", (4, 15), 0, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(c)
    cap.release()
    th, tw = thumbs[0].shape[:2]
    rows = [thumbs[i:i + a.cols] for i in range(0, len(thumbs), a.cols)]
    sheet = np.full((th * len(rows), tw * a.cols, 3), 255, np.uint8)
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = im[:th, :tw]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{a.clip}_{a.start:g}-{a.end:g}{('_' + a.tag) if a.tag else ''}.jpg"
    cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(path)


if __name__ == "__main__":
    main()
