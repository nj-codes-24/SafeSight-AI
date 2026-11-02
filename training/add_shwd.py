"""Build merged_shwd: merged_clean plus selected SHWD images in TRAIN ONLY, so val and test stay identical.

All helmet images are used. Heads-only images are mostly classrooms (SCUT-HEAD), so only a small sample with few
heads is kept as a domain-limited source of bare heads. Images resembling any val/test image are dropped.
"""
import json
import random
import shutil
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from find_near_duplicates import embed  # noqa: E402
from prepare_data import THRESH, mask_copy, refine  # noqa: E402
from pseudo_label import run_teacher  # noqa: E402

SRC = ROOT / "data" / "processed" / "merged_clean"
DST = ROOT / "data" / "processed" / "merged_shwd"
SHWD = ROOT / "data" / "raw" / "shwd"
HEADS_ONLY_SAMPLE = 500
MAX_HEADS = 12


def main():
    per = json.loads((SHWD / "per_image.json").read_text())
    imgs = SHWD / "VOC2028" / "JPEGImages"
    rng = random.Random(42)
    hats = [k for k, v in per.items() if v["hat"] > 0]
    heads = sorted(k for k, v in per.items() if v["hat"] == 0 and 1 <= v["head"] <= MAX_HEADS)
    chosen = hats + rng.sample(heads, min(HEADS_ONLY_SAMPLE, len(heads)))
    paths = [str(imgs / f"{k}.jpg") for k in chosen]

    held = [str(p) for s in ("val", "test") for p in sorted((SRC / "images" / s).iterdir())]
    train = [str(p) for p in sorted((SRC / "images" / "train").iterdir())]
    a = torch.from_numpy(embed(paths)).cuda()
    leak = ((a @ torch.from_numpy(embed(held)).cuda().T).max(1).values > THRESH).cpu().numpy()
    dup = ((a @ torch.from_numpy(embed(train)).cuda().T).max(1).values > 0.97).cpu().numpy()
    keep = [k for k, l, d in zip(chosen, leak, dup) if not l and not d]
    print(f"selected {len(chosen)}, dropped {int(leak.sum())} near val/test, {int(dup.sum())} already in train, kept {len(keep)}")

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    teacher = run_teacher([str(imgs / f"{k}.jpg") for k in keep])
    masked = 0
    for k in keep:
        img = imgs / f"{k}.jpg"
        lines = [l for l in (SHWD / "yolo_labels" / f"{k}.txt").read_text().splitlines() if l.strip()]
        lines, unlabelled = refine(lines, teacher.get(str(img), []))
        dst = DST / "images" / "train" / f"shwd_{k}.jpg"
        if unlabelled:
            mask_copy(img, dst, unlabelled)
            masked += len(unlabelled)
        else:
            shutil.copyfile(img, dst)
        (DST / "labels" / "train" / f"shwd_{k}.txt").write_text("\n".join(lines) + "\n")
    y = (DST / "dataset.yaml").read_text().replace("merged_clean", "merged_shwd")
    (DST / "dataset.yaml").write_text(y)
    counts = {0: 0, 1: 0, 2: 0}
    for f in (DST / "labels" / "train").glob("*.txt"):
        for l in f.read_text().splitlines():
            counts[int(l.split()[0])] += 1
    rep = {"selected": len(chosen), "dropped_near_val_test": int(leak.sum()), "dropped_in_train": int(dup.sum()),
           "kept": len(keep), "masked_heads": masked, "train_images": len(list((DST / "images" / "train").iterdir())),
           "train_instances": {"person": counts[0], "helmet": counts[1], "no_helmet": counts[2]}}
    (ROOT / "reports" / "prepare_merged_shwd.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
