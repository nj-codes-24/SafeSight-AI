"""Record what the frozen model and tracker produce on every frame of the evaluated clips, so the logic after the
detector (helmet vote, zones, incident lifecycle, policy) can be replayed deterministically without a GPU.

    python scripts/validation/record_traces.py [--clips c01,c08] [--workers 4]

Writes reports/validation/traces/<clip>.json.gz (git-ignored: derived model output): per frame the ByteTrack person
tracks after the person threshold, and every head box down to the model's 0.10 floor (the replay applies the frozen
PPE thresholds itself). Frames are read in order exactly as the offline runtime reads them. Model output only: never
give these files to annotators.
"""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_OFFLINE", "true")
OUT = ROOT / "reports" / "validation" / "traces"


def record(clip_id, path):
    import cv2
    import numpy as np

    from inference.config import DEFAULTS
    from inference.detector import Detector

    det = Detector()
    cap = cv2.VideoCapture(str(ROOT / path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames, size = [], None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        size = frame.shape[1], frame.shape[0]
        boxes = det.predict(frame)
        is_person = boxes.cls.astype(int) == det.person_id
        det.tracker.args.track_high_thresh = DEFAULTS["person_conf"]
        det.tracker.args.new_track_thresh = max(det.new_track_conf, DEFAULTS["person_conf"] + 0.1)
        tracks = det.tracker.update(boxes[is_person], frame)
        persons = [[int(t[4]), *[round(float(v), 1) for v in t[:4]], round(float(t[5]), 3)] for t in tracks]
        heads = [[*[round(float(v), 1) for v in b], round(float(c), 3), det.names[int(k)]]
                 for b, c, k in zip(boxes.xyxy[~is_person], boxes.conf[~is_person], boxes.cls[~is_person])]
        frames.append([persons, heads])
    cap.release()
    model = hashlib.sha256((ROOT / "models" / "best.pt").read_bytes()).hexdigest().upper()
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"{clip_id}.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"clip_id": clip_id, "file": path, "fps": fps, "width": size[0], "height": size[1], "model_sha256": model,
                   "person_conf": DEFAULTS["person_conf"], "frames": frames}, f, separators=(",", ":"))
    print(f"{clip_id}: {len(frames)} frames", flush=True)
    del np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--one", nargs=2, metavar=("CLIP", "PATH"))
    a = ap.parse_args()
    if a.one:
        return record(*a.one)
    from intelligence.annotations import load_set

    labels = load_set(ROOT / "reports" / "validation" / "annotations" / "m2-provisional-v1")
    todo = [(c, lab["file"]) for c, lab in labels.items() if not a.clips or c in a.clips.split(",")]
    todo.sort(key=lambda x: -(ROOT / x[1]).stat().st_size)  # longest first
    running = []
    while todo or running:
        while todo and len(running) < a.workers:
            c, p = todo.pop(0)
            running.append(subprocess.Popen([sys.executable, __file__, "--one", c, p], cwd=ROOT))
        running[0].wait()
        if running[0].returncode:
            raise SystemExit(f"recording failed (exit {running[0].returncode})")
        running.pop(0)


if __name__ == "__main__":
    main()
