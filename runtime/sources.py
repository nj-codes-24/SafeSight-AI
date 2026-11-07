"""Camera sources. A source opens, delivers BGR frames, and closes; the camera worker adds timing, rate selection,
queueing and reconnection (runtime/worker.py). New source types (for example ONVIF discovery resolving to an RTSP URI)
register in SOURCE_TYPES and validate their own options.

Credentials never live in configuration: an RTSP source names the environment variables that hold them, reads them at
connect time, registers them for log redaction, and describes itself without them.
"""
import os
import threading
import time
from urllib.parse import quote, urlsplit

import cv2
import numpy as np

from runtime.logs import redact_url, register_secret

SECRET_QUERY = ("pass", "pwd", "token", "key", "secret", "user", "auth")


class SourceError(Exception):
    """A source failed. fatal=True means retrying cannot help (for example missing credentials)."""

    def __init__(self, message, fatal=False):
        super().__init__(message)
        self.fatal = fatal


class FrameSource:
    type = ""
    OPTIONS: set = set()
    REQUIRED: set = set()
    live = True  # frames arrive in real time: drop the oldest when processing lags. False: read only as fast as processed.
    paced = False  # the worker sleeps between frames to replay a file at its own frame rate

    def __init__(self, options: dict, camera_id: str):
        self.options, self.camera_id = options, camera_id
        self.fps = 0.0
        self.discontinuity = False  # set when the content jumps (a looping file restarted)

    @classmethod
    def validate(cls, options: dict) -> None:
        extra = set(options) - cls.OPTIONS
        if extra:
            raise ValueError(f"{cls.type} source does not take {', '.join(sorted(extra))}")
        missing = cls.REQUIRED - set(options)
        if missing:
            raise ValueError(f"{cls.type} source needs {', '.join(sorted(missing))}")

    def open(self):
        raise NotImplementedError

    def read(self):
        """Next frame, or None at the end of a finite source. Raises SourceError when the stream fails."""
        raise NotImplementedError

    def skip(self):
        """Advance past one frame that will not be analysed, as cheaply as possible (no colour conversion or copy).
        True, or None at the end of a finite source. Raises SourceError like read()."""
        return True if self.read() is not None else None

    def close(self):
        pass

    def describe(self) -> str:
        return self.type

    def take_discontinuity(self) -> bool:
        d, self.discontinuity = self.discontinuity, False
        return d


class FileSource(FrameSource):
    """A video file: replayed at its own frame rate as a stand-in for a camera (realtime), or read as fast as it can be
    processed (realtime: false) for reproducible evaluation."""
    type = "file"
    OPTIONS = {"path", "loop", "realtime"}
    REQUIRED = {"path"}

    def __init__(self, options, camera_id):
        super().__init__(options, camera_id)
        from runtime.config import _path

        self.path = _path(options["path"])
        self.loop = bool(options.get("loop", False))
        self.live = self.paced = bool(options.get("realtime", True))
        self.cap, self.pos, self.frames, self.reads_since_open = None, 0, 0, 0

    @classmethod
    def validate(cls, options):
        super().validate(options)
        for k in ("loop", "realtime"):
            if k in options and not isinstance(options[k], bool):
                raise ValueError(f"{k} must be true or false")

    def open(self):
        if not self.path.exists():
            raise SourceError(f"file not found: {self.path.name}")
        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            cap.release()
            raise SourceError(f"cannot open video file {self.path.name}")
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if self.pos:  # reopened after a read error: continue where it stopped
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.pos)
        self.cap, self.reads_since_open = cap, 0

    def _next(self, decode):
        ok, frame = self.cap.read() if decode else (self.cap.grab(), True)
        if ok:
            self.pos += 1
            self.reads_since_open += 1
            return frame
        # Mid-file failure: reopen and resume. But failing again straight after a reopen at the same place means the
        # container over-reported its frame count (common): that is the end of the file, not an error to retry forever.
        if self.frames and self.pos < self.frames - 1 and (self.reads_since_open or not self.pos):
            raise SourceError(f"read failed at frame {self.pos} of {self.frames} in {self.path.name}")
        if not self.loop:
            return None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.pos, self.discontinuity = 0, True
        ok, frame = self.cap.read() if decode else (self.cap.grab(), True)
        if not ok:
            raise SourceError(f"cannot restart {self.path.name}")
        self.pos = 1
        return frame

    def read(self):
        return self._next(True)

    def skip(self):  # grab() without retrieve(): about 0.4 ms instead of 3.9 ms for a 720p demo frame
        return self._next(False)

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def describe(self):
        return f"file:{self.path.name}"


_ffmpeg_env = threading.Lock()  # OpenCV reads its FFmpeg options from a process-wide variable at open time


class RtspSource(FrameSource):
    """An RTSP camera through OpenCV's FFmpeg backend, with open and read timeouts so a dead camera cannot hang a thread."""
    type = "rtsp"
    OPTIONS = {"url", "username_env", "password_env", "transport", "open_timeout_s", "read_timeout_s"}
    REQUIRED = {"url"}

    @classmethod
    def validate(cls, options):
        super().validate(options)
        u = urlsplit(str(options["url"]))
        if u.scheme not in ("rtsp", "rtsps") or not u.hostname:
            raise ValueError("url must be rtsp://host[:port]/path or rtsps://…")
        if u.username or u.password:
            raise ValueError("credentials must not be in the url; use username_env and password_env")
        if any(s in u.query.lower() for s in SECRET_QUERY):
            raise ValueError("the url query looks like it carries credentials; use username_env and password_env")
        if options.get("transport", "tcp") not in ("tcp", "udp"):
            raise ValueError("transport must be tcp or udp")
        for k in ("open_timeout_s", "read_timeout_s"):
            v = options.get(k, 10)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.5 <= v <= 120:
                raise ValueError(f"{k} must be between 0.5 and 120 seconds")
        for k in ("username_env", "password_env"):
            if k in options and not str(options[k]).replace("_", "").isalnum():
                raise ValueError(f"{k} must be an environment variable name")

    def __init__(self, options, camera_id):
        super().__init__(options, camera_id)
        self.cap = None

    def _url(self) -> str:
        u = urlsplit(self.options["url"])
        names = [self.options.get("username_env"), self.options.get("password_env")]
        values = []
        for n in names:
            if n:
                v = os.environ.get(n)
                if v is None:
                    raise SourceError(f"credentials not available: environment variable {n} is not set", fatal=True)
                register_secret(v)
                values.append(quote(v, safe=""))
            else:
                values.append(None)
        if values[0] is None and values[1] is None:
            return self.options["url"]
        userinfo = (values[0] or "") + (f":{values[1]}" if values[1] is not None else "")
        return u._replace(netloc=f"{userinfo}@{u.netloc}").geturl()

    def open(self):
        url = self._url()
        params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(1000 * self.options.get("open_timeout_s", 10)),
                  cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(1000 * self.options.get("read_timeout_s", 10))]
        with _ffmpeg_env:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self.options.get('transport', 'tcp')}"
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
        if not cap.isOpened():
            cap.release()
            raise SourceError(f"cannot connect to {self.describe()}")
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        if not 1 <= self.fps <= 240:  # some cameras report nonsense; assume a common rate
            self.fps = 25.0
        self.cap = cap

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            raise SourceError(f"stream read failed or timed out: {self.describe()}")
        return frame

    def skip(self):
        if not self.cap.grab():
            raise SourceError(f"stream read failed or timed out: {self.describe()}")
        return True

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def describe(self):
        return redact_url(self.options["url"])


class SyntheticSource(FrameSource):
    """A generated test pattern: a bright upright box (a stand-in "person") on a dark background. For tests and for
    exercising the runtime without footage; the real model will not detect anything in it.

    patterns: walk (left-right and back), static (centre), cycle (left half then right half, alternately), empty.
    faults (tests only): read_fail_at (frame numbers at which one read fails, each once), open_failures (failed
    attempts after each read failure), never_opens.
    """
    type = "synthetic"
    OPTIONS = {"fps", "width", "height", "frames", "pattern", "period", "realtime", "faults"}
    PATTERNS = ("walk", "static", "cycle", "empty")

    @classmethod
    def validate(cls, options):
        super().validate(options)
        if options.get("pattern", "walk") not in cls.PATTERNS:
            raise ValueError(f"pattern must be one of {', '.join(cls.PATTERNS)}")
        faults = options.get("faults") or {}
        if set(faults) - {"read_fail_at", "open_failures", "never_opens"}:
            raise ValueError("faults: read_fail_at, open_failures, never_opens")

    def __init__(self, options, camera_id):
        super().__init__(options, camera_id)
        self.fps = float(options.get("fps", 25))
        self.w, self.h = int(options.get("width", 320)), int(options.get("height", 240))
        self.limit = options.get("frames")
        self.pattern = options.get("pattern", "walk")
        self.period = int(options.get("period", 100))
        self.live = self.paced = bool(options.get("realtime", False))
        f = options.get("faults") or {}
        self.fail_at = set(f.get("read_fail_at", []))
        self.open_failures = int(f.get("open_failures", 0))
        self.never_opens = bool(f.get("never_opens", False))
        self.pending_open_failures = 0
        self.n, self.opened, self.opens, self.closed, self.drawn = 0, False, 0, 0, 0

    def open(self):
        self.opens += 1
        if self.never_opens:
            raise SourceError("synthetic source configured never to open")
        if self.pending_open_failures:
            self.pending_open_failures -= 1
            raise SourceError("synthetic source still down")
        self.opened = True

    def position(self, n):
        """Centre x of the box in frame n, or None when the frame is empty."""
        if self.pattern == "empty":
            return None
        if self.pattern == "static":
            return self.w // 2
        if self.pattern == "cycle":
            return self.w // 4 if (n // self.period) % 2 == 0 else 3 * self.w // 4
        k = n % (2 * self.period)
        span = self.w - 40
        return 20 + int(span * (k if k < self.period else 2 * self.period - k) / self.period)

    def skip(self):
        return True if self._next(False) is not None else None

    def read(self):
        return self._next(True)

    def _next(self, draw):
        if not self.opened:
            raise SourceError("synthetic source is not open")
        if self.limit is not None and self.n >= self.limit:
            return None
        if self.n in self.fail_at:
            self.fail_at.discard(self.n)
            self.opened = False
            self.pending_open_failures = self.open_failures
            raise SourceError(f"synthetic read failure at frame {self.n}")
        if not draw:
            self.n += 1
            return True
        self.drawn += 1
        im = np.full((self.h, self.w, 3), 30, np.uint8)
        x = self.position(self.n)
        if x is not None:
            bw, bh = max(6, self.w // 16), max(18, self.h // 4)
            y1 = self.h // 2 - bh // 2
            im[y1:y1 + bh, max(0, x - bw // 2):x + bw // 2] = 230
        im[0, 0] = (self.n % 256, (self.n // 256) % 256, 0)  # frame number, so a test can tell which frames were processed
        self.n += 1
        return im

    def close(self):
        self.opened = False
        self.closed += 1

    def describe(self):
        return f"synthetic:{self.pattern}"


SOURCE_TYPES = {s.type: s for s in (FileSource, RtspSource, SyntheticSource)}


def make_source(options: dict, camera_id: str) -> FrameSource:
    opts = {k: v for k, v in options.items() if k != "type"}
    return SOURCE_TYPES[options["type"]](opts, camera_id)


def sleep_until(deadline: float, stop) -> bool:
    """Sleep until a deadline on the runtime clock (time.perf_counter) unless stop is set first; True if stopped."""
    while True:
        left = deadline - time.perf_counter()
        if left <= 0:
            return stop.is_set()
        if left < 0.05:  # time.sleep is high-resolution; Event.wait can round up to the system timer tick (~15 ms)
            time.sleep(left)
        elif stop.wait(min(left, 0.25)):
            return True
