"""Per-worker helmet state from frame detections. Missing evidence gives UNCERTAIN, never VIOLATION."""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

COMPLIANT, VIOLATION, UNCERTAIN = "COMPLIANT", "VIOLATION", "UNCERTAIN"
HEAD_REGION = 0.40  # top fraction of the person box where a head may be


@dataclass
class Detection:
    xyxy: np.ndarray
    conf: float
    cls: str


def head_score(person: np.ndarray, head: np.ndarray) -> float:
    """Fit of a head box to a person: 0 if outside the upper body, else closer to the top-centre scores higher."""
    x1, y1, x2, y2 = person
    w, h = max(x2 - x1, 1), max(y2 - y1, 1)
    cx, cy = (head[0] + head[2]) / 2, (head[1] + head[3]) / 2
    if not (x1 - 0.1 * w <= cx <= x2 + 0.1 * w and y1 - 0.1 * h <= cy <= y1 + HEAD_REGION * h):
        return 0.0
    return 1.0 - abs(cx - (x1 + x2) / 2) / w - abs(cy - y1) / (2 * h)


def assign_heads(persons: list[np.ndarray], heads: list[Detection]) -> list[Detection | None]:
    """Greedy one-to-one match, best fit first, so one helmet cannot satisfy two overlapping workers."""
    pairs = [(head_score(p, h.xyxy) * h.conf, i, j) for i, p in enumerate(persons) for j, h in enumerate(heads)]
    out, used = [None] * len(persons), set()
    for s, i, j in sorted(pairs, reverse=True):
        if s > 0 and out[i] is None and j not in used:
            out[i] = heads[j]
            used.add(j)
    return out


@dataclass
class HelmetStateTracker:
    """Rolling evidence per track. A state needs enough agreeing frames in the window, else UNCERTAIN."""
    window: int = 30
    min_votes: int = 8
    ratio: float = 0.7
    votes: dict = field(default_factory=dict)

    def update(self, track_id: int, head: Detection | None) -> tuple[str, float]:
        v = self.votes.setdefault(track_id, deque(maxlen=self.window))
        v.append((head.cls, head.conf) if head else (None, 0.0))
        return self.state(track_id)

    def state(self, track_id: int) -> tuple[str, float]:
        v = self.votes.get(track_id)
        if not v:
            return UNCERTAIN, 0.0
        no = [c for k, c in v if k == "no_helmet"]
        yes = [c for k, c in v if k == "helmet"]
        total = len(no) + len(yes)
        if total < self.min_votes:
            return UNCERTAIN, 0.0
        if len(no) / total >= self.ratio:
            return VIOLATION, float(np.mean(no))
        if len(yes) / total >= self.ratio:
            return COMPLIANT, float(np.mean(yes))
        return UNCERTAIN, 0.0

    def drop(self, track_id: int) -> None:
        self.votes.pop(track_id, None)
