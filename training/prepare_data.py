"""Build the leak-free datasets from the raw downloads. Raw data is never modified.

Common classes: 0 person, 1 helmet, 2 no_helmet.

Near-duplicate clusters (connected components of CNN-embedding similarity) keep footage from one source in one
split. The official Construction-PPE test images are kept verbatim as the test set; any train/val image from a
cluster touching test is dropped instead of moving test images. Mendeley gets a held-out test split by cluster.

    python training/prepare_data.py cppe      -> data/processed/cppe (baseline)
    python training/prepare_data.py merged    -> data/processed/merged (after pseudo_label.py)
"""
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_near_duplicates import EXTS, embed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_C = ROOT / "data" / "raw" / "construction-ppe"
RAW_M = ROOT / "data" / "raw" / "mendeley-ppe" / "20250731-ppe2286y"
NAMES = ["person", "helmet", "no_helmet"]
THRESH = 0.90
C_MAP = {6: 0, 0: 1, 7: 2}  # Person, helmet, no_helmet. 'none' and gear classes are dropped.
M_MAP = {0: 1, 1: 2}  # Helmet, NoHelmet. Vest classes dropped: Construction-PPE has no no_vest label.


def collect():
    items = []  # (source, split, image path, label path)
    for s in ("train", "val", "test"):
        for p in sorted((RAW_C / "images" / s).iterdir()):
            if p.suffix.lower() in EXTS:
                items.append(("cppe", s, p, RAW_C / "labels" / s / f"{p.stem}.txt"))
    for s in ("train", "valid"):
        for p in sorted((RAW_M / s / "images").iterdir()):
            if p.suffix.lower() in EXTS:
                items.append(("mendeley", "pool", p, RAW_M / s / "labels" / f"{p.stem}.txt"))
    return items


def clusters(paths):
    cache = ROOT / "data" / "processed" / "embeddings.npy"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and len(np.load(cache, mmap_mode="r")) == len(paths):
        e = np.load(cache)
    else:
        e = embed(paths)
        np.save(cache, e)
    t = torch.from_numpy(e).cuda()
    parent = list(range(len(paths)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(0, len(t), 512):
        for r, c in ((t[i:i + 512] @ t.T) > THRESH).nonzero().cpu().numpy():
            a, b = find(i + int(r)), find(int(c))
            if a != b:
                parent[a] = b
    return [find(i) for i in range(len(paths))]


def assign():
    items = collect()
    groups = clusters([str(x[2]) for x in items])
    by_group = {}
    for it, g in zip(items, groups):
        by_group.setdefault(g, []).append(it)
    rng = random.Random(42)
    split = {}
    dropped = Counter()
    # Mendeley-only clusters are split 75/10/15 by cluster.
    for g, members in sorted(by_group.items()):
        srcs = {m[1] for m in members}
        if "test" in srcs:
            final = "test"
        elif "val" in srcs:
            final = "val"
        elif "train" in srcs:
            final = "train"
        else:
            r = rng.random()
            final = "test" if r < 0.15 else "val" if r < 0.25 else "train"
        for m in members:
            orig = m[1]
            if orig != "pool" and orig != final:  # never promote: drop train/val images linked to a later split
                dropped[f"{m[0]}:{orig}_linked_to_{final}"] += 1
                continue
            if m[0] == "mendeley" and final == "test" and "test" in srcs:
                dropped["mendeley:linked_to_cppe_test"] += 1
                continue
            split[str(m[2])] = (m[0], final, m[3])
    return split, dropped, len(by_group)


def convert(lbl: Path, mapping: dict) -> list[str]:
    out = []
    for line in lbl.read_text().splitlines():
        p = line.split()
        if len(p) == 5 and int(p[0]) in mapping:
            out.append(" ".join([str(mapping[int(p[0])]), *p[1:]]))
    return out


def write(root: Path, rows):
    for s in ("train", "val", "test"):
        (root / "images" / s).mkdir(parents=True, exist_ok=True)
        (root / "labels" / s).mkdir(parents=True, exist_ok=True)
    stats = {}
    for img, src, s, lines in rows:
        name = f"{src}_{Path(img).stem[:60]}"
        shutil.copyfile(img, root / "images" / s / (name + Path(img).suffix.lower()))
        (root / "labels" / s / (name + ".txt")).write_text("\n".join(lines) + ("\n" if lines else ""))
        c = stats.setdefault(f"{src}/{s}", Counter())
        c["images"] += 1
        for l in lines:
            c[NAMES[int(l.split()[0])]] += 1
    (root / "dataset.yaml").write_text(yaml.safe_dump(
        {"path": str(root), "train": "images/train", "val": "images/val", "test": "images/test",
         "names": dict(enumerate(NAMES))}, sort_keys=False))
    return {k: dict(v) for k, v in stats.items()}


def iou(a, b):
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    w, h = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    return w * h / (a[2] * a[3] + b[2] * b[3] - w * h + 1e-9)


def overlap_min(a, b):
    """Intersection over the smaller box: catches truncated labels that plain IoU misses."""
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    w, h = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    return w * h / (min(a[2] * a[3], b[2] * b[3]) + 1e-9)


def refine(lines, persons):
    """Add confident teacher persons missing from the labels; return lines and head regions nobody labelled."""
    boxes = [(int(l.split()[0]), *map(float, l.split()[1:])) for l in lines]
    have = [b[1:] for b in boxes if b[0] == 0]
    heads = [b[1:] for b in boxes if b[0] in (1, 2)]
    lines, unlabelled = list(lines), []
    for t in persons:
        box, head = t["box"], t["head"]
        if t["conf"] >= 0.5 and all(iou(box, p) < 0.3 and overlap_min(box, p) < 0.7 for p in have):
            lines.append("0 " + " ".join(f"{v:.6f}" for v in box))
        if head is None:  # no visible face keypoints: nothing to mask
            continue
        hb = ((head[0] + head[2]) / 2, (head[1] + head[3]) / 2, head[2] - head[0], head[3] - head[1])
        if all(iou(hb, l) < 0.05 and overlap_min(hb, l) < 0.3 for l in heads):
            unlabelled.append(tuple(head))
    return lines, unlabelled


def mask_copy(img, dst, regions):
    """Grey out unlabelled heads in the train copy so they are neither positives nor background."""
    im = cv2.imread(str(img))
    h, w = im.shape[:2]
    for x1, y1, x2, y2 in regions:
        im[max(0, int(y1 * h)):int(y2 * h), max(0, int(x1 * w)):int(x2 * w)] = 114
    cv2.imwrite(str(dst), im, [cv2.IMWRITE_JPEG_QUALITY, 95])


def main(kind):
    """kind: cppe | merged_raw (plain union) | merged_clean (teacher persons + masked unlabelled heads)."""
    split, dropped, n_groups = assign()
    root = ROOT / "data" / "processed" / kind
    if root.exists():
        shutil.rmtree(root)
    teacher = {}
    if kind == "merged_clean":
        teacher = json.loads((ROOT / "data" / "processed" / "teacher_persons.json").read_text())
    rows, masks = [], {}
    for img, (src, s, lbl) in split.items():
        if kind == "cppe" and src != "cppe":
            continue
        lines = convert(lbl, C_MAP if src == "cppe" else M_MAP)
        if img in teacher and not (src == "cppe" and s == "test"):
            lines, unlabelled = refine(lines, teacher[img])
            if s == "train" and unlabelled:
                masks[img] = unlabelled
        rows.append((img, src, s, lines))
    stats = write(root, rows)
    for img, regions in masks.items():
        src, s, _ = split[img]
        name = f"{src}_{Path(img).stem[:60]}{Path(img).suffix.lower()}"
        mask_copy(img, root / "images" / s / name, regions)
    rep = {"threshold": THRESH, "clusters": n_groups, "dropped": dict(dropped), "stats": stats,
           "images_with_masked_heads": len(masks), "masked_heads": sum(len(v) for v in masks.values())}
    (ROOT / "reports" / f"prepare_{kind}.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
