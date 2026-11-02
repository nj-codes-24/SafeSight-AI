"""Measure tracking quality on the demo clips: ID fragmentation, duplicate boxes, speed and GPU memory."""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from inference.config import load_config  # noqa: E402
from inference.detector import Detector  # noqa: E402

DUP_IOU = 0.7
cfg = load_config()
det = Detector()
res = {}
for c in json.loads((ROOT / "data/demo/demo_clips.json").read_text(encoding="utf-8")):
    det.reset()
    torch.cuda.reset_peak_memory_stats()
    cap = cv2.VideoCapture(str(ROOT / "data/demo" / c["file"]))
    lengths, counts, dup_frames, n, spent = Counter(), [], 0, 0, 0.0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        t = time.perf_counter()
        persons, _ = det.track(f, cfg["person_conf"], cfg["ppe_conf"])
        spent += time.perf_counter() - t
        boxes = [p[1] for p in persons]
        for p in persons:
            lengths[p[0]] += 1
        counts.append(len(persons))
        n += 1
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
                union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
                if inter / union > DUP_IOU:
                    dup_frames += 1
                    break
    cap.release()
    fps = c["fps"]
    res[c["file"]] = {"frames": n, "ids": len(lengths), "max_concurrent": max(counts), "median_concurrent": int(np.median(counts)),
                      "short_ids_under_1s": sum(v < fps for v in lengths.values()), "frames_with_overlap_iou_gt_0.7": dup_frames,
                      "detect_track_fps": round(n / spent, 1), "gpu_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20)}
    print(c["file"], res[c["file"]], flush=True)
(ROOT / "reports" / "tracking_metrics.json").write_text(json.dumps(res, indent=1))
