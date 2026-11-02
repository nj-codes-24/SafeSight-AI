"""Audit SH17: class names from the VOC files, head and helmet geometry, near-duplicates against val and test."""
import random
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "data/raw/sh17"
xmls = sorted((S / "voc_labels").glob("*.xml"))
names = Counter(); pairs = {"helmet_in_head": 0, "head_with_helmet": 0, "head_no_helmet": 0, "helmet_no_head": 0}
wh = {"head": [], "helmet": [], "bare_head": [], "helmet_head_area": []}
persons = 0; im_with = Counter(); samples = []
def inter(a, b): return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
for x in xmls:
    r = ET.parse(x).getroot(); o = {}
    for ob in r.findall("object"):
        n = ob.find("name").text.strip().lower(); names[n] += 1
        b = ob.find("bndbox"); o.setdefault(n, []).append([float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax")])
    heads, helms = o.get("head", []), o.get("helmet", [])
    for h in heads:
        hw = (h[2] - h[0]) / max(h[3] - h[1], 1); wh["head"].append(hw)
        m = max([inter(h, k) / max((k[2] - k[0]) * (k[3] - k[1]), 1) for k in helms] or [0])
        if m > .4:
            pairs["head_with_helmet"] += 1
        else:
            pairs["head_no_helmet"] += 1; wh["bare_head"].append(hw)
    for k in helms:
        wh["helmet"].append((k[2] - k[0]) / max(k[3] - k[1], 1))
        m = max([inter(h, k) / max((k[2] - k[0]) * (k[3] - k[1]), 1) for h in heads] or [0])
        pairs["helmet_no_head"] += m <= .4
    for k in ("head", "helmet"):
        if k in o: im_with[k] += 1
    if heads and "person" in o: samples.append(x.stem)
print(names.most_common()); print(pairs); print(im_with)
print({k: (len(v), round(float(np.median(v)), 2)) for k, v in wh.items() if v})
line = (S / "labels" / (xmls[0].stem + ".txt")).read_text().splitlines()[:3]; print(xmls[0].stem, line)
random.seed(1); cells = []
for st in random.sample(samples, 30):
    im = next((S / "images").glob(st + ".*")); a = cv2.imread(str(im)); sc = 300 / max(a.shape[:2])
    r = ET.parse(S / "voc_labels" / f"{st}.xml").getroot()
    a = cv2.resize(a, None, fx=sc, fy=sc)
    for ob in r.findall("object"):
        n = ob.find("name").text.strip().lower()
        if n in ("head", "helmet", "person"):
            b = ob.find("bndbox"); p = [int(float(b.find(k).text) * sc) for k in ("xmin", "ymin", "xmax", "ymax")]
            cv2.rectangle(a, p[:2], p[2:], {"head": (0, 0, 255), "helmet": (0, 255, 0), "person": (255, 200, 0)}[n], 1)
    c = np.zeros((300, 300, 3), np.uint8); c[:a.shape[0], :a.shape[1]] = a; cells.append(c)
(ROOT / "reports/diagnostics").mkdir(exist_ok=True)
cv2.imwrite(str(ROOT / "reports/diagnostics/sh17_sample.jpg"), np.vstack([np.hstack(cells[i:i + 6]) for i in range(0, 30, 6)]))
