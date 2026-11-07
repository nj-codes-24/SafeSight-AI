"""Incident lifecycle: when an incident starts, continues, is resolved, or ends with an unknown outcome.

One camera's state machine above IncidentManager (which keeps persistence, evidence and risk). Per incident:

- ACTIVE while the condition (a confirmed helmet violation where a requirement applies, or a person inside an alert
  zone) is observed. UNOBSERVED when it is not observed this frame: the track is missing, or the head cannot be judged.
- RESOLVED only on positive evidence: a helmet state held for resolve_s (hysteresis: one compliant vote is not enough),
  a debounced zone exit, or the worker leaving the area where the PPE requirement applies. Resolution clears the
  cooldown, so a genuinely new violation afterwards is never suppressed.
- OBSERVATION_LOST when nothing has been observed for grace_s; CAMERA_INTERRUPTED when the stream gaps or restarts (the
  tracker restarts and continuity cannot be assessed); SESSION_END on shutdown. These outcomes are unknown and are
  recorded as unknown: the worker is never assumed compliant because the detector stopped seeing them.
- The camera's view stopped being trustworthy (inference/view_monitor.py): CAMERA_VIEW_CHANGED, CAMERA_SCENE_SWITCHED,
  CAMERA_BLOCKED or CAMERA_VIEW_UNVERIFIED, also unknown outcomes. The incident ends at the last check that still matched
  the registered view (anything observed after it, while the change was being confirmed, is not evidence), and the view
  event ID and the risk level before the interruption are recorded. These ends are never linked by position to later
  observations: after a view change the same pixels may be a different place.

Time: video time t (media time for files, monotonic seconds for live sources). An incident ends at the last time the
condition was observed; the decision time is kept separately. Exposure is confirmation time plus first-to-last observed
time, so it never extends past the evidence; time inside it without observation (gaps up to grace_s that were bridged by
a later observation) is reported as unobserved_s.

Identity: incidents belong to a camera-scoped track. A new track may continue an UNOBSERVED incident only if the old
track is no longer visible, the condition and zone match, and it appears within one box height of where the old one
was last seen, within grace_s. This is an inference from position, recorded as such ("reassociated"); it is never
presented as identity.

Grouping and notifications: incidents of one worker's one violation form an alert group. After an unknown-outcome end, a
re-observation of the same worker (same track, or same place with the old track gone) within cooldown_s is recorded
against the group as a re-observation (time and duration), not as a duplicate incident or notification; if it is still
going on when the cooldown ends, a new incident opens in the same group, still without a new notification. A new group
after a confirmed resolution is a recurrence and is notified. Notifications of the same kind on one camera opened
within burst_s are batched into one notification that lists every group: different workers stay separate incidents.
Every decision is written to incident_events.
"""
import itertools
from dataclasses import dataclass, field

import numpy as np

ACTIVE, UNOBSERVED = "active", "unobserved"
RESOLVED, LOST, INTERRUPTED, SESSION_END, RECLASSIFIED = (
    "resolved", "observation_lost", "camera_interrupted", "session_end", "classification_changed")
UNKNOWN_OUTCOME = {LOST, INTERRUPTED, SESSION_END}  # may be linked to a re-observation of the same worker (cooldown)
# Camera view interruptions: unknown outcome too, but never linked by position (inference/view_monitor.py EVENT_TYPES)
VIEW_CHANGED, SCENE_SWITCHED, BLOCKED, VIEW_UNVERIFIED = (
    "camera_view_changed", "camera_scene_switched", "camera_blocked", "camera_view_unverified")
VIEW_INTERRUPTION = {VIEW_CHANGED, SCENE_SWITCHED, BLOCKED, VIEW_UNVERIFIED}
VIOLATION_CLS, REVIEW_CLS = "violation", "requires_review"
GAP_EVENT_S = 1.0  # an observation gap at least this long is written to the audit when it is bridged
PATH_STEP_S = 0.5  # the worker's box is kept this often, for identity-aware evaluation and investigation


@dataclass
class Episode:
    iid: str
    group: "Group"
    kind: str
    zone: str | None
    track: int
    opened_t: float
    last_t: float
    classification: str
    requirement: dict | None
    conf: float
    box: np.ndarray | None
    tracks: list = field(default_factory=list)
    observed_s: float = 0.0
    unobserved_s: float = 0.0
    state: str = ACTIVE
    seen_now: bool = True
    resolve_since: float | None = None
    compliant_now: bool = False
    relation: str | None = None
    linked_to: str | None = None
    path: list = field(default_factory=list)  # [t, x1, y1, x2, y2] normalised, every PATH_STEP_S: which worker, where


@dataclass
class Group:
    gid: str
    kind: str
    zone: str | None
    classification: str
    first_t: float
    last_t: float
    incidents: list = field(default_factory=list)
    exposure_s: float = 0.0  # ended incidents only; open ones are added when reported
    observed_s: float = 0.0
    reobserved_s: float = 0.0
    state: str = "open"
    end_reason: str | None = None
    ended_t: float | None = None
    track: int | None = None
    box: np.ndarray | None = None
    notification: str | None = None
    reobs: dict | None = None  # current re-observation after an unknown-outcome end


class IncidentLifecycle:
    def __init__(self, manager, db, session_id, camera_id, fps, confirm_s=0.5, grace_s=10.0, resolve_s=2.0,
                 cooldown_s=30.0, burst_s=10.0, same_place=1.0, group_risk=None):
        self.m, self.db, self.session, self.camera = manager, db, session_id, camera_id
        self.confirm_s, self.grace_s, self.resolve_s = confirm_s, grace_s, resolve_s
        self.cooldown_s, self.burst_s, self.same_place = cooldown_s, burst_s, same_place
        self.frame_gap = 2.5 / (fps or 25.0)  # one missed frame is still continuous observation
        self.group_risk = group_risk  # optional (kind, zone, conf, exposure_s) -> risk level
        self.open: dict = {}  # (kind, track, zone) -> Episode
        self.groups: dict = {}  # gid -> Group
        self.notes: dict = {}  # notification id -> record
        self.new_notifications, self.ended = [], []
        self._ids = itertools.count(1)
        self.frame_size = None  # (width, height), set by the pipeline each frame
        manager.exposure_fn = self._exposure

    # ------------------------------------------------------------------ helpers
    def _id(self, prefix):
        return f"{prefix}-{self.session[-12:]}-{next(self._ids):04d}"

    def _event(self, event, t=None, ep=None, group=None, track=None, **detail):
        g = ep.group if ep else group
        self.db.add_event(self.session, event, ep.iid if ep else None, g.gid if g else None, t, track if track is not None
                          else (ep.track if ep else None), detail or None)

    def _exposure(self, key, video_t=None):
        ep = self.open.get(key)
        return None if ep is None else self.confirm_s + max(0.0, ep.last_t - ep.opened_t)

    def _near(self, box_a, box_b):
        if box_a is None or box_b is None:
            return False
        ca, cb = (box_a[:2] + box_a[2:]) / 2, (box_b[:2] + box_b[2:]) / 2
        return float(np.hypot(*(ca - cb))) < self.same_place * float(box_b[3] - box_b[1])

    def _save(self, ep, t=None, end_reason=None, ended_t=None):
        self.db.save_lifecycle({
            "incident_id": ep.iid, "group_id": ep.group.gid, "session_id": self.session, "camera_id": self.camera,
            "incident_type": ep.kind, "zone": ep.zone, "tracks": ep.tracks, "state": end_reason and "ended" or ep.state,
            "end_reason": end_reason, "classification": ep.classification, "requirement": ep.requirement,
            "opened_t": round(ep.opened_t, 3), "last_observed_t": round(ep.last_t, 3),
            "ended_t": None if ended_t is None else round(ended_t, 3), "closed_t": None if end_reason is None else round(t, 3),
            "observed_s": round(ep.observed_s, 3), "unobserved_s": round(ep.unobserved_s, 3),
            "exposure_s": round(self.confirm_s + max(0.0, ep.last_t - ep.opened_t), 3), "relation": ep.relation,
            "linked_to": ep.linked_to, "path": ep.path if end_reason else None})

    def _save_group(self, g):
        live = [e for e in self.open.values() if e.group is g]
        exposure = g.exposure_s + sum(self.confirm_s + max(0.0, e.last_t - e.opened_t) for e in live) + g.reobserved_s
        observed = g.observed_s + sum(e.observed_s for e in live)
        risk = self.group_risk(g.kind, g.zone, max((e.conf for e in live), default=0.0), exposure) if self.group_risk else None
        self.db.save_group({"group_id": g.gid, "session_id": self.session, "camera_id": self.camera, "incident_type": g.kind,
                            "zone": g.zone, "classification": g.classification, "state": g.state, "first_t": round(g.first_t, 3),
                            "last_t": round(g.last_t, 3), "exposure_s": round(exposure, 3), "observed_s": round(observed, 3),
                            "reobserved_s": round(g.reobserved_s, 3), "incidents": g.incidents, "risk_level": risk,
                            "notification_id": g.notification})

    def _notify(self, g, t, kind):
        """Batch with a notification of the same kind opened on this camera within burst_s, else create one."""
        for n in self.notes.values():
            if n["kind"] == kind and n["incident_type"] == g.kind and t - n["created_t"] <= self.burst_s:
                n["group_ids"].append(g.gid)
                n["incident_ids"].append(g.incidents[0])
                n["count"] += 1
                g.notification = n["notification_id"]
                self.db.save_notification(n)
                self._event("notification_batched", t, group=g, notification=n["notification_id"], count=n["count"])
                return
        nid = self._id("N")
        n = {"notification_id": nid, "session_id": self.session, "camera_id": self.camera, "incident_type": g.kind,
             "kind": kind, "classification": g.classification, "created_t": round(t, 3), "group_ids": [g.gid],
             "incident_ids": [g.incidents[0]], "count": 1}
        self.notes[nid] = n
        g.notification = nid
        self.db.save_notification(n)
        self.new_notifications.append(dict(n))
        self._event("notification_created", t, group=g, notification=nid, kind=kind)

    # ------------------------------------------------------------------ per frame
    def begin_frame(self):
        for ep in self.open.values():
            ep.seen_now = ep.compliant_now = False

    def observe(self, kind, track, t, conf, box, frame, active, zone=None, classification=VIOLATION_CLS, requirement=None):
        """The condition holds for this track now. Returns the new incident's alert, or None if an existing incident
        continues or this is a recorded re-observation."""
        key = (kind, track, zone)
        ep = self.open.get(key)
        if ep is not None and ep.classification != classification:  # e.g. walked from an unconfigured into a required area
            self._end(ep, t, RECLASSIFIED)
            ep = None
        if ep is not None:
            self._extend(ep, t, conf, box)
            return None
        ep = self._reassociate(kind, track, t, box, active, zone, classification)
        if ep is not None:
            self._extend(ep, t, conf, box)
            return None
        g = self._unknown_end_group(kind, track, t, box, active, zone, classification)
        relation = None
        if g is not None:
            if t - g.ended_t < self.cooldown_s:
                self._reobserve(g, track, t)
                return None
            relation = "continued_after_unknown_end"  # still going on after the cooldown: a new incident, same group
        alert = self.m.raise_incident(kind, track, conf, t, frame, zone, box, active, check=False)
        if alert is None:
            return None
        new_group = g is None
        if new_group:
            g = Group(self._id("G"), kind, zone, classification, t, t, track=track, box=box)
            self.groups[g.gid] = g
        else:
            self._close_reobs(g, t)
            g.state, g.end_reason, g.ended_t = "open", None, None
        g.incidents.append(alert["incident_id"])
        g.track, g.box, g.last_t = track, box, t
        ep = Episode(alert["incident_id"], g, kind, zone, track, t, t, classification, requirement, conf, box, [track],
                     relation=relation, linked_to=g.incidents[-2] if len(g.incidents) > 1 else None)
        self._sample(ep, t)
        self.open[key] = ep
        alert.update(classification=classification, group_id=g.gid, requirement=(requirement or {}).get("state"),
                     requirement_status=(requirement or {}).get("status"), relation=relation)
        self._save(ep)
        self._event("opened", t, ep, classification=classification, relation=relation, requirement=requirement)
        if new_group:
            self._notify(g, t, "review" if classification == REVIEW_CLS else
                         "recurrence" if self._recurrence(kind, track, zone) else "alert")
        else:
            self._event("group_continued", t, ep, after_unknown_end=True)
        self._save_group(g)
        return alert

    def compliant(self, kind, track, t, zone=None):
        """Positive evidence against the condition this frame (helmet state COMPLIANT)."""
        ep = self.open.get((kind, track, zone))
        if ep is not None:
            ep.compliant_now = True
            if ep.resolve_since is None:
                ep.resolve_since = t

    def resolve(self, kind, track, t, zone=None, why="zone_exit"):
        """Immediate, already-debounced resolution (zone exit; worker left the area where the requirement applies)."""
        ep = self.open.get((kind, track, zone))
        if ep is not None:
            self._end(ep, t, RESOLVED, why=why)

    def end_frame(self, t):
        for ep in list(self.open.values()):
            if not ep.compliant_now:
                ep.resolve_since = None
            elif t - ep.resolve_since >= self.resolve_s:
                self._end(ep, t, RESOLVED, why="compliance sustained")
                continue
            if ep.seen_now:
                continue
            if ep.state == ACTIVE and t - ep.last_t >= GAP_EVENT_S:  # a frame or two missing is not worth recording
                ep.state = UNOBSERVED
                self._event("observation_lost", t, ep, last_observed_t=round(ep.last_t, 3))
                self._save(ep)
            if t - ep.last_t > self.grace_s:
                self._end(ep, t, LOST, why=f"not observed for more than {self.grace_s:g} s")
        for g in self.groups.values():
            if g.reobs is not None and t - g.reobs["last"] > self.grace_s:
                self._close_reobs(g, t)

    def track_lost(self, track, t):
        for ep in self.open.values():
            if ep.track == track:
                self._event("track_lost", t, ep)

    def interrupt(self, t, reason=INTERRUPTED, why="stream gap or restart", until=None, detail=None) -> list:
        """Camera gap or restart (or, with a view reason, the view became untrustworthy): every open incident ends at its
        last observation, outcome unknown. until caps that at the last reliable observation: later observations are kept
        in the audit (observed_until_t) but end no exposure. Returns the IDs of the incidents ended."""
        ended = []
        for ep in list(self.open.values()):
            extra = dict(detail or {})
            a = self.m.assessed.get((ep.kind, ep.track, ep.zone))
            if a is not None:
                extra["risk_before"] = a[3].level
            if until is not None and ep.last_t > until:
                extra["observed_until_t"] = round(ep.last_t, 3)
                if ep.opened_t > until:
                    extra["opened_after_last_reliable_view"] = True
                ep.last_t = max(ep.opened_t, until)
                ep.observed_s = min(ep.observed_s, ep.last_t - ep.opened_t)
                ep.unobserved_s = min(ep.unobserved_s, ep.last_t - ep.opened_t - ep.observed_s)
            self._end(ep, t, reason, why=why, **extra)
            ended.append(ep.iid)
        for g in self.groups.values():
            self._close_reobs(g, t)
        return ended

    def finish(self, t):
        for ep in list(self.open.values()):
            self._end(ep, t, SESSION_END, why="monitoring stopped")
        for g in self.groups.values():
            self._close_reobs(g, t)
            if g.state != "closed":
                g.state = "closed"
                self._save_group(g)

    def drain_notifications(self) -> list:
        n, self.new_notifications = self.new_notifications, []
        return n

    # ------------------------------------------------------------------ transitions
    def _extend(self, ep, t, conf, box):
        if ep.seen_now:
            return
        dt = t - ep.last_t
        if dt <= self.frame_gap:
            ep.observed_s += dt
        else:
            ep.unobserved_s += dt  # bridged: observed again within grace_s; counted inside exposure, reported apart
        was = ep.state
        ep.last_t, ep.state, ep.seen_now, ep.conf = t, ACTIVE, True, max(ep.conf, float(conf))
        ep.box = box if box is not None else ep.box
        self._sample(ep, t)
        ep.group.last_t, ep.group.box = t, ep.box
        if was == UNOBSERVED:
            self._event("reobserved", t, ep, gap_s=round(dt, 3))
            self._save(ep)

    def _sample(self, ep, t):
        if ep.box is None or self.frame_size is None or (ep.path and t - ep.path[-1][0] < PATH_STEP_S):
            return
        w, h = self.frame_size
        x1, y1, x2, y2 = (float(v) for v in ep.box)
        ep.path.append([round(t, 3), round(x1 / w, 4), round(y1 / h, 4), round(x2 / w, 4), round(y2 / h, 4)])

    def _reassociate(self, kind, track, t, box, active, zone, classification):
        cands = [e for e in self.open.values() if e.kind == kind and e.zone == zone and e.classification == classification
                 and not e.seen_now and e.track not in active and t - e.last_t <= self.grace_s and self._near(box, e.box)]
        if not cands:
            return None
        ep = min(cands, key=lambda e: t - e.last_t)
        old = (kind, ep.track, zone)
        new = (kind, track, zone)
        self.open[new] = self.open.pop(old)
        self.m.rekey(old, new)
        self._event("reassociated", t, ep, from_track=ep.track, to_track=track, basis="position (same place, old track gone)",
                    gap_s=round(t - ep.last_t, 3))
        ep.track = track
        ep.tracks.append(track)
        self._save(ep)
        return ep

    def _unknown_end_group(self, kind, track, t, box, active, zone, classification):
        best = None
        for g in self.groups.values():
            if g.kind != kind or g.zone != zone or g.classification != classification or g.state != "ended":
                continue
            if g.end_reason not in UNKNOWN_OUTCOME or g.ended_t is None:
                continue
            ongoing = g.reobs is not None and g.reobs["track"] == track  # a re-observation that began inside the cooldown
            if t - g.ended_t >= self.cooldown_s and not ongoing:
                continue  # too long ago to assume the same worker's same violation
            same = g.track == track or ongoing
            if same or (g.track not in active and self._near(box, g.box)):
                if best is None or g.ended_t > best.ended_t:
                    best = g
        return best

    def _recurrence(self, kind, track, zone):
        return any(g.kind == kind and g.zone == zone and g.track == track and g.end_reason == RESOLVED
                   for g in self.groups.values())

    def _reobserve(self, g, track, t):
        r = g.reobs
        if r is None or r["track"] != track:
            self._close_reobs(g, t)
            g.reobs = {"track": track, "start": t, "last": t, "observed_s": 0.0}
            self.m.suppressed += 1
            self._event("reobserved_after_unknown_end", t, group=g, track=track, incident=g.incidents[-1],
                        ended_by=g.end_reason, seconds_after_end=round(t - g.ended_t, 3))
            return
        dt = t - r["last"]
        if dt <= self.frame_gap:
            r["observed_s"] += dt
        r["last"] = t

    def _close_reobs(self, g, t):
        r, g.reobs = g.reobs, None
        if r is None:
            return
        g.reobserved_s += r["observed_s"]
        self._event("reobservation_ended", t, group=g, track=r["track"], start_t=round(r["start"], 3),
                    last_t=round(r["last"], 3), observed_s=round(r["observed_s"], 3))
        self._save_group(g)

    def _end(self, ep, t, reason, why="", **detail):
        key = (ep.kind, ep.track, ep.zone)
        self.open.pop(key, None)
        if key in self.m.open:
            self.m.end(ep.kind, ep.track, ep.last_t, ep.zone, resolved=reason == RESOLVED)
        self._save(ep, t, reason, ep.last_t)
        self._event("ended", t, ep, reason=reason, why=why, ended_t=round(ep.last_t, 3),
                    exposure_s=round(self.confirm_s + max(0.0, ep.last_t - ep.opened_t), 3),
                    observed_s=round(ep.observed_s, 3), unobserved_s=round(ep.unobserved_s, 3), **detail)
        g = ep.group
        g.exposure_s += self.confirm_s + max(0.0, ep.last_t - ep.opened_t)
        g.observed_s += ep.observed_s
        if not any(e.group is g for e in self.open.values()):
            g.state, g.end_reason, g.ended_t, g.track, g.box = "ended", reason, ep.last_t, ep.track, ep.box
        self.ended.append({"incident_id": ep.iid, "reason": reason, "ended_t": ep.last_t, "closed_t": t})
        self._save_group(g)
