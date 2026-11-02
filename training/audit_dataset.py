"""Audit a YOLO-format dataset: counts, class balance, box sizes, label sanity, duplicates."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import imagehash
from PIL import Image


def audit(root: Path, names: dict[int, str]) -> dict:
    report = {"root": str(root), "splits": {}}
    hashes = defaultdict(list)
    for split in ("train", "val", "test"):
        img_dir, lbl_dir = root / "images" / split, root / "labels" / split
        if not img_dir.exists():
            continue
        images = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})
        inst, img_with, small = Counter(), Counter(), Counter()
        missing, empty, malformed, corrupt = 0, 0, 0, 0
        for img in images:
            try:
                with Image.open(img) as im:
                    hashes[str(imagehash.phash(im.convert("RGB")))].append(f"{split}/{img.name}")
            except Exception:
                corrupt += 1
                continue
            lbl = lbl_dir / (img.stem + ".txt")
            if not lbl.exists():
                missing += 1
                continue
            lines = [l.split() for l in lbl.read_text().splitlines() if l.strip()]
            if not lines:
                empty += 1
            seen = set()
            for parts in lines:
                try:
                    cls = int(parts[0])
                    x, y, w, h = map(float, parts[1:5])
                    if len(parts) != 5 or not all(0 <= v <= 1 for v in (x, y, w, h)):
                        raise ValueError
                except (ValueError, IndexError):
                    malformed += 1
                    continue
                inst[cls] += 1
                seen.add(cls)
                if w * h < (32 / 640) ** 2:
                    small[cls] += 1
            img_with.update(seen)
        report["splits"][split] = {
            "images": len(images),
            "missing_labels": missing,
            "empty_labels": empty,
            "malformed_lines": malformed,
            "corrupt_images": corrupt,
            "instances": {names.get(k, str(k)): v for k, v in sorted(inst.items())},
            "images_with_class": {names.get(k, str(k)): v for k, v in sorted(img_with.items())},
            "small_boxes_lt32px": {names.get(k, str(k)): v for k, v in sorted(small.items())},
        }
    dup_groups = [v for v in hashes.values() if len(v) > 1]
    cross = [g for g in dup_groups if len({x.split("/")[0] for x in g}) > 1]
    report["exact_phash_duplicate_groups"] = len(dup_groups)
    report["cross_split_duplicate_groups"] = len(cross)
    report["cross_split_examples"] = cross[:10]
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--names", required=True, help="comma-separated class names in id order")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    names = dict(enumerate(a.names.split(",")))
    r = audit(Path(a.root), names)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(r, indent=2))
    print(json.dumps(r, indent=2))
