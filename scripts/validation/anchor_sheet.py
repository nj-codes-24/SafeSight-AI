"""Frames with a coordinate grid, for placing identity anchors (normalised x, y) by eye. No model output is drawn.

    python scripts/validation/anchor_sheet.py CLIP T1,T2,... [--width 640]

Writes reports/validation/review/anchors/<clip>.jpg (git-ignored): one tile per time, grid lines every 0.1 with labels.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.review_frames import clip_path  # noqa: E402

OUT = ROOT / "reports" / "validation" / "review" / "anchors"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("times")
    ap.add_argument("--width", type=int, default=640)
    a = ap.parse_args(argv)
    cap = cv2.VideoCapture(str(clip_path(a.clip)))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    tiles = []
    for t in (float(x) for x in a.times.split(",")):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * fps))
        ok, f = cap.read()
        if not ok:
            continue
        f = cv2.resize(f, (a.width, int(f.shape[0] * a.width / f.shape[1])))
        h, w = f.shape[:2]
        for k in range(1, 10):
            cv2.line(f, (int(w * k / 10), 0), (int(w * k / 10), h), (0, 255, 255), 1)
            cv2.line(f, (0, int(h * k / 10)), (w, int(h * k / 10)), (0, 255, 255), 1)
            cv2.putText(f, f".{k}", (int(w * k / 10) + 2, 12), 0, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(f, f".{k}", (2, int(h * k / 10) - 2), 0, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(f, (w - 90, h - 20), (w, h), (0, 0, 0), -1)
        cv2.putText(f, f"{t:.1f} s", (w - 85, h - 6), 0, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(f)
    cap.release()
    rows = [np.hstack(tiles[i:i + 2] + [np.zeros_like(tiles[0])] * (2 - len(tiles[i:i + 2]))) for i in range(0, len(tiles), 2)]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{a.clip}.jpg"
    cv2.imwrite(str(p), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(p)


if __name__ == "__main__":
    main()
