"""Error-analysis probe: what the frozen model outputs on chosen frames, down to the 0.10 floor, before any threshold,
vote or rule. Used after scoring to tell "the model saw nothing" from "below threshold" from "wrong class".

    python scripts/validation/probe_detections.py CLIP T1,T2,... [--crop X0 Y0 X1 Y1] [--tag NAME]

The crop (fractions of the frame) limits the listing and the image to a region. Writes a JPEG with every raw box
(class and confidence) to reports/validation/review/probe/ (git-ignored) and prints the boxes, with head heights in
source pixels. Diagnostic only: nothing here feeds the scores.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.review_frames import clip_path  # noqa: E402

OUT = ROOT / "reports" / "validation" / "review" / "probe"
COLOURS = {"person": (200, 200, 200), "helmet": (60, 200, 60), "no_helmet": (40, 40, 230)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("times")
    ap.add_argument("--crop", nargs=4, type=float, default=(0, 0, 1, 1))
    ap.add_argument("--tag", default="probe")
    ap.add_argument("--width", type=int, default=480)
    a = ap.parse_args(argv)
    from inference.detector import Detector

    det = Detector()
    cap = cv2.VideoCapture(str(clip_path(a.clip)))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    tiles = []
    for t in (float(x) for x in a.times.split(",")):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * fps))
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = int(a.crop[0] * w), int(a.crop[1] * h), int(a.crop[2] * w), int(a.crop[3] * h)
        boxes = det.predict(frame)
        view = frame.copy()
        print(f"t={t:.2f}s")
        for b, c, k in sorted(zip(boxes.xyxy, boxes.conf, boxes.cls), key=lambda z: -z[1]):
            name = det.names[int(k)]
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            print(f"  {name:<9} {c:.2f}  box {b.astype(int).tolist()}  height {b[3] - b[1]:.0f}px")
            col = COLOURS.get(name, (255, 255, 0))
            cv2.rectangle(view, tuple(b[:2].astype(int)), tuple(b[2:].astype(int)), col, 2)
            cv2.putText(view, f"{name} {c:.2f}", (int(b[0]), int(b[1]) - 4), 0, 0.6, col, 2, cv2.LINE_AA)
        crop = view[y0:y1, x0:x1]
        crop = cv2.resize(crop, (a.width, int(crop.shape[0] * a.width / crop.shape[1])))
        cv2.rectangle(crop, (0, 0), (a.width, 20), (0, 0, 0), -1)
        cv2.putText(crop, f"{a.clip} {t:.2f}s raw model output", (4, 14), 0, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(crop)
    cap.release()
    if tiles:
        hmax = max(x.shape[0] for x in tiles)
        tiles = [cv2.copyMakeBorder(x, 0, hmax - x.shape[0], 0, 0, cv2.BORDER_CONSTANT) for x in tiles]
        rows = [np.hstack(tiles[i:i + 3] + [np.zeros_like(tiles[0])] * (3 - len(tiles[i:i + 3]))) for i in range(0, len(tiles), 3)]
        OUT.mkdir(parents=True, exist_ok=True)
        p = OUT / f"{a.clip}_{a.tag}.jpg"
        cv2.imwrite(str(p), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(p)


if __name__ == "__main__":
    main()
