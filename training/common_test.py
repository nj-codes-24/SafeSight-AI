"""Build test slices from unrefined labels: Construction-PPE official test verbatim, Mendeley test with human labels only."""
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "merged_raw"
OUT = ROOT / "data" / "processed" / "common_test"
for src in ("cppe", "mendeley"):
    root = OUT / src
    (root / "images" / "test").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "test").mkdir(parents=True, exist_ok=True)
    n = 0
    for p in (SRC / "images" / "test").glob(src + "_*"):
        shutil.copyfile(p, root / "images" / "test" / p.name)
        shutil.copyfile(SRC / "labels" / "test" / f"{p.stem}.txt", root / "labels" / "test" / f"{p.stem}.txt")
        n += 1
    (root / "d.yaml").write_text(yaml.safe_dump({"path": str(root), "train": "images/test", "val": "images/test", "test": "images/test",
                                                 "names": {0: "person", 1: "helmet", 2: "no_helmet"}}))
    print(src, n)
