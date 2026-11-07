"""Per-worker helmet state from frame detections. Missing evidence gives UNCERTAIN, never VIOLATION.

Visibility: a head cut off by the image border can look bare because the helmet is outside the frame, so a "no helmet"
detection on a truncated head is not counted as evidence of a missing helmet (a helmet seen on a truncated head still
counts). When the recent window holds no usable head evidence at all, the worker is NOT_OBSERVABLE (reported apart
from UNCERTAIN, where evidence exists but disagrees or is too thin).
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

COMPLIANT, VIOLATION, UNCERTAIN = "COMPLIANT", "VIOLATION", "UNCERTAIN"
NOT_OBSERVABLE = "NOT_OBSERVABLE"  # detail only: state() still returns UNCERTAIN for it, as before
HEAD_REGION = 0.40  # top fraction of the person box where a head may be
EDGE = "edge"  # vote kind for a "no helmet" box on a head cut off by the image border


def head_truncated(head: "Detection | None", w: int, margin: float = 2.0) -> bool:
    """True if the head box touches the top, left or right border (boxes are clipped to the image). The bottom border
    is not a head problem."""
    if head is None:
        return False
    x1, y1, x2, _ = head.xyxy
    return bool(y1 <= margin or x1 <= margin or x2 >= w - margin)


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

    def update(self, track_id: int, head: Detection | None, truncated: bool = False) -> tuple[str, float]:
        v = self.votes.setdefault(track_id, deque(maxlen=self.window))
        if head is not None and truncated and head.cls == "no_helmet":
            v.append((EDGE, head.conf))  # neither "no" nor "yes": the helmet may be outside the frame
        else:
            v.append((head.cls, head.conf) if head else (None, 0.0))
        return self.state(track_id)

    def detail(self, track_id: int) -> str:
        """state() plus NOT_OBSERVABLE: UNCERTAIN with no usable head evidence in the window."""
        s = self.state(track_id)[0]
        if s != UNCERTAIN:
            return s
        v = self.votes.get(track_id) or ()
        return NOT_OBSERVABLE if not any(k in ("helmet", "no_helmet") for k, _ in v) else UNCERTAIN

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
