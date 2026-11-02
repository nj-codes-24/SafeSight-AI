"""Build the box-harmonised training sets and the SH17 validation set.

    merged_h        merged_clean with Construction-PPE head boxes extended to full heads (train only)
    merged_h_sh17   merged_h plus a balanced SH17 train subset
    sh17_val        SH17 official val, fully labelled, canonical full-head boxes, for measuring real precision

Val and test of merged_clean are never changed. SH17 images near-duplicating any existing train, val or test image are
dropped, and images whose head and helmet boxes do not resolve cleanly are rejected rather than guessed.
"""
import json
import os
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from find_near_duplicates import embed  # noqa: E402

RAW = ROOT / "data" / "raw" / "sh17"
PROC = ROOT / "data" / "processed"
CLEAN = PROC / "merged_clean"
HEAD_WH = 0.75  # canonical head box aspect, between Mendeley (0.61) and SH17 (0.79)
BARE_ONLY_IMAGES = 1500
DUP = 0.90
HELMET_ON = 0.4  # share of a helmet box inside a head box that means "this head wears it"
HELMET_TOUCH = 0.05  # below HELMET_ON but above this the pairing is ambiguous, so the image is rejected
MAX_SIDE = 1280
NAMES = {0: "person", 1: "helmet", 2: "no_helmet"}


def inter(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def extended(box, im_h):
    """Extend a headgear-only box downward to a full-head aspect."""
    x1, y1, x2, y2 = box
    return [x1, y1, x2, min(im_h, max(y2, y1 + (x2 - x1) / HEAD_WH))]


def sh17_labels(stem, w, h):
    """YOLO lines in canonical form: a head holding a helmet is helmet, any other head is no_helmet. Hats are not helmets."""
    o = {}
    for ob in ET.parse(RAW / "voc_labels" / f"{stem}.xml").getroot().findall("object"):
        b = ob.find("bndbox")
        o.setdefault(ob.find("name").text.strip().lower(), []).append([float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax")])
    out, heads, helmets = [], o.get("head", []), o.get("helmet", [])
    claimed, ambiguous = set(), False
    for h_box in heads:
        best, bi = 0, None
        for i, k in enumerate(helmets):
            f = inter(h_box, k) / max((k[2] - k[0]) * (k[3] - k[1]), 1)
            if f > best:
                best, bi = f, i
        if best > HELMET_ON:
            claimed.add(bi)
            out.append((1, h_box))
        else:
            ambiguous |= best > HELMET_TOUCH
            out.append((2, h_box))
    loose = [k for i, k in enumerate(helmets) if i not in claimed]
    for k in loose:  # a helmet with no head of its own, just above or beside a labelled bare head, may be that head's helmet
        cx = (k[0] + k[2]) / 2
        ambiguous |= any(c == 2 and b[0] - (b[2] - b[0]) < cx < b[2] + (b[2] - b[0]) and abs(k[3] - b[1]) < b[3] - b[1] for c, b in out)
    out += [(1, extended(k, h)) for k in loose]
    out += [(0, p) for p in o.get("person", [])]
    return ["%d %.6f %.6f %.6f %.6f" % (c, (b[0] + b[2]) / 2 / w, (b[1] + b[3]) / 2 / h, (b[2] - b[0]) / w, (b[3] - b[1]) / h)
            for c, b in out], any(c == 1 for c, _ in out), any(c == 2 for c, _ in out), ambiguous


def write_sh17(path, img_dir, lbl_dir, name):
    im = cv2.imread(str(path))
    h, w = im.shape[:2]
    lines, *_ = sh17_labels(path.stem, w, h)
    s = MAX_SIDE / max(h, w)
    if s < 1:
        im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(img_dir / f"{name}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    (lbl_dir / f"{name}.txt").write_text("\n".join(lines))


def harmonised_lines(lbl, img):
    h, w = cv2.imread(str(img)).shape[:2]
    out = []
    for line in lbl.read_text().splitlines():
        v = line.split()
        if v and v[0] in "12":
            x, y, bw, bh = map(float, v[1:5])
            b = extended([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h], h)
            line = "%s %.6f %.6f %.6f %.6f" % (v[0], x, (b[1] + b[3]) / 2 / h, bw, (b[3] - b[1]) / h)
        out.append(line)
    return out


def build_harmonised(root):
    for s in ("train", "val", "test"):
        (root / "images" / s).mkdir(parents=True, exist_ok=True)
        (root / "labels" / s).mkdir(parents=True, exist_ok=True)
        for img in (CLEAN / "images" / s).iterdir():
            lbl = CLEAN / "labels" / s / f"{img.stem}.txt"
            if not (root / "images" / s / img.name).exists():
                os.link(img, root / "images" / s / img.name)
            if s == "train" and img.name.startswith("cppe_"):
                (root / "labels" / s / lbl.name).write_text("\n".join(harmonised_lines(lbl, img)))
            else:
                shutil.copyfile(lbl, root / "labels" / s / lbl.name)
    (root / "dataset.yaml").write_text(yaml.safe_dump({"path": str(root), "train": "images/train", "val": "images/val",
                                                       "test": "images/test", "names": NAMES}))


def main():
    images = {p.stem: p for p in (RAW / "images").iterdir()}
    train = [images[Path(x).stem] for x in (RAW / "train_files.txt").read_text().split() if Path(x).stem in images]
    val = [images[Path(x).stem] for x in (RAW / "val_files.txt").read_text().split() if Path(x).stem in images]
    held = sorted((CLEAN / "images" / "val").iterdir()) + sorted((CLEAN / "images" / "test").iterdir())
    seen_train = sorted((CLEAN / "images" / "train").iterdir())
    cache = PROC / "sh17_embeddings.npz"
    if cache.exists():
        d = np.load(cache)
        et, ev, eh, es = d["et"], d["ev"], d["eh"], d["es"]
    else:
        print("embedding", len(train), len(val), len(held), len(seen_train), flush=True)
        et, ev, eh, es = embed(train), embed(val), embed(held), embed(seen_train)
        np.savez(cache, et=et, ev=ev, eh=eh, es=es)
    bad_train = (et @ np.vstack([eh, es, ev]).T).max(1) > DUP  # every existing image and SH17 val
    bad_val = (ev @ np.vstack([eh, es]).T).max(1) > DUP
    print("SH17 train dropped as near-duplicates:", int(bad_train.sum()), "SH17 val dropped:", int(bad_val.sum()), flush=True)

    clean_train = [p for p, b in zip(train, bad_train) if not b]
    helmeted, bare, rejected = [], [], 0
    for p in clean_train:
        im_size = cv2.imread(str(p)).shape
        _, has_helmet, has_bare, ambiguous = sh17_labels(p.stem, im_size[1], im_size[0])
        rejected += ambiguous
        if not ambiguous:
            (helmeted if has_helmet else bare if has_bare else []).append(p)
    print("rejected as ambiguous head and helmet pairing:", rejected, flush=True)
    random.seed(42)
    random.shuffle(bare)
    chosen = helmeted + bare[:BARE_ONLY_IMAGES]
    print("SH17 train: helmet images", len(helmeted), "bare-only available", len(bare), "chosen", len(chosen), flush=True)

    build_harmonised(PROC / "merged_h")
    root = PROC / "merged_h_sh17"
    build_harmonised(root)
    for p in chosen:
        write_sh17(p, root / "images" / "train", root / "labels" / "train", f"sh17_{p.stem}")

    v = PROC / "sh17_val"
    (v / "images" / "val").mkdir(parents=True, exist_ok=True)
    (v / "labels" / "val").mkdir(parents=True, exist_ok=True)
    kept = []
    for p, b in zip(val, bad_val):
        s = cv2.imread(str(p)).shape
        if not b and not sh17_labels(p.stem, s[1], s[0])[3]:
            kept.append(p)
    for p in kept:
        write_sh17(p, v / "images" / "val", v / "labels" / "val", f"sh17_{p.stem}")
    (v / "d.yaml").write_text(yaml.safe_dump({"path": str(v), "train": "images/val", "val": "images/val", "names": NAMES}))

    def count(d):
        c = dict.fromkeys(NAMES.values(), 0)
        for f in d.iterdir():
            for line in f.read_text().splitlines():
                c[NAMES[int(line.split()[0])]] += 1
        return c
    res = {"sh17_train_dropped": int(bad_train.sum()), "sh17_val_dropped": int(bad_val.sum()), "sh17_val_images": len(kept),
           "sh17_train_rejected_ambiguous": rejected, "sh17_train_images_used": len(chosen), "helmet_images": len(helmeted),
           "merged_h_sh17_train_instances": count(root / "labels" / "train"), "sh17_val_instances": count(v / "labels" / "val")}
    (ROOT / "reports" / "diagnostics" / "sh17_build.json").write_text(json.dumps(res, indent=1))
    print(res)


if __name__ == "__main__":
    main()
