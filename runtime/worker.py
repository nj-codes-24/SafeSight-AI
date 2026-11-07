"""One camera: a capture thread, a bounded frame queue, and a processing thread that owns the camera's Pipeline.

Capture reads every frame the source delivers, timestamps it (monotonic for durations, UTC for records), keeps at most
max_fps of them (the rest are skipped by design), and queues them. The queue is bounded: for live sources the oldest
frame is dropped when processing lags (counted, never silent); offline files block instead, so every selected frame
is processed. Dropping happens only before inference, so a state change can never be lost to backpressure.

Processing owns everything stateful for this camera: the tracker (through its own Detector), PPE votes, zones,
incidents, and its own SQLite connection. After a gap longer than lost_track_seconds, or when a looping file restarts,
all tracks are closed at the last observed time and new track IDs continue past every ID already issued in the session.

Before a frame is analysed the view guard (runtime/view.py) checks, every few frames, that the camera still shows its
registered view. While the view is not trusted (changed, switched, blocked, unverified, recovering) frames are still
checked but not analysed: no detection, no incident, and the inference backend is not asked for anything.
"""
import sqlite3
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from database.database import IncidentDB
from runtime import logs
from runtime.config import pipeline_settings
from runtime.health import CONNECTING, ERROR, RECONNECTING, STOPPED, STREAMING, CameraHealth, clock, iso, utc_now
from runtime.sources import SourceError, make_source, sleep_until

MAX_CONSECUTIVE_ERRORS = 5  # failed frames in a row before the camera's pipeline is declared failed


@dataclass
class Frame:
    image: np.ndarray
    index: int  # frames delivered by the source since the worker started
    t: float  # seconds: media time for offline sources, monotonic time since the worker started for live ones
    mono: float  # runtime clock (time.perf_counter: monotonic, high resolution) at capture
    utc: datetime  # wall clock at capture
    segment: int  # connection number; a new segment starts after every (re)connect
    discontinuity: bool = False  # the content jumped (a looping file restarted)


class FrameQueue:
    def __init__(self, maxsize, drop_oldest):
        self.items, self.maxsize, self.drop_oldest = deque(), maxsize, drop_oldest
        self.cond = threading.Condition()
        self.closed = False

    def put(self, item, stop) -> int:
        """Queue an item; returns how many queued frames were dropped to make room (drop_oldest only)."""
        dropped = 0
        with self.cond:
            while len(self.items) >= self.maxsize:
                if self.drop_oldest:
                    self.items.popleft()
                    dropped += 1
                elif stop.is_set() or self.closed:
                    return dropped
                else:
                    self.cond.wait(0.1)
            self.items.append(item)
            self.cond.notify_all()
        return dropped

    def get(self, timeout):
        with self.cond:
            if not self.items and not self.closed:
                self.cond.wait(timeout)
            if self.items:
                item = self.items.popleft()
                self.cond.notify_all()
                return item
            return None

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()

    def __len__(self):
        return len(self.items)


class CameraWorker:
    def __init__(self, camera, rcfg, backend, policy, source=None, ppe_policy=None):
        self.cam, self.rcfg, self.backend, self.policy = camera, rcfg, backend, policy
        self.ppe_policy = ppe_policy  # None: every PPE requirement is unconfigured (review, never a confirmed violation)
        self.log = logs.get(f"camera.{camera.id}")
        self.health = CameraHealth(camera.id, camera.health)
        self.source = source or make_source(camera.source, camera.id)
        self.queue = FrameQueue(camera.processing.queue_size, drop_oldest=self.source.live)
        self.control = deque()  # coverage-gap notices from capture to processing (never dropped)
        self.stop_event = threading.Event()
        self.session_id = f"S{datetime.now():%Y%m%d-%H%M%S}-{camera.id}-{uuid.uuid4().hex[:4]}"
        self.settings = pipeline_settings(rcfg, camera)
        self.end_reason = None
        self.summary = None
        self.pipeline = None
        self.view = None  # runtime/view.py ViewGuard, created with the pipeline when view monitoring is enabled
        self.fps = None  # analysis rate, known once the source is open
        self._db = self._ref = self._outage = None
        self._infer_ms = None
        self._threads = [threading.Thread(target=self._capture, name=f"capture-{camera.id}", daemon=True),
                         threading.Thread(target=self._process, name=f"process-{camera.id}", daemon=True)]

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        self.log.info("starting camera '%s' (site %s, source %s, session %s)", self.cam.name, self.cam.site or "-",
                      self.source.describe(), self.session_id)
        for t in self._threads:
            t.start()

    def stop(self, reason="shutdown"):
        self.end_reason = self.end_reason or reason
        self.stop_event.set()

    def join(self, timeout=None) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        for t in self._threads:
            t.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
        return not self.alive

    @property
    def alive(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    # ------------------------------------------------------------------ capture thread
    def _capture(self):
        src, cam, h, rc = self.source, self.cam, self.health, self.cam.reconnect
        delay, failures, segment, delivered = rc.initial_delay_s, 0, 0, 0
        mono0, due, outage, connected_once = clock(), None, False, False
        max_fps = cam.processing.max_fps
        step = 1 / max_fps if max_fps else 0.0
        try:
            while not self.stop_event.is_set():
                try:
                    with h.lock:
                        h.attempts += 1
                    src.open()
                except SourceError as e:
                    failures += 1
                    msg = str(e)
                    if not outage:
                        self.control.append(("outage_start", utc_now(), msg))
                        outage = True
                    if e.fatal or (rc.max_attempts and failures >= rc.max_attempts):
                        why = msg if e.fatal else f"gave up after {failures} failed attempts: {msg}"
                        h.on_error(msg)
                        h.set_state(ERROR, why)
                        self.end_reason = self.end_reason or f"error: {why}"
                        self.log.error("camera not monitoring: %s", why)
                        break
                    h.set_state(RECONNECTING if connected_once else CONNECTING,
                                f"attempt {failures} failed: {msg}; next try in {delay:.1f} s")
                    self.log.warning("cannot open source (attempt %d): %s; retrying in %.1f s", failures, msg, delay)
                    if self.stop_event.wait(delay):
                        break
                    delay = min(delay * 2, rc.max_delay_s)
                    continue

                if connected_once:
                    with h.lock:
                        h.reconnects += 1
                    self.log.info("reconnected after %d attempt(s)", failures)
                if outage:
                    self.control.append(("outage_end", utc_now()))
                    outage = False
                failures, delay, connected_once = 0, rc.initial_delay_s, True
                segment += 1
                fps = src.fps or 25.0
                self.fps = min(fps, max_fps) if max_fps else fps
                h.source_fps, h.target_fps = fps, (self.fps if src.live else None)
                h.set_state(STREAMING)
                pace0, n_seg, pending_disc = clock(), 0, False
                try:
                    while not self.stop_event.is_set():
                        if src.paced and sleep_until(pace0 + n_seg / fps, self.stop_event):
                            break
                        n_seg += 1
                        # Rate selection on a due-time schedule, so the average rate is max_fps whatever the source
                        # rate (a "since last frame" rule would turn 15 of 50 FPS into every 4th frame, 12.5 FPS).
                        # Decided before reading, so a skipped frame is only grabbed, never converted or copied.
                        t_next = delivered / fps if not src.live else clock() - mono0
                        skip = bool(step) and due is not None and not pending_disc and t_next < due - 1e-6
                        img = src.skip() if skip else src.read()
                        if img is None:
                            self.end_reason = self.end_reason or "end of stream"
                            self.log.info("end of stream after %d frames", delivered)
                            return
                        now, utc = clock(), utc_now()
                        h.on_read(utc)
                        t = delivered / fps if not src.live else now - mono0
                        delivered += 1
                        disc = src.take_discontinuity() or pending_disc
                        if disc and src.paced:
                            pace0, n_seg = now, 1
                        if skip:  # a loop restart on a skipped frame is carried to the next analysed frame
                            pending_disc = disc
                            h.on_skip()
                            continue
                        pending_disc = False
                        due = t + step if due is None or disc or t - due > step else due + step
                        dropped = self.queue.put(Frame(img, delivered - 1, t, now, utc, segment, disc), self.stop_event)
                        if dropped:
                            h.on_drop(dropped)
                        h.on_queue(len(self.queue))
                except SourceError as e:
                    msg = str(e)
                    h.on_error(msg)
                    self.control.append(("outage_start", utc_now(), msg))
                    outage = True
                    h.set_state(RECONNECTING, msg)
                    self.log.warning("stream lost: %s; reconnecting in %.1f s", msg, delay)
                    src.close()
                    if self.stop_event.wait(delay):
                        break
        except Exception as e:  # anything unexpected stops this camera only
            self.log.exception("capture failed")
            h.on_error(f"capture failed: {e}")
            h.set_state(ERROR, f"capture failed: {e}")
            self.end_reason = self.end_reason or f"error: capture failed: {e}"
        finally:
            try:
                src.close()
            finally:
                self.queue.close()

    # ------------------------------------------------------------------ processing thread
    def _timed(self, fn):
        def call(frame):
            t0 = time.perf_counter()
            try:
                return fn(frame)
            finally:
                self._infer_ms = 1000 * (time.perf_counter() - t0)
        return call

    def _make_pipeline(self, db, detector):
        from inference.tracker import Pipeline

        return Pipeline(detector, self.fps or self.source.fps or 25.0, self.settings, self.cam.id, zones=self.cam.zones, db=db,
                        session_id=self.session_id, policy=self.policy, evidence_dir=self.rcfg.evidence_dir,
                        listener=self._on_event, annotate=self.cam.processing.annotate, ppe_policy=self.ppe_policy,
                        site=self.cam.site)

    def _on_event(self, event, iid, kind, track_id, zone, video_t):
        """Incident opened or closed: record camera, site, session, camera-scoped worker and UTC time."""
        ref = self._ref
        utc = ref.utc + timedelta(seconds=video_t - ref.t) if ref is not None else utc_now()
        if event == "opened":
            self._db.add_incident_context(iid, self.session_id, self.cam.id, self.cam.site,
                                          f"{self.cam.id}/{self.session_id}/W{track_id}", iso(utc), round(video_t, 3))
        else:
            self._db.close_incident_context(iid, iso(utc), round(video_t, 3))

    def _drain_control(self, db):
        while self.control:
            msg = self.control.popleft()
            if msg[0] == "outage_start" and self._outage is None:
                self._outage = db.add_outage(self.session_id, self.cam.id, iso(msg[1]), msg[2])
            elif msg[0] == "outage_end" and self._outage is not None:
                db.end_outage(self._outage, iso(msg[1]))
                self._outage = None

    def _process(self):
        h, cam = self.health, self.cam
        db, last, consecutive, segment = None, None, 0, None
        lost = self.settings["lost_track_seconds"]
        try:
            db = self._db = IncidentDB(self.rcfg.database)
            db.start_runtime_session(self.session_id, cam.id, cam.name, cam.site, cam.source["type"], self.source.describe(),
                                     iso(utc_now()), self.policy.get("version"), self.policy.get("status"))
            detector = self.backend.detector_for(cam.id)
            if hasattr(detector, "_predict"):
                detector._predict = self._timed(detector._predict)
            while True:
                self._drain_control(db)
                frame = self.queue.get(0.25)
                h.on_queue(len(self.queue))
                if frame is None:
                    if self.queue.closed and not len(self.queue):
                        break
                    continue
                if self.pipeline is None:
                    self.pipeline = self._make_pipeline(db, detector)
                    if cam.view.enabled:
                        from runtime.view import ViewGuard

                        self.view = ViewGuard(cam, db, self.session_id, self.rcfg.evidence_dir, self.log, h)
                if last is not None and (frame.discontinuity or (self.source.live and frame.t - last.t > lost)):
                    self.pipeline.reset_tracks(last.t)  # tracks end where they were last seen
                    self.log.info("tracks reset after a %s", "loop restart" if frame.discontinuity else
                                  f"{frame.t - last.t:.1f} s gap")
                self._ref, self._infer_ms = frame, None
                t0 = time.perf_counter()
                if self.view is not None:
                    try:
                        self.view.poll_commands(time.monotonic(), self.pipeline)
                        self.view.observe(frame.image, frame.t, frame.utc, frame.discontinuity or frame.segment != segment,
                                          self.pipeline)
                    except sqlite3.Error as e:
                        h.on_error(f"view event persistence failed: {e}", persist=True)
                        self.log.error("view event persistence failed at t=%.2f s: %s", frame.t, e)
                    except Exception as e:  # a failing view check fails safe (not trusted), never stops the camera
                        h.on_error(f"view check failed: {e}")
                        self.view.on_failure(e, frame.t, self.pipeline)
                    segment = frame.segment
                    if not self.view.analysing:  # checked for recovery only: nothing here is evidence
                        h.on_view_suspended()
                        h.on_processed(frame.utc, 1000 * (time.perf_counter() - t0), 1000 * (clock() - frame.mono))
                        last = frame  # tracks were reset when the view stopped being trusted; this is not a gap
                        continue
                try:
                    self.pipeline.process(frame.image, frame.t)
                    consecutive = 0
                except sqlite3.Error as e:
                    h.on_error(f"event persistence failed: {e}", persist=True)
                    self.log.error("event persistence failed at t=%.2f s: %s", frame.t, e)
                except Exception as e:
                    consecutive += 1
                    h.on_error(f"processing failed: {e}")
                    self.log.exception("processing failed at t=%.2f s (%d in a row)", frame.t, consecutive)
                    if consecutive >= MAX_CONSECUTIVE_ERRORS:
                        why = f"inference pipeline failed {consecutive} times in a row: {e}"
                        h.set_state(ERROR, why)
                        self.end_reason = self.end_reason or f"error: {why}"
                        self.log.error("camera not monitoring: %s", why)
                        break
                    continue
                done = clock()
                e2e = 1000 * (done - frame.mono)
                h.on_processed(frame.utc, 1000 * (time.perf_counter() - t0), e2e, self._infer_ms)
                for a in self.pipeline.incidents.drain_alerts():
                    with h.lock:
                        h.incidents_opened += 1
                        h.incident_ms.append(e2e)
                    self.log.warning("incident %s: %s (%s) risk %s zone %s worker %s/W%s t=%.1f s", a["incident_id"], a["type"],
                                     a.get("hazard", "-"), a.get("risk", "-"), a["zone"] or "-", self.session_id, a["worker_id"],
                                     a["video_t"])
                for n in self.pipeline.lifecycle.drain_notifications():
                    self.log.info("notification %s (%s): %s on %s, groups %s", n["notification_id"], n["kind"], n["incident_type"],
                                  self.cam.id, ",".join(n["group_ids"]))
                for e in self.pipeline.incidents.drain_escalations():
                    with h.lock:
                        h.escalations += 1
                    self.log.warning("incident %s escalated %s -> %s at t=%.1f s", e["incident_id"], e["from"], e["to"],
                                     e["video_t"])
                last = frame
        except Exception as e:
            self.log.exception("processing thread failed")
            h.on_error(f"processing thread failed: {e}")
            h.set_state(ERROR, f"processing thread failed: {e}")
            self.end_reason = self.end_reason or f"error: {e}"
        finally:
            self.stop_event.set()  # capture must not outlive processing
            self.queue.close()
            self._finish(db, last)

    def _finish(self, db, last):
        h = self.health
        if hasattr(self.backend, "release"):
            self.backend.release(self.cam.id)
        try:
            if self.pipeline is not None:
                self._ref = last
                self.summary = self.pipeline.finish(f"camera:{self.cam.id}", t=last.t if last else None)
            if self.view is not None:
                self.view.finish(last.t if last else None)
            if db is not None:
                self._drain_control(db)
                if self._outage is not None:
                    db.end_outage(self._outage, iso(utc_now()))
                db.end_runtime_session(self.session_id, iso(utc_now()), self.end_reason or "stopped", h.read, h.processed,
                                       h.skipped, h.dropped, h.reconnects)
        except Exception:
            self.log.exception("could not finalise the session")
        finally:
            if db is not None:
                db.close()
            if h.state != ERROR:
                h.set_state(STOPPED, self.end_reason or "stopped")
            self.log.info("camera stopped (%s): %d frames read, %d processed, %d skipped by rate, %d dropped under load",
                          self.end_reason or "stopped", h.read, h.processed, h.skipped, h.dropped)
