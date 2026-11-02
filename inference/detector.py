"""Load the trained model and track workers with ByteTrack; PPE classes are detected per frame."""
import os
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402
from ultralytics.trackers.byte_tracker import BYTETracker  # noqa: E402
from ultralytics.utils import YAML, IterableSimpleNamespace  # noqa: E402

from inference.ppe_association import Detection  # noqa: E402

DEFAULT_WEIGHTS = ROOT / "models" / "best.pt"
TRACKER_CFG = ROOT / "inference" / "bytetrack_safesight.yaml"
LOW_CONF = 0.1  # ByteTrack uses low-score boxes to keep a track alive through blur and occlusion


class Detector:
    def __init__(self, weights=DEFAULT_WEIGHTS, imgsz=640, device=None):
        self.model = YOLO(str(weights))
        self.names = self.model.names
        self.imgsz = imgsz
        self.device = device if device is not None else (0 if torch.cuda.is_available() else "cpu")
        self.person_id = next(k for k, v in self.names.items() if v == "person")
        self.tracker = None
        self.reset()

    def reset(self):
        cfg = YAML.load(TRACKER_CFG)
        self.new_track_conf = cfg["new_track_thresh"]
        self.tracker = BYTETracker(IterableSimpleNamespace(**cfg))

    def track(self, frame, person_conf=0.35, ppe_conf=0.3, no_helmet_conf=None):
        """Returns ([(track_id, xyxy, conf)], [Detection for helmet / no_helmet]). Only persons enter the tracker."""
        r = self.model.predict(frame, conf=LOW_CONF, imgsz=self.imgsz, device=self.device, verbose=False)[0]
        boxes = r.boxes.cpu().numpy()
        is_person = boxes.cls.astype(int) == self.person_id
        self.tracker.args.track_high_thresh = person_conf
        self.tracker.args.new_track_thresh = max(self.new_track_conf, person_conf + 0.1)
        tracks = self.tracker.update(boxes[is_person], frame)
        persons = [(int(t[4]), np.asarray(t[:4], dtype=np.float64), float(t[5])) for t in tracks]
        heads = [Detection(np.asarray(b), float(c), self.names[int(k)])
                 for b, c, k in zip(boxes.xyxy[~is_person], boxes.conf[~is_person], boxes.cls[~is_person])
                 if c >= (no_helmet_conf if no_helmet_conf and self.names[int(k)] == "no_helmet" else ppe_conf)]
        return persons, heads
