"""Restricted-zone logic: a track is inside when its foot point (bottom-centre of the box) is in the polygon."""
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Zone:
    name: str
    polygon: list  # normalised [[x, y], ...] in 0-1, so a zone survives a change of resolution

    def pixels(self, w: int, h: int) -> np.ndarray:
        return (np.array(self.polygon, dtype=np.float32) * [w, h]).astype(np.int32)

    def contains(self, pt, w: int, h: int) -> bool:
        return cv2.pointPolygonTest(self.pixels(w, h).astype(np.float32), (float(pt[0]), float(pt[1])), False) >= 0


def validate_polygon(points) -> list:
    pts = [[float(x), float(y)] for x, y in points]
    if len(pts) < 3:
        raise ValueError("a zone needs at least 3 points")
    if not all(0 <= v <= 1 for p in pts for v in p):
        raise ValueError("zone coordinates must be normalised to 0-1")
    a = np.array(pts)
    area = 0.5 * abs(np.dot(a[:, 0], np.roll(a[:, 1], 1)) - np.dot(a[:, 1], np.roll(a[:, 0], 1)))
    if area < 1e-4:
        raise ValueError("zone has no area")
    return pts


@dataclass
class ZoneMonitor:
    """Debounced entry/exit per (track, zone). entry_frames and exit_frames stop jitter at the edge re-firing."""
    zones: list
    entry_frames: int = 8
    exit_frames: int = 15
    state: dict = field(default_factory=dict)

    def update(self, track_id, foot, w, h) -> list[tuple[str, str]]:
        events = []
        for z in self.zones:
            s = self.state.setdefault((track_id, z.name), {"inside": False, "in": 0, "out": 0})
            if z.contains(foot, w, h):
                s["in"], s["out"] = s["in"] + 1, 0
                if not s["inside"] and s["in"] >= self.entry_frames:
                    s["inside"] = True
                    events.append(("enter", z.name))
            else:
                s["out"], s["in"] = s["out"] + 1, 0
                if s["inside"] and s["out"] >= self.exit_frames:
                    s["inside"] = False
                    events.append(("exit", z.name))
        return events

    def inside(self, track_id) -> list[str]:
        return [z.name for z in self.zones if self.state.get((track_id, z.name), {}).get("inside")]

    def drop(self, track_id) -> list[str]:
        """Forget a lost track; return zones it was still inside so the caller can close the intrusion."""
        left = self.inside(track_id)
        for z in self.zones:
            self.state.pop((track_id, z.name), None)
        return left
