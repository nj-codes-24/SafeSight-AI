"""Frame-by-frame pipeline: detect and track, resolve PPE state, watch zones, record incidents, annotate."""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from database.database import IncidentDB
from inference.config import DEFAULTS, load_config, save_config  # noqa: F401  (re-exported)
from inference.incident_lifecycle import REVIEW_CLS, VIOLATION_CLS, IncidentLifecycle
from inference.incident_manager import NO_HELMET, ZONE, IncidentManager
from inference.ppe_association import COMPLIANT, NOT_OBSERVABLE, UNCERTAIN, VIOLATION, HelmetStateTracker, assign_heads, head_truncated
from inference.zone_monitor import Zone, ZoneMonitor
from intelligence import ppe_policy as ppe
from intelligence.risk import RiskEngine, load_policy
from intelligence.taxonomy import ZONE_KINDS, hazard_for

if TYPE_CHECKING:  # imported lazily below: the detector pulls in torch, which the headless runtime's tests do without
    from inference.detector import Detector

COLORS = {COMPLIANT: (94, 197, 34), VIOLATION: (60, 60, 239), UNCERTAIN: (11, 158, 245)}

# PPE compliance categories (reports never collapse them into compliant / non-compliant).
CONFIRMED_VIOLATION, CONFIRMED_COMPLIANCE, PPE_UNCERTAIN = "confirmed_violation", "confirmed_compliance", "uncertain"
NOT_APPLICABLE, PPE_NOT_OBSERVABLE, NOT_CONFIGURED = "not_applicable", "not_observable", "requirement_not_configured"
# A requirement entered but not confirmed by the responsible person (entry status "provisional"): never a confirmed
# violation or compliance, because nobody authorised has said the rule applies (M3)
NOT_CONFIRMED = "requirement_not_confirmed"
PPE_CATEGORIES = [CONFIRMED_VIOLATION, CONFIRMED_COMPLIANCE, PPE_UNCERTAIN, NOT_APPLICABLE, PPE_NOT_OBSERVABLE, NOT_CONFIGURED,
                  NOT_CONFIRMED]


def classify(helmet: str, req: "ppe.Requirement") -> str:
    """One worker's head-protection category from the helmet evidence and the configured requirement."""
    if req.state in (ppe.NOT_REQUIRED, ppe.INACTIVE):
        return NOT_APPLICABLE
    if req.state == ppe.UNCONFIGURED:
        return NOT_CONFIGURED
    if req.state == ppe.AMBIGUOUS:
        return PPE_UNCERTAIN
    if req.status != "confirmed":
        return NOT_CONFIRMED
    return {VIOLATION: CONFIRMED_VIOLATION, COMPLIANT: CONFIRMED_COMPLIANCE, NOT_OBSERVABLE: PPE_NOT_OBSERVABLE}.get(
        helmet, PPE_UNCERTAIN)


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
                 policy=None, evidence_dir=None, listener=None, annotate=True, ppe_policy=ppe.POLICY_PATH, site=None):
        """ppe_policy: a policy dict, a path to one (default config/ppe_policy.json if present), or None for none."""
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
        self.camera_id, self.site = camera_id, site
        self.ppe = ppe.PPEPolicy(ppe_policy if isinstance(ppe_policy, dict) or ppe_policy is None else ppe.load(ppe_policy))
        self.lifecycle = IncidentLifecycle(self.incidents, self.db, self.session_id, camera_id, self.fps,
                                           confirm_s=self.cfg["confirm_seconds"], grace_s=self.cfg["grace_seconds"],
                                           resolve_s=self.cfg["resolve_seconds"], cooldown_s=self.cfg["cooldown_seconds"],
                                           burst_s=self.cfg["burst_seconds"], group_risk=self._group_risk)
        self._raising = None  # classification of the incident being raised, for its risk assessment
        self._review = {}  # incident id -> True when it is a review (no confirmed requirement), kept for re-assessments
        self.incidents.assessor_iid = True
        self.ppe_seconds = {c: 0.0 for c in PPE_CATEGORIES}  # worker-seconds per PPE category
        self.ppe_tracks = {c: set() for c in PPE_CATEGORIES}
        self.ppe_now = {}  # track id -> category this frame
        # False while zone geometry is not verified for the camera's current view (runtime/view.py): zone membership is
        # unknown, so no zone event or intrusion is raised and zone-dependent PPE requirements become ambiguous (review)
        self.zones_active = True

    def _assess(self, kind, zone, conf, exposure_s, iid=None):
        a = self.risk.assess(hazard_for(kind, self.zone_kind.get(zone)).code, exposure_s, conf, zone)
        if self._raising is not None and iid is not None:
            self._review[iid] = self._raising == REVIEW_CLS
        if kind == NO_HELMET and self._review.get(iid):
            a.requires_review = True
            a.factors.append("PPE requirement not configured, not confirmed, or ambiguous here: missing head protection is "
                             "reported for review, not as a confirmed violation")
        return a

    def _group_risk(self, kind, zone, conf, exposure_s):
        return self.risk.assess(hazard_for(kind, self.zone_kind.get(zone)).code, exposure_s, conf or None, zone).level

    def _requirement(self, tid, box, w, h):
        if not self.zones_active or box[3] >= h - self.cfg["edge_margin_px"]:  # unverified zones, or feet below the frame: where
            return self.ppe.requirement("head", self.camera_id, self.site, (), [z.name for z in self.zones.zones])  # unknown
        return self.ppe.requirement("head", self.camera_id, self.site, self.zones.inside(tid), self.zones.crossing(tid))

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
        lc = self.lifecycle
        lc.frame_size = (w, h)
        lc.begin_frame()
        dt = 1.0 / self.fps if self.t_last is None else min(max(t - self.t_last, 0.0), 1.0)
        for (tid, box, conf), head in zip(persons, matched):
            state, sconf = self.helmets.update(tid, head, head_truncated(head, w, self.cfg["edge_margin_px"]))
            foot = ((box[0] + box[2]) / 2, box[3])
            self.last_seen[tid] = fi
            self.stats.seen_ids.add(tid)
            self.stats.age[tid] = self.stats.age.get(tid, 0) + 1
            if state != UNCERTAIN or tid not in self.stats.final:
                self.stats.final[tid] = state
            # before the requirement: it may depend on the zone
            zone_events = self.zones.update(tid, foot, w, h) if self.zones_active else []
            req = self._requirement(tid, box, w, h)
            cat = classify(self.helmets.detail(tid), req)
            self.ppe_now[tid] = cat
            self.ppe_seconds[cat] += dt
            self.ppe_tracks[cat].add(tid)
            rows.append((tid, box, state, foot))
            crossing = self.zones_active and req.state == ppe.AMBIGUOUS and req.reason == "zone membership uncertain" and \
                box[3] < h - self.cfg["edge_margin_px"]
            if state == VIOLATION and crossing:
                pass  # entering or leaving a zone that decides the requirement: wait for the debounced entry or exit
            elif state == VIOLATION and req.state in (ppe.REQUIRED, ppe.UNCONFIGURED, ppe.AMBIGUOUS):
                # only a requirement confirmed by a named responsible person makes a violation; provisional is review
                cls = VIOLATION_CLS if req.state == ppe.REQUIRED and req.status == "confirmed" else REVIEW_CLS
                pending.append((NO_HELMET, tid, sconf, None, box, cls, req.to_dict()))
            elif state == VIOLATION:  # the requirement does not apply where the worker is now
                lc.resolve(NO_HELMET, tid, t, why=f"PPE requirement {req.state} here ({req.reason})")
            elif state == COMPLIANT:
                lc.compliant(NO_HELMET, tid, t)
            for ev, zone in zone_events:
                if zone in self.alert_zones and ev == "exit":
                    lc.resolve(ZONE, tid, t, zone, why="zone exit")
            for zone in self.zones.inside(tid) if self.zones_active else ():
                if zone in self.alert_zones:  # walkways, keep-clear and work areas: a person there is not the hazard
                    pending.append((ZONE, tid, conf, zone, box, VIOLATION_CLS, None))
        self._expire(fi, t)
        self.stats.tracked = {r[0]: r[2] for r in rows}  # visible now; lost tracks stay remembered but are not counted
        active = {r[0] for r in rows}
        new = [p for p in pending if (p[0], p[1], p[3]) not in lc.open]
        out = self._annotate(frame.copy(), rows, heads) if self.annotate or new else frame
        for kind, tid, c, zone, box, cls, req in pending:
            self._raising = cls
            lc.observe(kind, tid, t, c, box, out, active, zone, cls, req)
        self._raising = None
        lc.end_frame(t)
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
        if t is not None:
            self.lifecycle.interrupt(t)  # outcome unknown: each incident ends at its last observation
        for tid in list(self.last_seen):
            self.zones.drop(tid)
            self.helmets.drop(tid)
            if t is not None:
                self.incidents.close_track(tid, t)
        self.last_seen.clear()
        self.stats.tracked = {}
        self.id_offset = self.max_tid
        self.det.reset()

    def interrupt_view(self, t, reliable_t, reason, event_id, why) -> list:
        """The camera's view stopped being trustworthy at t (runtime/view.py): every open incident ends at the last
        reliable observation (reliable_t), outcome unknown, with the view event recorded; then every track is dropped
        and new IDs continue past the old ones, as after a stream gap. Returns the IDs of the incidents ended."""
        # no reliable observation at all (blocked from the start): nothing after an incident's opening counts
        until = reliable_t if reliable_t is not None else float("-inf")
        ended = self.lifecycle.interrupt(t, reason=reason, why=why, until=until, detail={"view_event_id": event_id})
        self.reset_tracks(t)
        return ended

    def set_zones_active(self, active: bool):
        """Zone geometry verified (True) or not (False) for the current view. Leaving active forgets zone membership:
        it was measured in geometry that is no longer trusted."""
        if self.zones_active and not active:
            self.zones.state.clear()
        self.zones_active = active

    def _expire(self, fi, t):
        limit = self.cfg["lost_track_seconds"] * self.fps
        for tid in [k for k, v in self.last_seen.items() if fi - v > limit]:
            self.zones.drop(tid)  # a lost track is not an exit: its zone incident waits for re-observation (grace)
            self.helmets.drop(tid)
            self.lifecycle.track_lost(tid, t)
            del self.last_seen[tid]

    def _annotate(self, im, rows, heads):
        h, w = im.shape[:2]
        scale = max(0.45, min(w, h) / 1100)
        for z in self.zones.zones if self.zones_active else ():  # unverified geometry is not drawn as if it were valid
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
            cat = self.ppe_now.get(tid)
            note = " (REVIEW: no rule)" if cat == NOT_CONFIGURED and state == VIOLATION else \
                " (REVIEW: rule not confirmed)" if cat == NOT_CONFIRMED and state == VIOLATION else \
                " (N/A here)" if cat == NOT_APPLICABLE and state == VIOLATION else ""
            label = f"W{tid} {state}{note}" + (" IN ZONE" if self.alert_zones.intersection(self.zones.inside(tid)) else "")
            (tw, th), _ = cv2.getTextSize(label, 0, scale, 1)
            top = max(th + 6, y1)
            cv2.rectangle(im, (x1, top - th - 6), (x1 + tw + 6, top), col, -1)
            cv2.putText(im, label, (x1 + 3, top - 4), 0, scale, (15, 15, 15), 1, cv2.LINE_AA)
            cv2.circle(im, (int(foot[0]), int(foot[1])), 4, col, -1, cv2.LINE_AA)
        return im

    def finish(self, source=None, t=None):
        """End open incidents (at their last observation; the session ends at t, default the end of the frames) and
        store the session. Safe to call twice."""
        t = self.stats.frames / self.fps if t is None else t
        self.lifecycle.finish(t)
        self.incidents.close_all(t)
        self.db.save_ppe_observations(self.session_id, self.camera_id, self.ppe_seconds,
                                      {c: len(v) for c, v in self.ppe_tracks.items()})
        keep = self.stats.confirmed()
        f = [self.stats.final[k] for k in keep if k in self.stats.final]
        self.db.save_session(self.session_id, source, self.stats.frames, len(keep), f.count(COMPLIANT),
                             f.count(VIOLATION), f.count(UNCERTAIN), round(self.stats.fps, 1))
        return self.summary()

    def summary(self):
        return self.stats.snapshot(sum(self.incidents.counts.values()))  # incidents raised in this session


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
