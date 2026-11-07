"""Turn confirmed state changes into one incident each, with a cooldown and an evidence screenshot."""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from intelligence.risk import LEVELS

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "logs" / "incidents" / "evidence"
NO_HELMET, ZONE = "NO_HELMET", "ZONE_INTRUSION"


@dataclass
class IncidentManager:
    db: object
    session_id: str
    camera_id: str = "CAM-01"
    cooldown_s: float = 30.0  # in video time, so results match however fast the video is processed
    open: dict = field(default_factory=dict)  # (type, track, zone) -> incident id
    last_fired: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    new_alerts: list = field(default_factory=list)
    recent: dict = field(default_factory=dict)  # (type, track, zone) -> (video time, x, y) where it was raised
    same_place: float = 1.0  # box heights; a new ID this close to a lost track's incident is treated as the same worker
    suppressed: int = 0
    # Optional risk assessment (intelligence/risk.py): assessor(kind, zone, conf, exposure_s) -> Assessment. Without it the
    # manager behaves exactly as before. min_exposure_s is the confirmation time a state needed before it was raised.
    assessor: object = None
    min_exposure_s: float = 0.0
    assessed: dict = field(default_factory=dict)  # (type, track, zone) -> (incident id, video time raised, conf, Assessment)
    escalations: list = field(default_factory=list)
    evidence_dir: Path | None = None  # None: the module-level EVIDENCE_DIR
    # Optional listener(event, incident_id, type, track, zone, video_t) for "opened" and "closed" (runtime/worker.py).
    listener: object = None

    def _repeat_of_lost_track(self, kind, zone, track_id, box, video_t, active):
        """True if a track no longer visible raised this incident close by, so this is the same worker under a new ID."""
        if box is None:
            return False
        cx, cy, h = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, box[3] - box[1]
        for (k, tid, z), (t, x, y) in self.recent.items():
            if k == kind and z == zone and tid != track_id and tid not in active and video_t - t < self.cooldown_s \
                    and np.hypot(cx - x, cy - y) < self.same_place * h:
                return True
        return False

    def raise_incident(self, kind, track_id, conf, video_t, frame, zone=None, box=None, active=()):
        key = (kind, track_id, zone)
        if key in self.open:
            return None
        last = self.last_fired.get(key)
        if last is not None and video_t - last < self.cooldown_s:
            return None
        if self._repeat_of_lost_track(kind, zone, track_id, box, video_t, active):
            self.suppressed += 1
            return None
        if box is not None:
            self.recent[key] = (video_t, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        iid = self.db.add(kind, track_id, round(float(conf), 3), self.camera_id, self.session_id, zone, round(video_t, 2))
        path = self._evidence(iid, frame)
        self.db.set_evidence(iid, path)
        self.open[key] = iid
        self.last_fired[key] = video_t
        self.counts[track_id] = self.counts.get(track_id, 0) + 1
        alert = {"incident_id": iid, "type": kind, "worker_id": track_id, "zone": zone, "video_t": round(video_t, 1),
                 "evidence": str(path), "repeat": self.counts[track_id] > 1}
        if self.assessor:
            a = self.assessor(kind, zone, conf, self.min_exposure_s)
            self.db.save_assessment(iid, a.to_dict())
            self.assessed[key] = (iid, video_t, conf, a)
            alert.update(hazard=a.hazard, severity=a.severity, risk=a.level, evidence_quality=a.evidence)
        self.new_alerts.append(alert)
        if self.listener:
            self.listener("opened", iid, kind, track_id, zone, video_t)
        return alert

    def _reassess(self, key, video_t):
        """Assess again with the exposure so far; save it, and record an escalation if the risk level rose."""
        iid, t0, conf, before = self.assessed[key]
        after = self.assessor(key[0], key[2], conf, self.min_exposure_s + max(0.0, video_t - t0))
        rose = LEVELS.index(after.level) > LEVELS.index(before.level)
        if rose:
            self.escalations.append({"incident_id": iid, "type": key[0], "worker_id": key[1], "zone": key[2],
                                     "video_t": round(video_t, 1), "from": before.level, "to": after.level})
        return iid, t0, conf, after, rose

    def tick(self, video_t):
        """Called once per frame: open incidents escalate as exposure grows (recorded, not yet notified)."""
        for key in [k for k in self.assessed if k in self.open]:
            iid, t0, conf, after, rose = self._reassess(key, video_t)
            if rose:
                self.db.save_assessment(iid, after.to_dict(), escalated_at_s=round(video_t, 2))
                self.assessed[key] = (iid, t0, conf, after)

    def close(self, kind, track_id, video_t, zone=None):
        key = (kind, track_id, zone)
        iid = self.open.pop(key, None)
        if iid:
            self.db.close_incident(iid)
            self.last_fired[key] = video_t  # the cooldown runs from the end of the incident
            if key in self.assessed:  # final exposure; it includes the lost-track wait when a track was lost
                iid, _, _, after, rose = self._reassess(key, video_t)
                self.db.save_assessment(iid, after.to_dict(), escalated_at_s=round(video_t, 2) if rose else None)
                del self.assessed[key]
            if self.listener:
                self.listener("closed", iid, kind, track_id, zone, video_t)

    def close_track(self, track_id, video_t):
        for key in [k for k in self.open if k[1] == track_id]:
            self.close(key[0], track_id, video_t, key[2])

    def close_all(self, video_t):
        for key in list(self.open):
            self.close(key[0], key[1], video_t, key[2])

    def _evidence(self, iid, frame) -> Path:
        d = (self.evidence_dir or EVIDENCE_DIR) / self.session_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{iid}.jpg"  # the id is unique, so older evidence is never overwritten
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return path

    def drain_alerts(self) -> list:
        a, self.new_alerts = self.new_alerts, []
        return a

    def drain_escalations(self) -> list:
        e, self.escalations = self.escalations, []
        return e

    @staticmethod
    def new_session_id() -> str:
        return datetime.now().strftime("S%Y%m%d-%H%M%S")
