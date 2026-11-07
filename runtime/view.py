"""One camera's view guard: runs the view monitor on its frames and acts on what it finds.

- Reference: the camera's active revision from the database. Without one, the first steady view becomes revision 1
  (basis "auto"); its zones are recorded as "assumed": drawn for that view, as before view monitoring, but not verified
  by an operator. A stored reference is verified before any frame is analysed.
- Confirmed change, scene switch or blockage: a camera_view_events row; every open incident is ended at the last
  reliable observation with the event type as its reason; tracks are reset (new IDs); safety analysis is suspended.
- Recovery: only to the registered view, after recover_s; a different steady view becomes a candidate revision that an
  operator must accept (python -m runtime view accept). Zones of an accepted revision need review (verify-zones) unless
  the operator said they reviewed them; until then zone membership is unknown and no zone alert is raised.
- Snapshots: a few small grey images per event (analysis width, no colour), next to the incident evidence.

The processing thread owns the guard; it is never shared between cameras.
"""
import hashlib
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

import cv2

from inference import view_monitor as vm
from runtime.health import iso, utc_now

COMMAND_EVERY_S = 1.0  # how often (wall time) pending operator commands are looked up
MAX_CHECK_FAILURES = 5  # view checks failing in a row before the view counts as unverifiable
CHECK_FAILED = "CHECK_FAILED"  # reported view state while checks keep failing (not a monitor state)


def zones_hash(zones) -> str:
    return hashlib.sha256(json.dumps(zones, sort_keys=True).encode()).hexdigest()[:16]


class ViewGuard:
    def __init__(self, camera, db, session_id, evidence_dir, log, health=None):
        self.cam, self.db, self.session, self.log, self.health = camera, db, session_id, log, health
        self.s = camera.view
        self.dir = Path(evidence_dir) / "view" / camera.id
        self.zhash = zones_hash(camera.zones)
        self.revision = None
        self.zones_status = None  # assumed | verified | requires_review (None: no zones)
        ref = None
        for r in db.view_revisions(camera.id, status="active"):
            self.revision, self.zones_status = r["revision"], r["zones_status"]
            ref = vm.Fingerprint.from_png(db.view_fingerprint(camera.id, r["revision"]))
            if camera.zones and r["zones_hash"] != self.zhash and self.zones_status != "requires_review":
                self.zones_status = "requires_review"  # edited since they were checked against this view
                db.set_view_zones(camera.id, self.revision, self.zones_status, self.zhash)
                log.warning("zones changed in the configuration since view revision %d was checked: zone monitoring "
                            "waits for 'python -m runtime view verify-zones'", self.revision)
        self.mon = vm.ViewMonitor(self.s, ref)
        self.event = None  # the open view event (dict), if any
        self.last_event = None  # the latest event of this session, open or closed (for status)
        self.ref_t = self.ref_utc = None  # a recent frame's (video time, UTC), to date video times
        self.last_commands = None
        self.interrupted = 0  # incidents interrupted by view events this session
        self.failures = 0  # view checks that raised, in a row
        if ref is not None:
            log.info("view: verifying registered reference revision %d before analysing", self.revision)
        self._publish()

    # ------------------------------------------------------------------ what the worker asks
    @property
    def analysing(self) -> bool:
        """Safety analysis runs on this frame: the view is trusted, or no reference exists yet (bootstrap) and nothing
        has gone wrong (after a confirmed blockage at start, analysis waits for the reference). A view that cannot be
        checked (the check keeps failing) is not trusted."""
        return not self.s.enabled or (not self.failed and (self.mon.trusted or (self.mon.bootstrapping and self.event is None)))

    @property
    def failed(self) -> bool:
        return self.failures >= MAX_CHECK_FAILURES

    def on_failure(self, error, t, pipeline):
        """A view check raised. One failure is logged; MAX_CHECK_FAILURES in a row means the view cannot be verified:
        open incidents end at the last reliable observation (camera_view_unverified) and analysis stops until a
        check succeeds again."""
        self.failures += 1
        self.log.error("view check failed at t=%.2f s (%d in a row): %s", t, self.failures, error)
        if self.failures == MAX_CHECK_FAILURES:
            self._open_event(vm.Transition(self.mon.state, CHECK_FAILED, t, f"view checks failing: {error}",
                                           vm.CAMERA_VIEW_UNVERIFIED, self.mon.reliable_t, t,
                                           {"error": str(error), "failures": self.failures}), pipeline)
            self.log.error("view cannot be verified: analysis suspended until a check succeeds")
        self._publish()

    @property
    def zones_ok(self) -> bool:
        return (not self.s.enabled or (self.analysing and not self.mon.unsettled)) and \
            self.zones_status in (None, "assumed", "verified")

    def _utc(self, t):
        if t is None or self.ref_t is None or self.ref_utc is None:
            return None
        return iso(self.ref_utc + timedelta(seconds=t - self.ref_t))

    # ------------------------------------------------------------------ per frame
    def observe(self, frame, t, utc, discontinuity, pipeline):
        """Check the frame when a check is due; act on any transition. Returns the transitions (for logging/tests)."""
        if not self.s.enabled:
            return []
        self.ref_t, self.ref_utc = t, utc
        if not self.mon.due(t, discontinuity):
            return []
        t0 = time.perf_counter()
        trs = self.mon.observe(frame, t, discontinuity)
        if self.failed and self.event is not None and self.event["state"] == CHECK_FAILED:
            self._close_event(t, "view checks working again", recovered=self.mon.trusted)
        self.failures = 0
        if self.health is not None:
            self.health.on_view_check(1000 * (time.perf_counter() - t0))
        for tr in trs:
            self._apply(tr, pipeline)
        if pipeline is not None:
            pipeline.set_zones_active(self.zones_ok)
        self._publish()
        return trs

    def _apply(self, tr, pipeline):
        cam, mon = self.cam, self.mon
        log = self.log.warning if tr.kind else self.log.info
        log("view %s -> %s at t=%.1f s: %s", tr.previous, tr.state, tr.t, tr.cause)
        if tr.previous == vm.INITIALIZING and tr.state == vm.VIEW_STABLE and self.revision is None:
            if self.event is not None:  # blocked before any reference existed, now observable and steady
                self._close_event(tr.t, "observable again; reference established")
            self.zones_status = "assumed" if cam.zones else None
            self.revision = self.db.add_view_revision(
                cam.id, mon.reference.to_png(), *mon.reference.gray.shape[::-1], "active",
                "auto: first steady view (temporal median)", "system", self.session, None, self.zhash, self.zones_status)
            self.log.info("view reference revision %d established%s", self.revision,
                          "; zones assumed to be drawn for this view (not operator-verified)" if cam.zones else "")
            return
        if tr.kind:
            self._open_event(tr, pipeline)
            return
        if tr.state == vm.VIEW_UNVERIFIED and self.event is not None:
            self._expire_candidate()
            fp = mon.candidate
            rev = self.db.add_view_revision(cam.id, fp.to_png(), *fp.gray.shape[::-1], "candidate",
                                            "candidate: steady view that differs from the registered reference", "system",
                                            self.session, self.event["event_id"], self.zhash,
                                            "requires_review" if cam.zones else None)
            self.event.update(state=vm.VIEW_UNVERIFIED, candidate_revision=rev)
            self._snap("candidate", fp.gray)
            self._save_event()
            self.log.warning("view: candidate revision %d stored; an operator must accept it (python -m runtime view accept "
                             "--camera %s --revision %d) or restore the camera", rev, cam.id, rev)
            return
        if tr.state == vm.VIEW_STABLE and tr.previous == vm.RECOVERING and self.event is not None:
            self._close_event(tr.t, "original_view_restored")
            return
        if self.event is not None and self.event["state"] != tr.state:
            self.event["state"] = tr.state
            self._save_event()

    def _open_event(self, tr, pipeline):
        cam = self.cam
        linked = None
        if self.event is not None:  # e.g. blocked, then uncovered on a different view: a new event, linked
            linked = self.event["event_id"]
            self._close_event(tr.t, f"superseded by {tr.kind}", recovered=False)
        eid = f"VE-{cam.id}-{uuid.uuid4().hex[:8].upper()}"
        ended = []
        if pipeline is not None:
            ended = pipeline.interrupt_view(tr.t, tr.reliable_t, tr.kind, eid, tr.cause)
            pipeline.set_zones_active(False)
        self.interrupted += len(ended)
        ev = tr.evidence
        self.event = {
            "event_id": eid, "camera_id": cam.id, "site_id": cam.site, "session_id": self.session, "event_type": tr.kind,
            "cause": tr.cause, "state": tr.state, "previous_revision": self.revision,
            "first_suspected_t": round(tr.suspected_t, 3), "first_suspected_utc": self._utc(tr.suspected_t),
            "last_reliable_t": None if tr.reliable_t is None else round(tr.reliable_t, 3),
            "last_reliable_utc": self._utc(tr.reliable_t), "confirmed_t": round(tr.t, 3), "confirmed_utc": self._utc(tr.t),
            "evidence_quality": ev.get("evidence_quality", "medium"), "evidence": ev, "affected_incidents": ended,
            "snapshots": {}, "linked_event": linked, "acknowledged": 0}
        if self.mon.reference is not None:
            self._snap("reference", self.mon.reference.gray)
        if self.mon.last_reliable_gray is not None:
            self._snap("last_reliable", self.mon.last_reliable_gray)
        if self.mon.last_gray is not None:
            self._snap("confirmed", self.mon.last_gray)
        self._save_event()
        self.log.warning("view event %s (%s): %d open incident(s) ended at the last reliable observation (t=%s); safety "
                         "analysis suspended%s", eid, tr.kind, len(ended),
                         "-" if tr.reliable_t is None else f"{tr.reliable_t:.1f} s",
                         "; zones require revalidation unless the registered view returns" if cam.zones else "")

    def _expire_candidate(self):
        """A candidate the camera no longer shows cannot be accepted any more."""
        rev = self.event.get("candidate_revision") if self.event else None
        if rev is not None and rev != self.event.get("accepted_revision"):
            self.db.set_view_revision_status(self.cam.id, rev, "expired")

    def _close_event(self, t, outcome, recovered=True, accepted=None):
        if accepted is None:
            self._expire_candidate()
        e = self.event
        e.update(state=self.mon.state, outcome=outcome)
        if recovered:
            e.update(recovered_t=round(t, 3), recovered_utc=self._utc(t))
        if accepted is not None:
            e["accepted_revision"] = accepted
        self._save_event()
        if recovered:
            self.log.info("view event %s closed: %s; analysis resumes with new track IDs", e["event_id"], outcome)
        self.event = None

    def _save_event(self):
        self.db.save_view_event(self.event)
        self.last_event = dict(self.event)

    def _snap(self, name, gray):
        if not self.s.snapshots or gray is None:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{self.event['event_id']}_{name}.png"
        cv2.imwrite(str(path), gray)
        self.event["snapshots"][name] = str(path)

    # ------------------------------------------------------------------ operator commands
    def poll_commands(self, now, pipeline):
        """Apply pending operator commands for this camera (checked at most every COMMAND_EVERY_S of wall time)."""
        if self.last_commands is not None and now - self.last_commands < COMMAND_EVERY_S:
            return
        self.last_commands = now
        for c in self.db.view_commands(self.cam.id, pending=True):
            try:
                result = getattr(self, f"_cmd_{c['command'].replace('-', '_')}")(c, pipeline)
            except AttributeError:
                result = f"rejected: unknown command {c['command']}"
            self.db.finish_view_command(c["command_id"], result)
            self.log.warning("view command %d (%s by %s): %s", c["command_id"], c["command"], c["requested_by"], result)
        if pipeline is not None:
            pipeline.set_zones_active(self.zones_ok)
        self._publish()

    def _cmd_accept(self, c, pipeline):
        rev = c["revision"]
        row = [r for r in self.db.view_revisions(self.cam.id) if r["revision"] == rev]
        if not row or row[0]["status"] not in ("candidate", "active"):
            return f"rejected: revision {rev} is not a candidate"
        fp = vm.Fingerprint.from_png(self.db.view_fingerprint(self.cam.id, rev))
        now = self.mon.prev
        m = vm.match(now, fp, self.s.min_inliers) if now is not None else None
        if m is None or not m.fitted or m.shift > self.s.max_shift:
            return f"rejected: the camera is not showing revision {rev} now (view {self.mon.state})"
        self.db.activate_view_revision(self.cam.id, rev)
        self.zones_status = ("verified" if c["zones_reviewed"] else "requires_review") if self.cam.zones else None
        self.db.set_view_zones(self.cam.id, rev, self.zones_status, self.zhash,
                               c["requested_by"] if c["zones_reviewed"] else None)
        t = self.mon.last_check_t or 0.0
        self.mon.accept(fp, t)
        self.revision = rev
        if self.event is not None:
            self._close_event(t, f"new_view_accepted by {c['requested_by']}", accepted=rev)
        return f"accepted revision {rev} as the reference; zones {self.zones_status or 'none'}"

    def _cmd_verify_zones(self, c, pipeline):
        if not self.cam.zones:
            return "rejected: this camera has no zones"
        if self.revision is None:
            return "rejected: no reference revision yet"
        self.zones_status = "verified"
        self.db.set_view_zones(self.cam.id, self.revision, "verified", self.zhash, c["requested_by"])
        return f"zones verified for revision {self.revision}"

    def _cmd_acknowledge(self, c, pipeline):
        rows = [e for e in self.db.view_events(self.cam.id) if e["event_id"] == c["event_id"]]
        if not rows:
            return f"rejected: no event {c['event_id']}"
        e = rows[0]
        e.update(acknowledged=1, acknowledged_by=c["requested_by"], acknowledged_utc=iso(utc_now()))
        self.db.save_view_event(e)
        if self.event is not None and self.event["event_id"] == e["event_id"]:
            self.event.update(acknowledged=1, acknowledged_by=c["requested_by"], acknowledged_utc=e["acknowledged_utc"])
        return "acknowledged"

    # ------------------------------------------------------------------ status and shutdown
    def finish(self, t):
        if self.event is not None:
            self.event["outcome"] = f"open when monitoring stopped (view {self.mon.state})"
            self._save_event()
            self.event = None

    def status(self) -> dict:
        m = self.mon
        e = self.last_event
        zones = None if not self.cam.zones else (
            "monitoring" if self.zones_ok else "suspended: view not trusted" if not self.analysing else
            "suspended: no steady view" if m.unsettled else "requires_review: not verified for this view")
        state = "DISABLED" if not self.s.enabled else CHECK_FAILED if self.failed else m.state
        return {"enabled": self.s.enabled, "geometry": self.s.geometry, "state": state,
                "trusted": self.analysing, "since_utc": self._utc(m.since), "reference_revision": self.revision,
                "zones": zones, "zones_status": self.zones_status, "warnings": m.warnings,
                "transient_disturbances": m.disturbances, "interrupted_incidents": self.interrupted,
                "check_failures": self.failures,
                "last_event": None if e is None else {k: e.get(k) for k in ("event_id", "event_type", "cause",
                                                                           "confirmed_utc", "recovered_utc", "outcome",
                                                                           "candidate_revision", "acknowledged")}}

    def _publish(self):
        if self.health is not None:
            self.health.set_view(self.status())
