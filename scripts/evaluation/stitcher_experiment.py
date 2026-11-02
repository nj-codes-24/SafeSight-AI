"""Reconnect broken tracks by position and size only: no appearance, face or identity features are used."""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class TrackStitcher:
    """Maps tracker IDs to steadier worker IDs. A new track takes over a recently lost one if it appears where that was heading."""
    max_gap: int = 60  # frames a lost track stays available
    reach: float = 0.6  # allowed centre distance, in box heights
    size_ratio: float = 1.6  # allowed height change
    next_id: int = 1
    links: dict = field(default_factory=dict)  # tracker id -> worker id
    last: dict = field(default_factory=dict)  # worker id -> (frame, centre, height, velocity)
    merges: list = field(default_factory=list)

    def update(self, frame_idx, persons):
        """persons: [(track_id, xyxy, conf)]. Returns the same list with worker IDs."""
        active = {self.links[p[0]] for p in persons if p[0] in self.links}
        out = []
        for tid, box, conf in persons:
            c = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            h = float(box[3] - box[1])
            if tid not in self.links:
                self.links[tid] = self._match(frame_idx, c, h, active, tid)
                active.add(self.links[tid])
            wid = self.links[tid]
            prev = self.last.get(wid)
            v = np.zeros(2)
            if prev is not None and frame_idx > prev[0]:
                v = 0.8 * prev[3] + 0.2 * (c - prev[1]) / (frame_idx - prev[0])
            self.last[wid] = (frame_idx, c, h, v)
            out.append((wid, box, conf))
        return out

    def _match(self, frame_idx, c, h, active, tid):
        best, best_d = None, None
        for wid, (f, pc, ph, v) in self.last.items():
            gap = frame_idx - f
            if wid in active or gap <= 0 or gap > self.max_gap or not 1 / self.size_ratio <= h / max(ph, 1) <= self.size_ratio:
                continue
            d = float(np.linalg.norm(c - (pc + v * min(gap, 15)))) / max(ph, 1)
            if d <= self.reach and (best_d is None or d < best_d):
                best, best_d = wid, d
        if best is not None:
            self.merges.append({"frame": frame_idx, "worker": best, "tracker_id": tid, "distance": round(best_d, 2)})
            return best
        self.next_id += 1
        return self.next_id - 1
