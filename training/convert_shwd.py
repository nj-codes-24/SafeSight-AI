"""Extract SHWD safely and convert VOC to YOLO: hat -> helmet (1), person (a bare head) -> no_helmet (2)."""
import json
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "raw" / "shwd-zip" / "shwd.tar"
DEST = ROOT / "data" / "raw" / "shwd"
MAP = {"hat": 1, "person": 2}


def extract():
    if DEST.exists():
        return
    DEST.mkdir(parents=True)
    if zipfile.is_zipfile(ARCHIVE):
        with zipfile.ZipFile(ARCHIVE) as z:
            root = DEST.resolve()
            for n in z.namelist():
                if not (root / n).resolve().is_relative_to(root):
                    raise RuntimeError(f"unsafe path in archive: {n}")
            z.extractall(DEST)
    else:
        with tarfile.open(ARCHIVE) as t:
            t.extractall(DEST, filter="data")


def main():
    extract()
    ann = next(DEST.rglob("Annotations"))
    imgs = ann.parent / "JPEGImages"
    out = DEST / "yolo_labels"
    out.mkdir(exist_ok=True)
    per_img, c, names = {}, Counter(), Counter()
    for x in sorted(ann.glob("*.xml")):
        r = ET.parse(x).getroot()
        s = r.find("size")
        w, h = float(s.findtext("width") or 0), float(s.findtext("height") or 0)
        if not w or not h:
            c["bad_size"] += 1
            continue
        lines = []
        for o in r.iter("object"):
            n = (o.findtext("name") or "").strip()
            names[n] += 1
            if n not in MAP:
                continue
            b = o.find("bndbox")
            x1, y1, x2, y2 = [float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
            lines.append(f"{MAP[n]} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
        (out / f"{x.stem}.txt").write_text("\n".join(lines) + "\n")
        hats = sum(l[0] == "1" for l in lines)
        per_img[x.stem] = {"hat": hats, "head": len(lines) - hats}
    print("raw class names", dict(names), dict(c))
    print("images", len(per_img), "with hats", sum(v["hat"] > 0 for v in per_img.values()),
          "heads only", sum(v["hat"] == 0 for v in per_img.values()))
    print("sample names", sorted(per_img)[:3], sorted(per_img)[-3:])
    missing = sum(not (imgs / f"{k}.jpg").exists() for k in per_img)
    print("missing images", missing, "imgs dir", imgs)
    print("ImageSets", [p.name for p in (ann.parent / "ImageSets" / "Main").iterdir()])
    (DEST / "per_image.json").write_text(json.dumps(per_img))


if __name__ == "__main__":
    sys.exit(main())
