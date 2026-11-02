"""M2 and M5 side by side on worksite clips, with head boxes coloured by class, for judging by eye."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, ".")
from ultralytics import YOLO

A, B = YOLO("models/candidates/m2_fallback.pt"), YOLO("runs/m5_sh17_ft/checkpoints/best_good.pt")
tot = {}
out = Path("reports/diagnostics/m2_vs_m5"); out.mkdir(parents=True, exist_ok=True)
for c in json.loads(Path("data/demo/demo_clips.json").read_text(encoding="utf-8")):
    cap = cv2.VideoCapture("data/demo/" + c["file"]); n = int(cap.get(7)); rows = []; cnt = {"m2": [0, 0, 0], "m5": [0, 0, 0]}
    for i in range(n):
        ok, f = cap.read()
        if not ok: break
        pair = []
        for nm, m in (("m2", A), ("m5", B)):
            r = m.predict(f, conf=.3, imgsz=640, verbose=False, device=0)[0]; v = f.copy()
            for k, b, p in zip(r.boxes.cls.cpu().numpy().astype(int), r.boxes.xyxy.cpu().numpy().astype(int), r.boxes.conf.cpu().numpy()):
                cnt[nm][k] += 1
                if k:
                    col = (0, 255, 0) if k == 1 else (0, 0, 255)
                    cv2.rectangle(v, tuple(b[:2]), tuple(b[2:]), col, 2); cv2.putText(v, f"{p:.2f}", (b[0], b[1] - 3), 0, .5, col, 1)
            pair.append(cv2.resize(v, (640, int(f.shape[0] * 640 / f.shape[1]))))
        if i in [int(n * x) for x in (.15, .5, .85)]: rows.append(np.hstack(pair))
    cv2.imwrite(str(out / (Path(c["file"]).stem + ".jpg")), np.vstack(rows)); tot[c["file"]] = cnt; print(c["file"], cnt, flush=True)
json.dump(tot, open(out / "counts.json", "w"), indent=1)