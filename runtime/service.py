"""The runtime orchestrator: start enabled cameras, report status, and shut down cleanly.

A camera that cannot open, loses its stream or whose pipeline fails changes only its own state; the others carry on.
status.json is written atomically every status_interval_s and once more at shutdown.
"""
import json
import os
import threading
import time

from intelligence.ppe_policy import load as load_ppe
from intelligence.risk import load_policy
from runtime import logs
from runtime.health import ProcessMetrics, iso, utc_now
from runtime.inference import make_backend
from runtime.worker import CameraWorker

NOTE = ("An absence of incidents is not evidence of safety. Check each camera's monitoring state; SafeSight is an "
        "additional monitoring layer, not a safety function.")


class Runtime:
    def __init__(self, cfg, backend=None, sources=None):
        """backend and sources (camera id -> FrameSource) may be injected, for tests."""
        self.cfg, self._backend, self._sources = cfg, backend, sources or {}
        self.backend = None
        self.workers = {}
        self.policy = None
        self.ppe_policy = None
        self.state = "starting"
        self.started_utc = None
        self.stop_requested = threading.Event()
        self.metrics = ProcessMetrics()
        self.log = logs.get()
        self._status_thread = None
        self._status_lock = threading.Lock()  # the status thread and start/stop both write the file

    def start(self):
        c = self.cfg
        for d in (c.database.parent, c.evidence_dir, c.status_file.parent):
            d.mkdir(parents=True, exist_ok=True)
        self.started_utc = utc_now()
        self.policy = load_policy(c.risk_policy) if c.risk_policy else load_policy()
        if self.policy["status"] != "approved":
            self.log.warning("risk policy '%s' is a DRAFT: risk levels are examples until a competent person approves "
                             "a site policy", self.policy["version"])
        self.ppe_policy = load_ppe(c.ppe_policy) if c.ppe_policy else None
        if self.ppe_policy is None:
            self.log.warning("no PPE policy configured: missing head protection is reported for review, never as a "
                             "confirmed violation, until a safety administrator configures where PPE is required")
        elif self.ppe_policy["status"] != "approved":
            self.log.warning("PPE policy '%s' is a DRAFT", self.ppe_policy["version"])
        self.backend = self._backend or make_backend(c.inference)
        for cam in c.cameras:
            if not cam.enabled:
                self.log.info("camera %s is disabled in the configuration", cam.id)
                continue
            w = CameraWorker(cam, c, self.backend, self.policy, source=self._sources.get(cam.id), ppe_policy=self.ppe_policy)
            self.workers[cam.id] = w
            w.start()
        self.state = "running"
        self.log.info("runtime started: %d camera(s), %s inference, status at %s", len(self.workers), self.backend.mode,
                      c.status_file)
        self._status_thread = threading.Thread(target=self._status_loop, name="status", daemon=True)
        self._status_thread.start()
        self.write_status()

    def _status_loop(self):
        while not self.stop_requested.wait(self.cfg.status_interval_s):
            try:
                self.write_status()
            except Exception:
                self.log.exception("could not write status")

    def done(self) -> bool:
        return all(not w.alive for w in self.workers.values())

    def wait(self, exit_when_done=False, duration=None):
        """Block until a stop is requested, the duration has passed, or (exit_when_done) every camera has finished."""
        end = None if duration is None else time.monotonic() + duration
        while not self.stop_requested.wait(0.2):
            if exit_when_done and self.done():
                self.log.info("every camera has finished")
                return
            if end is not None and time.monotonic() >= end:
                self.log.info("run duration reached")
                return

    def stop(self, timeout=20.0) -> list:
        """Stop every camera, flush their sessions, stop inference. Returns cameras that did not stop in time."""
        if self.state == "stopped":
            return []
        self.state = "stopping"
        self.stop_requested.set()
        self.log.info("shutting down %d camera(s)", len(self.workers))
        for w in self.workers.values():
            w.stop()
        deadline = time.monotonic() + timeout
        stuck = [cid for cid, w in self.workers.items() if not w.join(max(0.0, deadline - time.monotonic()))]
        for cid in stuck:
            self.log.error("camera %s did not stop within %.0f s", cid, timeout)
        if self.backend is not None:
            self.backend.stop()
        if self._status_thread is not None:
            self._status_thread.join(timeout=5)
        self.state = "stopped"
        self.write_status()
        self.log.info("shutdown complete")
        return stuck

    def status(self) -> dict:
        cams = {}
        for cam in self.cfg.cameras:
            base = {"name": cam.name, "site": cam.site, "site_name": self.cfg.sites.get(cam.site), "source_type": cam.source["type"]}
            w = self.workers.get(cam.id)
            if w is None:
                cams[cam.id] = {**base, "state": "DISABLED", "monitoring": "no", "reason": "disabled in configuration"}
            else:
                cams[cam.id] = {**base, "source": w.source.describe(), "session_id": w.session_id, **w.health.snapshot()}
        groups = {k: [cid for cid, s in cams.items() if s["monitoring"] == k] for k in ("yes", "partial", "no")}
        return {
            "runtime": {"state": self.state, "pid": os.getpid(), "started_utc": iso(self.started_utc), "updated_utc": iso(utc_now()),
                        "status_interval_s": self.cfg.status_interval_s,
                        "inference": self.backend.stats() if self.backend else None,
                        "risk_policy": {"version": self.policy["version"], "status": self.policy["status"]} if self.policy else None,
                        "ppe_policy": {"version": self.ppe_policy["version"], "status": self.ppe_policy["status"]}
                        if self.ppe_policy else {"status": "unconfigured"},
                        "note": NOTE},
            "process": self.metrics.snapshot(),
            "summary": {"cameras": len(cams), "monitoring": groups["yes"], "partial": groups["partial"],
                        "not_monitoring": groups["no"]},
            "cameras": cams,
        }

    def write_status(self):
        path = self.cfg.status_file
        tmp = path.with_suffix(".tmp")
        with self._status_lock:
            tmp.write_text(json.dumps(self.status(), indent=1), encoding="utf-8")
            for _ in range(10):  # on Windows a reader holding the file open makes the replace fail briefly
                try:
                    os.replace(tmp, path)
                    return
                except PermissionError:
                    time.sleep(0.05)
            self.log.warning("status file busy; skipped one update")
