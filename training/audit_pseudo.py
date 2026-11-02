"""Crop random samples of pseudo-labels and masked regions from raw images for a visual precision check."""
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from prepare_data import C_MAP, M_MAP, assign, convert, refine  # noqa: E402

OUT = ROOT / "reports" / "audit"
split, _, _ = assign()
teacher = json.loads((ROOT / "data/processed/teacher_persons.json").read_text())
rng = random.Random(7)
added, masked, n_img = [], [], 0
for img, (src, s, lbl) in split.items():
    if s != "train" or img not in teacher:
        continue
    n_img += 1
    base = convert(lbl, C_MAP if src == "cppe" else M_MAP)
    lines, un = refine(base, teacher[img])
    added += [(img, tuple(map(float, l.split()[1:]))) for l in lines[len(base):]]
    masked += [(img, r) for r in un]
print("train images", n_img, "pseudo persons", len(added), "masked heads", len(masked))


def tile(img, box, xyxy=False):
    im = cv2.imread(img)
    h, w = im.shape[:2]
    x1, y1, x2, y2 = box if xyxy else (box[0] - box[2] / 2, box[1] - box[3] / 2, box[0] + box[2] / 2, box[1] + box[3] / 2)
    c = im[max(0, int(y1 * h)):max(int(y2 * h), int(y1 * h) + 2), max(0, int(x1 * w)):max(int(x2 * w), int(x1 * w) + 2)]
    return cv2.resize(c, (110, 110)) if c.size else np.zeros((110, 110, 3), np.uint8)


def sheet(items, xyxy, path, n=96, cols=12):
    s = rng.sample(items, min(n, len(items)))
    tiles = [tile(i, b, xyxy) for i, b in s]
    while len(tiles) % cols:
        tiles.append(np.zeros((110, 110, 3), np.uint8))
    cv2.imwrite(str(path), np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 85])


sheet(added, False, OUT / "pseudo_persons.jpg")
sheet(masked, True, OUT / "masked_heads.jpg")
