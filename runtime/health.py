"""Camera health: a state per camera, rolling metrics, and process-level resource use.

The worker sets the connection state (CONNECTING, STREAMING, RECONNECTING, STOPPED, ERROR). DEGRADED is derived from
the metrics: a camera that is connected but cannot process adequately must never look like a healthy camera that
simply has no incidents. Only STREAMING counts as monitoring; DEGRADED counts as partial.

The view state (runtime/view.py) is reported beside the connection state, never merged into it: a camera can stream
perfectly while its lens is covered. A view that is not trusted makes monitoring "no"; zones awaiting revalidation
make it "partial".
"""
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone

import psutil

# Monotonic and high-resolution. time.monotonic() ticks every ~15.6 ms on Windows with Python 3.11, which is too coarse
# for frame pacing and latency; perf_counter is monotonic too. Every frame time in the runtime uses this clock.
clock = time.perf_counter

CONNECTING, STREAMING, DEGRADED, RECONNECTING, STOPPED, ERROR = (
    "CONNECTING", "STREAMING", "DEGRADED", "RECONNECTING", "STOPPED", "ERROR")
MONITORING = {STREAMING: "yes", DEGRADED: "partial"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="milliseconds") if dt else None


def _pct(values, q):
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))], 2)


class CameraHealth:
    """Counters are written by the camera's own threads and read by the status thread under a small lock."""

    def __init__(self, camera_id, cfg):
        self.camera_id, self.cfg = camera_id, cfg
        self.lock = threading.Lock()
        self.state, self.reason = CONNECTING, "opening source"
        self.started = clock()
        self.state_since = self.started
        self.connected_s = 0.0  # time spent STREAMING (including DEGRADED) since the worker started
        self.target_fps = None  # analysis rate once the source is open; None when frames are not rate-limited (offline)
        self.source_fps = None
        self.read = self.skipped = self.dropped = self.processed = 0
        self.reconnects = self.attempts = self.errors = self.persist_errors = 0
        self.incidents_opened = self.escalations = 0
        self.queue_depth = self.queue_max = 0
        self.last_error = None
        self.last_frame_utc = self.last_processed_utc = None
        self.last_processed_mono = None
        self.read_times, self.proc_times, self.drop_times, self.persist_fail_times = deque(), deque(), deque(), deque()
        self.infer_ms, self.proc_ms, self.e2e_ms = deque(maxlen=600), deque(maxlen=600), deque(maxlen=600)
        self.incident_ms = deque(maxlen=200)
        self.view = None  # the view guard's status (runtime/view.py), None when view monitoring is off
        self.view_suspended = 0  # frames read while the view was not trusted (checked for recovery, not analysed)
        self.view_ms = deque(maxlen=600)  # duration of each view check

    def set_view(self, view: dict):
        with self.lock:
            self.view = view

    def on_view_check(self, ms):
        with self.lock:
            self.view_ms.append(ms)

    def on_view_suspended(self):
        with self.lock:
            self.view_suspended += 1

    def set_state(self, state, reason=None):
        now = clock()
        with self.lock:
            if self.state == STREAMING:
                self.connected_s += now - self.state_since
            self.state, self.reason, self.state_since = state, reason, now

    def _trim(self, now):
        cut = now - self.cfg.window_s
        for d in (self.read_times, self.proc_times, self.drop_times, self.persist_fail_times):
            while d and d[0] < cut:
                d.popleft()

    def on_read(self, utc):
        now = clock()
        with self.lock:
            self.read += 1
            self.last_frame_utc = utc
            self.read_times.append(now)
            self._trim(now)

    def on_skip(self):
        with self.lock:
            self.skipped += 1

    def on_drop(self, n=1):
        now = clock()
        with self.lock:
            self.dropped += n
            self.drop_times.extend([now] * n)

    def on_queue(self, depth):
        with self.lock:
            self.queue_depth = depth
            self.queue_max = max(self.queue_max, depth)

    def on_processed(self, utc, proc_ms, e2e_ms, infer_ms=None):
        now = clock()
        with self.lock:
            self.processed += 1
            self.last_processed_utc, self.last_processed_mono = utc, now
            self.proc_times.append(now)
            self.proc_ms.append(proc_ms)
            self.e2e_ms.append(e2e_ms)
            if infer_ms is not None:
                self.infer_ms.append(infer_ms)
            self._trim(now)

    def on_error(self, message, persist=False):
        now = clock()
        with self.lock:
            self.errors += 1
            self.last_error = message
            if persist:
                self.persist_errors += 1
                self.persist_fail_times.append(now)

    def snapshot(self) -> dict:
        now = clock()
        with self.lock:
            self._trim(now)
            win = min(self.cfg.window_s, max(1e-6, now - self.state_since)) if self.state == STREAMING else self.cfg.window_s
            proc_fps = len(self.proc_times) / win
            read_fps = len(self.read_times) / win
            drops = len(self.drop_times)
            state, reason = self.state, self.reason
            if state == STREAMING and now - self.state_since >= self.cfg.warmup_s:
                why = []
                if self.target_fps and proc_fps < self.cfg.degraded_ratio * self.target_fps:
                    why.append(f"processing {proc_fps:.1f} FPS, target {self.target_fps:.1f}")
                if drops and drops / (drops + len(self.proc_times)) > self.cfg.max_drop_ratio:
                    why.append(f"{drops} frames dropped under load in {self.cfg.window_s:.0f} s")
                if self.last_processed_mono is None or now - self.last_processed_mono > self.cfg.stall_s:
                    age = "never" if self.last_processed_mono is None else f"{now - self.last_processed_mono:.0f} s ago"
                    why.append(f"last processed frame {age}")
                if self.persist_fail_times:
                    why.append("event persistence failing")
                if why:
                    state, reason = DEGRADED, "; ".join(why)
            connected = self.connected_s + (now - self.state_since if self.state == STREAMING else 0)
            uptime = now - self.started
            monitoring, view = MONITORING.get(state, "no"), self.view
            if view and view.get("enabled") and monitoring != "no":
                if not view["trusted"]:
                    monitoring = "no"
                    reason = f"camera view {view['state']}" + (f": {view['last_event']['cause']}" if view.get("last_event")
                                                               and view["state"] != "INITIALIZING" else "")
                elif view.get("zones") and view["zones"] != "monitoring":
                    monitoring = "partial"
                    reason = "; ".join(x for x in (reason, f"zones {view['zones']}") if x)
                elif view.get("geometry") is False:  # blockage-only: the camera may be pointing anywhere
                    monitoring = "partial"
                    reason = "; ".join(x for x in (reason, "camera position not validated (blockage-only view monitoring)")
                                       if x)
            return {
                "state": state, "reason": reason, "monitoring": monitoring, "view": view,
                "state_for_s": round(now - self.state_since, 1),
                "source_fps": round(self.source_fps, 2) if self.source_fps else None,
                "target_fps": round(self.target_fps, 2) if self.target_fps else None,
                "read_fps": round(read_fps, 2), "processed_fps": round(proc_fps, 2),
                "frames": {"read": self.read, "processed": self.processed, "skipped_by_rate": self.skipped,
                           "dropped_backpressure": self.dropped, "queued": self.queue_depth, "queue_max": self.queue_max,
                           "view_suspended": self.view_suspended},
                "latency_ms": {"inference_p50": _pct(self.infer_ms, 0.5), "inference_p95": _pct(self.infer_ms, 0.95),
                               "processing_p50": _pct(self.proc_ms, 0.5), "processing_p95": _pct(self.proc_ms, 0.95),
                               "end_to_end_p50": _pct(self.e2e_ms, 0.5), "end_to_end_p95": _pct(self.e2e_ms, 0.95),
                               "incident_p50": _pct(self.incident_ms, 0.5), "incident_max": _pct(self.incident_ms, 1.0),
                               "view_check_p50": _pct(self.view_ms, 0.5), "view_check_p95": _pct(self.view_ms, 0.95)},
                "reconnects": self.reconnects, "connect_attempts": self.attempts, "errors": self.errors,
                "persist_errors": self.persist_errors, "last_error": self.last_error,
                "incidents_opened": self.incidents_opened, "escalations": self.escalations,
                "last_frame_utc": iso(self.last_frame_utc), "last_processed_utc": iso(self.last_processed_utc),
                "uptime_s": round(uptime, 1), "connected_s": round(connected, 1),
                "availability": round(connected / uptime, 4) if uptime > 0 else None,
            }


class ProcessMetrics:
    """CPU and memory of this process; GPU memory from torch when it is loaded; GPU utilisation from nvidia-smi."""

    def __init__(self, gpu_every_s=5.0):
        self.proc = psutil.Process()
        self.proc.cpu_percent(None)
        self.gpu_every_s, self.gpu_last, self.gpu = gpu_every_s, 0.0, None
        self.smi = shutil.which("nvidia-smi")

    def _gpu_query(self):
        if not self.smi or time.monotonic() - self.gpu_last < self.gpu_every_s:
            return self.gpu
        self.gpu_last = time.monotonic()
        try:
            out = subprocess.run([self.smi, "--query-gpu=utilization.gpu,memory.used,memory.total,clocks.sm",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()[0]
            u, used, total, clock = (float(x) for x in out.split(","))
            self.gpu = {"utilization_pct": u, "memory_used_mb": used, "memory_total_mb": total, "sm_clock_mhz": clock}
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            self.gpu = None
        return self.gpu

    def snapshot(self) -> dict:
        m = self.proc.memory_info()
        out = {"pid": self.proc.pid, "cpu_pct": round(self.proc.cpu_percent(None), 1), "rss_mb": round(m.rss / 2**20, 1),
               "threads": self.proc.num_threads(), "system_cpu_pct": psutil.cpu_percent(None),
               "gpu": self._gpu_query(), "ui_loaded": "streamlit" in sys.modules}
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            out["torch_cuda_mb"] = {"allocated": round(torch.cuda.memory_allocated() / 2**20, 1),
                                    "max_allocated": round(torch.cuda.max_memory_allocated() / 2**20, 1),
                                    "reserved": round(torch.cuda.memory_reserved() / 2**20, 1)}
        return out
