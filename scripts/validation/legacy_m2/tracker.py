"""Frame-by-frame pipeline: detect and track, resolve PPE state, watch zones, record incidents, annotate."""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from database.database import IncidentDB
from inference.config import DEFAULTS, load_config, save_config  # noqa: F401  (re-exported)
from intelligence.risk import RiskEngine, load_policy
from intelligence.taxonomy import ZONE_KINDS, hazard_for
from scripts.validation.legacy_m2.incident_manager import NO_HELMET, ZONE, IncidentManager
from scripts.validation.legacy_m2.ppe_association import COMPLIANT, UNCERTAIN, VIOLATION, HelmetStateTracker, assign_heads
from scripts.validation.legacy_m2.zone_monitor import Zone, ZoneMonitor

if TYPE_CHECKING:  # imported lazily below: the detector pulls in torch, which the headless runtime's tests do without
    from inference.detector import Detector

COLORS = {COMPLIANT: (94, 197, 34), VIOLATION: (60, 60, 239), UNCERTAIN: (11, 158, 245)}


@dataclass
class Stats:
    frames: int = 0
    tracked: dict = field(default_factory=dict)  # track id -> last state
    seen_ids: set = field(default_factory=set)
    fps: float = 0.0
    final: dict = field(default_factory=dict)  # track id -> last state, kept after the track is lost
    age: dict = field(default_factory=dict)  # track id -> frames seen
    min_frames: int = 25  # a track counts as confirmed after this many frames (1 s of video); a track is not a person

    def confirmed(self) -> list:
        return [k for k, v in self.age.items() if v >= self.min_frames]

    def snapshot(self, incidents) -> dict:
        s = list(self.tracked.values())
        c, v = s.count(COMPLIANT), s.count(VIOLATION)
        return {"frames": self.frames, "tracked_now": len(s), "compliant": c, "violation": v, "uncertain": s.count(UNCERTAIN),
                "track_ids": len(self.seen_ids), "confirmed_tracks": len(self.confirmed()), "compliance_rate": round(100 * c / (c + v), 1) if c + v else None,
                "fps": round(self.fps, 1), "incidents": incidents}


class Pipeline:
    """One camera's state: tracker, PPE votes, zones and incidents. Not thread-safe; use one per camera and thread.

    annotate=False draws boxes only on frames that raise an incident (their evidence); other frames are returned as is.
    """

    def __init__(self, detector: "Detector", fps: float, cfg=None, camera_id="CAM-01", zones=None, db=None, session_id=None,
                 policy=None, evidence_dir=None, listener=None, annotate=True):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.det = detector
        self.det.reset()
        self.fps = fps or 25.0
        confirm = max(2, int(self.cfg["confirm_seconds"] * self.fps))
        self.helmets = HelmetStateTracker(window=max(confirm * 3, 15), min_votes=confirm)
        zones = zones if zones is not None else self.cfg.get("zones", {}).get(camera_id, [])
        self.zones = ZoneMonitor([Zone(z["name"], z["polygon"], z.get("kind", "restricted")) for z in zones],
                                 entry_frames=confirm, exit_frames=confirm * 2)
        self.zone_kind = {z.name: z.kind for z in self.zones.zones}
        self.alert_zones = {n for n, k in self.zone_kind.items() if ZONE_KINDS[k].person_entry}  # person entry is the hazard
        self.session_id = session_id or IncidentManager.new_session_id()
        self.db = db or IncidentDB()
        self.risk = RiskEngine(policy if policy is not None else load_policy())
        self.incidents = IncidentManager(self.db, self.session_id, camera_id, cooldown_s=self.cfg["cooldown_seconds"],
                                         assessor=self._assess, min_exposure_s=self.cfg["confirm_seconds"],
                                         evidence_dir=evidence_dir, listener=listener)
        self.stats = Stats(min_frames=max(1, round(self.fps)))
        self.last_seen = {}
        self.t_prev = None
        self.annotate = annotate
        self.id_offset = self.max_tid = 0  # after a track reset, new tracker IDs continue past every ID already issued
        self.t_last = None

    def _assess(self, kind, zone, conf, exposure_s):
        return self.risk.assess(hazard_for(kind, self.zone_kind.get(zone)).code, exposure_s, conf, zone)

    def process(self, frame, t=None):
        """Annotates and returns the frame. Evidence screenshots show the annotated view at the moment of confirmation.

        t is the frame time in seconds; by default frames are assumed evenly spaced at fps. Live sources pass monotonic
        time so that exposure and cooldowns stay correct when frames are skipped.
        """
        h, w = frame.shape[:2]
        fi = self.stats.frames
        t = fi / self.fps if t is None else t
        persons, heads = self.det.track(frame, self.cfg["person_conf"], self.cfg["ppe_conf"], self.cfg.get("no_helmet_conf"))
        if self.id_offset:
            persons = [(tid + self.id_offset, box, conf) for tid, box, conf in persons]
        self.max_tid = max([self.max_tid] + [p[0] for p in persons])
        matched = assign_heads([p[1] for p in persons], heads)
        pending, rows = [], []
        for (tid, box, conf), head in zip(persons, matched):
            state, sconf = self.helmets.update(tid, head)
            foot = ((box[0] + box[2]) / 2, box[3])
            self.last_seen[tid] = fi
            self.stats.seen_ids.add(tid)
            self.stats.age[tid] = self.stats.age.get(tid, 0) + 1
            if state != UNCERTAIN or tid not in self.stats.final:
                self.stats.final[tid] = state
            rows.append((tid, box, state, foot))
            if state == VIOLATION:
                pending.append((NO_HELMET, tid, sconf, None, box))
            elif state == COMPLIANT:
                self.incidents.close(NO_HELMET, tid, t)
            for ev, zone in self.zones.update(tid, foot, w, h):
                if zone not in self.alert_zones:
                    continue  # walkways and keep-clear areas: a person there is not the hazard
                if ev == "enter":
                    pending.append((ZONE, tid, conf, zone, box))
                else:
                    self.incidents.close(ZONE, tid, t, zone)
        self._expire(fi, t)
        self.stats.tracked = {r[0]: r[2] for r in rows}  # visible now; lost tracks stay remembered but are not counted
        out = self._annotate(frame.copy(), rows, heads) if self.annotate or pending else frame
        active = {r[0] for r in rows}
        for kind, tid, c, zone, box in pending:
            self.incidents.raise_incident(kind, tid, c, t, out, zone, box, active)
        self.incidents.tick(t)
        self.t_last = t
        self.stats.frames += 1
        now = time.perf_counter()
        if self.t_prev:
            inst = 1 / max(now - self.t_prev, 1e-6)
            self.stats.fps = inst if not self.stats.fps else 0.9 * self.stats.fps + 0.1 * inst
        self.t_prev = now
        return out

    def reset_tracks(self, t=None):
        """A gap in the video (stream outage, looping file restart): every track is lost at time t (default: the last
        processed frame), and the tracker restarts with IDs that continue past those already issued in this session."""
        t = self.t_last if t is None else t
        for tid in list(self.last_seen):
            self.zones.drop(tid)
            self.helmets.drop(tid)
            if t is not None:
                self.incidents.close_track(tid, t)
        self.last_seen.clear()
        self.stats.tracked = {}
        self.id_offset = self.max_tid
        self.det.reset()

    def _expire(self, fi, t):
        limit = self.cfg["lost_track_seconds"] * self.fps
        for tid in [k for k, v in self.last_seen.items() if fi - v > limit]:
            self.zones.drop(tid)
            self.helmets.drop(tid)
            self.incidents.close_track(tid, t)
            del self.last_seen[tid]

    def _annotate(self, im, rows, heads):
        h, w = im.shape[:2]
        scale = max(0.45, min(w, h) / 1100)
        for z in self.zones.zones:
            pts = z.pixels(w, h)
            occupied = z.name in self.alert_zones and any(z.name in self.zones.inside(r[0]) for r in rows)
            col = (60, 60, 239) if occupied else (11, 158, 245)
            layer = im.copy()
            cv2.fillPoly(layer, [pts], col)
            cv2.addWeighted(layer, 0.18, im, 0.82, 0, im)
            cv2.polylines(im, [pts], True, col, 2, cv2.LINE_AA)
            cv2.putText(im, z.name, tuple(pts[0] + [6, 20]), 0, scale, col, 2, cv2.LINE_AA)
        for d in heads:
            x1, y1, x2, y2 = d.xyxy.astype(int)
            cv2.rectangle(im, (x1, y1), (x2, y2), (94, 197, 34) if d.cls == "helmet" else (60, 60, 239), 1, cv2.LINE_AA)
        for tid, box, state, foot in rows:
            x1, y1, x2, y2 = box.astype(int)
            col = COLORS[state]
            cv2.rectangle(im, (x1, y1), (x2, y2), col, 2, cv2.LINE_AA)
            label = f"W{tid} {state}" + (" IN ZONE" if self.alert_zones.intersection(self.zones.inside(tid)) else "")
            (tw, th), _ = cv2.getTextSize(label, 0, scale, 1)
            top = max(th + 6, y1)
            cv2.rectangle(im, (x1, top - th - 6), (x1 + tw + 6, top), col, -1)
            cv2.putText(im, label, (x1 + 3, top - 4), 0, scale, (15, 15, 15), 1, cv2.LINE_AA)
            cv2.circle(im, (int(foot[0]), int(foot[1])), 4, col, -1, cv2.LINE_AA)
        return im

    def finish(self, source=None, t=None):
        """Close open incidents (at time t, default the end of the frames) and store the session. Safe to call twice."""
        self.incidents.close_all(self.stats.frames / self.fps if t is None else t)
        keep = self.stats.confirmed()
        f = [self.stats.final[k] for k in keep if k in self.stats.final]
        self.db.save_session(self.session_id, source, self.stats.frames, len(keep), f.count(COMPLIANT),
                             f.count(VIOLATION), f.count(UNCERTAIN), round(self.stats.fps, 1))
        return self.summary()

    def summary(self):
        return self.stats.snapshot(len(self.incidents.last_fired))


def process_video(path, weights=None, out_path=None, cfg=None, zones=None, camera_id="CAM-01", max_frames=None, db=None):
    """Offline run of a whole video; returns the summary and writes an annotated mp4 if out_path is given."""
    from inference.detector import Detector

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pipe = Pipeline(Detector(weights) if weights else Detector(), fps, cfg, camera_id, zones, db)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)) if out_path else None
    t0 = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok or (max_frames and pipe.stats.frames >= max_frames):
            break
        out = pipe.process(frame)
        if writer:
            writer.write(out)
    cap.release()
    if writer:
        writer.release()
    res = pipe.finish(Path(path).name)
    res.update(session_id=pipe.session_id, wall_s=round(time.perf_counter() - t0, 1),
               avg_fps=round(pipe.stats.frames / max(time.perf_counter() - t0, 1e-6), 1))
    return res
