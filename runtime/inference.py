"""Inference backends: how camera workers share the model. Tracking always stays per camera.

- batched (default): one inference thread gathers the frames cameras are waiting on (at most one per camera, so the
  request queue is bounded by the number of cameras) and runs them as one batch. Profiled on the development GPU:
  15 ms for one frame, 4.8 ms per frame in a batch of four (docs/product_research/15 §3.3).
- shared: one model behind a lock. Ultralytics does not document predict as thread-safe on a shared instance.
- per_camera: a model per camera, no lock (memory per camera, no batching); kept for comparison.
- null: no model and no detections; for checking cameras and the runtime without a GPU.

Each camera gets a Detector that shares the model but owns its ByteTrack instance.
"""
import queue
import threading
import time
from collections import deque
from concurrent.futures import Future

import numpy as np

from runtime import logs

log = logs.get("inference")


class NullDetector:
    names = {0: "person", 1: "helmet", 2: "no_helmet"}

    def reset(self):
        pass

    def track(self, frame, *args):
        return [], []


class Backend:
    mode = ""

    def __init__(self):
        self.latencies = deque(maxlen=2000)  # model call durations, ms
        self.calls = 0

    def detector_for(self, camera_id):
        raise NotImplementedError

    def release(self, camera_id):
        """The camera has stopped and will send no more frames."""

    def stop(self):
        pass

    def _timed(self, fn):
        def call(frame):
            t0 = time.perf_counter()
            try:
                return fn(frame)
            finally:
                self.latencies.append(1000 * (time.perf_counter() - t0))
                self.calls += 1
        return call

    def stats(self) -> dict:
        lat = sorted(self.latencies)
        out = {"mode": self.mode, "calls": self.calls}
        if lat:
            out.update(model_ms_p50=round(lat[len(lat) // 2], 2), model_ms_p95=round(lat[int(0.95 * (len(lat) - 1))], 2))
        return out


class NullBackend(Backend):
    mode = "null"

    def detector_for(self, camera_id):
        return NullDetector()


def _load(cfg):
    if not cfg.weights.exists():
        raise FileNotFoundError(f"model weights not found at {cfg.weights} (see models/README.md)")
    from inference.detector import Detector  # imports torch; only when a model is really needed

    det = Detector(cfg.weights, cfg.imgsz, None if cfg.device == "auto" else cfg.device)
    det.predict(np.zeros((cfg.imgsz, cfg.imgsz, 3), np.uint8))  # warm up CUDA before cameras start
    log.info("model loaded: %s on %s (%s backend)", cfg.weights.name, det.device, cfg.backend)
    return det


class SharedBackend(Backend):
    mode = "shared"

    def __init__(self, cfg, base=None):
        super().__init__()
        self.cfg = cfg
        self.base = base or _load(cfg)
        self.lock = threading.Lock()

    def _predict(self, frame):
        with self.lock:
            return self.base.predict(frame)

    def detector_for(self, camera_id):
        from inference.detector import Detector

        return Detector(model=self.base.model, imgsz=self.base.imgsz, device=self.base.device, predict=self._timed(self._predict))


class PerCameraBackend(Backend):
    mode = "per_camera"

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        _load(cfg)  # fail at startup, not in the first camera thread, if the weights are missing

    def detector_for(self, camera_id):
        from inference.detector import Detector

        det = Detector(self.cfg.weights, self.cfg.imgsz, None if self.cfg.device == "auto" else self.cfg.device)
        det._predict = self._timed(det.predict)
        return det


class BatchedBackend(Backend):
    mode = "batched"

    def __init__(self, cfg, base=None):
        super().__init__()
        self.cfg = cfg
        self.base = base or _load(cfg)
        self.requests = queue.Queue()
        self.batch_sizes = deque(maxlen=2000)
        self.cameras = 0  # registered cameras: never wait for more frames than there are cameras to send them
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="inference-batcher", daemon=True)
        self.thread.start()

    def submit(self, frame):
        if not self.running:
            raise RuntimeError("inference backend stopped")
        fut = Future()
        self.requests.put((frame, fut))
        return fut.result(timeout=self.cfg.timeout_s)

    def _loop(self):
        wait = self.cfg.batch_wait_ms / 1000
        while self.running:
            try:
                batch = [self.requests.get(timeout=0.1)]
            except queue.Empty:
                continue
            deadline = time.perf_counter() + wait
            while len(batch) < min(self.cfg.max_batch, self.cameras):
                try:
                    batch.append(self.requests.get(timeout=max(0.0, deadline - time.perf_counter())))
                except queue.Empty:
                    break
            t0 = time.perf_counter()
            try:
                boxes = self.base.predict_batch([f for f, _ in batch])
                for (_, fut), b in zip(batch, boxes):
                    fut.set_result(b)
            except Exception as e:  # every waiting camera sees the failure; the thread keeps serving
                log.exception("batched inference failed for %d frame(s)", len(batch))
                for _, fut in batch:
                    if not fut.done():
                        fut.set_exception(e)
            per_frame = 1000 * (time.perf_counter() - t0) / len(batch)
            self.latencies.extend([per_frame] * len(batch))
            self.calls += len(batch)
            self.batch_sizes.append(len(batch))

    def detector_for(self, camera_id):
        from inference.detector import Detector

        self.cameras += 1
        return Detector(model=self.base.model, imgsz=self.base.imgsz, device=self.base.device, predict=self.submit)

    def release(self, camera_id):
        self.cameras = max(0, self.cameras - 1)

    def stop(self):
        self.running = False
        self.thread.join(timeout=5)
        while True:
            try:
                _, fut = self.requests.get_nowait()
            except queue.Empty:
                break
            fut.set_exception(RuntimeError("inference backend stopped"))

    def stats(self) -> dict:
        out = super().stats()
        if self.batch_sizes:
            out["mean_batch"] = round(sum(self.batch_sizes) / len(self.batch_sizes), 2)
        return out


def make_backend(cfg) -> Backend:
    return {"null": lambda: NullBackend(), "shared": lambda: SharedBackend(cfg), "per_camera": lambda: PerCameraBackend(cfg),
            "batched": lambda: BatchedBackend(cfg)}[cfg.backend]()
