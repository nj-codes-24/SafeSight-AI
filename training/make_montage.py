"""Draw labelled boxes on random samples, or crop one class, to visually check annotations."""
import argparse
import random
from pathlib import Path

import cv2
import numpy as np

COLORS = [(80, 200, 80), (220, 160, 60), (60, 200, 220), (200, 80, 200), (60, 60, 230), (240, 240, 240),
          (240, 120, 60), (30, 30, 255), (120, 120, 255), (160, 120, 255), (200, 120, 255)]


def load(lbl):
    if not lbl.exists():
        return []
    return [(int(p[0]), *map(float, p[1:5])) for p in (l.split() for l in lbl.read_text().splitlines()) if p]


def scenes(imgs, lbls, names, n, cols, rng, tile=420):
    out = []
    for p in rng.sample(imgs, min(n, len(imgs))):
        im = cv2.imread(str(p))
        h, w = im.shape[:2]
        s = tile / max(h, w)
        im = cv2.resize(im, (int(w * s), int(h * s)))
        h, w = im.shape[:2]
        for c, x, y, bw, bh in load(lbls / f"{p.stem}.txt"):
            a, b = (int((x - bw / 2) * w), int((y - bh / 2) * h)), (int((x + bw / 2) * w), int((y + bh / 2) * h))
            col = COLORS[c % len(COLORS)]
            cv2.rectangle(im, a, b, col, 2)
            cv2.putText(im, names[c], (a[0], max(10, a[1] - 3)), 0, 0.4, col, 1, cv2.LINE_AA)
        out.append(cv2.copyMakeBorder(im, 0, tile - h, 0, tile - w, cv2.BORDER_CONSTANT))
    return grid(out, cols)


def crops(imgs, lbls, names, target, n, cols, rng, tile=120):
    items = []
    for p in imgs:
        for c, x, y, bw, bh in load(lbls / f"{p.stem}.txt"):
            if names[c] == target:
                items.append((p, x, y, bw, bh))
    rng.shuffle(items)
    out = []
    for p, x, y, bw, bh in items[:n]:
        im = cv2.imread(str(p))
        h, w = im.shape[:2]
        pad = 0.15
        a, b = int(max(0, (x - bw * (0.5 + pad)) * w)), int(max(0, (y - bh * (0.5 + pad)) * h))
        c2, d = int(min(w, (x + bw * (0.5 + pad)) * w)), int(min(h, (y + bh * (0.5 + pad)) * h))
        out.append(cv2.resize(im[b:d, a:c2], (tile, tile)))
    return grid(out, cols)


def grid(tiles, cols):
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--split", default="train")
    ap.add_argument("--names", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop", default="", help="class name: montage of its crops instead of full scenes")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    root, names = Path(a.root), a.names.split(",")
    imgs = sorted((root / "images" / a.split).iterdir())
    lbls = root / "labels" / a.split
    rng = random.Random(a.seed)
    m = crops(imgs, lbls, names, a.crop, a.n, a.cols, rng) if a.crop else scenes(imgs, lbls, names, a.n, a.cols, rng)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(a.out, m, [cv2.IMWRITE_JPEG_QUALITY, 85])
