"""Find near-duplicates across splits/datasets with CNN embeddings (robust to crop, tint and small rotations)."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.models import ResNet18_Weights, resnet18

EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


class Images(Dataset):
    def __init__(self, paths, tf):
        self.paths, self.tf = paths, tf

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        return self.tf(Image.open(self.paths[i]).convert("RGB"))


@torch.inference_mode()
def embed(paths, batch=128):
    weights = ResNet18_Weights.DEFAULT
    model = resnet18(weights=weights)
    model.fc = torch.nn.Identity()
    model = model.eval().cuda()
    dl = DataLoader(Images(paths, weights.transforms()), batch_size=batch, num_workers=4)
    out = [torch.nn.functional.normalize(model(b.cuda()), dim=1).cpu() for b in dl]
    return torch.cat(out).numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True, help="name=image_dir (repeatable)")
    ap.add_argument("--thresh", type=float, default=0.93)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    names, paths = [], []
    for g in a.group:
        n, d = g.split("=", 1)
        for p in sorted(Path(d).iterdir()):
            if p.suffix.lower() in EXTS:
                names.append(n)
                paths.append(str(p))
    e = embed(paths)
    names_a = np.array(names)
    t = torch.from_numpy(e).cuda()
    pairs = []
    for i in range(0, len(t), 512):
        sim = t[i:i + 512] @ t.T
        for r, c in (sim > a.thresh).nonzero().cpu().numpy():
            r2 = i + int(r)
            if int(c) > r2 and names_a[r2] != names_a[c]:
                pairs.append([paths[r2], paths[int(c)], round(float(sim[r, c]), 4)])
    summary = {}
    for p, q, _ in pairs:
        k = f"{names[paths.index(p)]}<->{names[paths.index(q)]}"
        summary[k] = summary.get(k, 0) + 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"thresh": a.thresh, "summary": summary, "pairs": pairs}, indent=1))
    print(a.thresh, summary, "total", len(pairs))


if __name__ == "__main__":
    main()
