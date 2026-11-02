import sys
from pathlib import Path

import cv2
import numpy as np

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for name in sys.argv[2:]:
    p = Path("data/demo/candidates") / name
    c = cv2.VideoCapture(str(p)); n = min(int(c.get(7)), 1500); cells = []
    for f in np.linspace(0, n - 1, 6).astype(int):
        c.set(1, int(f)); ok, im = c.read()
        if ok: cells.append(cv2.resize(im, (640, int(im.shape[0] * 640 / im.shape[1]))))
    h = min(x.shape[0] for x in cells); cells = [x[:h] for x in cells]
    cv2.imwrite(str(out / f"{p.stem}.jpg"), np.vstack([np.hstack(cells[i:i + 3]) for i in range(0, 6, 3)])); print(name, n, c.get(5))