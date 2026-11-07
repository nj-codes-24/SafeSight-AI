"""Camera view monitoring: is the image still the camera's registered view, and can anything be seen in it at all?

Connection health (runtime/health.py) says frames arrive. This says whether they can be trusted: a camera with a healthy
RTSP connection can be covered, knocked off its aim, zoomed, or streaming another camera's scene.

Per check (every check_interval_s of video time, on a small grey copy of the frame, about 2-4 ms):

1. Observability, contrast-normalised so that lighting does not decide it: a near-uniform image (std below blank_std:
   covered lens, black or white frame) or, once a reference exists, a collapse of structure (features and sharpness
   relative to contrast, both against the reference) is UNOBSERVABLE.
2. Geometry against the reference: ORB features of the current frame are matched to the reference's and a similarity
   transform (shift, rotation, scale) is fitted with RANSAC. The reference is the temporal median of the first stable
   seconds, so workers and vehicles that were moving are not in it: their features have no counterpart and fall out as
   outliers. The camera's own motion moves every background feature together, which is what the fit measures. The
   result is the largest displacement of the image corners and centre as a share of the image width (zone polygons
   are in the same normalised coordinates, so this is directly the error a zone would have). MATCH within max_shift,
   SHIFTED beyond it with enough inliers, NO_MATCH with too few.
3. Continuity with the previous check (same fit), only to tell an abrupt cut from movement.

One check proves nothing: the states below need the evidence to persist (time in video seconds, not check counts):

    INITIALIZING  -> VIEW_STABLE              reference established (no stored reference) or the stored one verified
    VIEW_STABLE   -> VIEW_CHANGE_SUSPECTED    any check that is not MATCH
    SUSPECTED     -> VIEW_STABLE              a MATCH: a transient disturbance (person or forklift passing, flicker)
    SUSPECTED     -> VIEW_CHANGED             not MATCH for confirm_s (cut: no continuity at the first bad check)
    SUSPECTED     -> BLOCKED                  mostly UNOBSERVABLE for blocked_confirm_s
    VIEW_CHANGED  -> VIEW_UNVERIFIED          a self-consistent different view held for unverified_after_s
    BLOCKED, VIEW_CHANGED, VIEW_UNVERIFIED -> RECOVERING   a MATCH with the registered reference
    RECOVERING    -> VIEW_STABLE              MATCH held for recover_s; any other check goes back
    BLOCKED       -> VIEW_CHANGED             observable again but not the registered view for confirm_s
    VIEW_CHANGED / VIEW_UNVERIFIED -> BLOCKED UNOBSERVABLE for blocked_confirm_s
    any           -> VIEW_STABLE              an operator accepts a new reference (accept()); never automatic

The reference is never replaced automatically. Only VIEW_STABLE and VIEW_CHANGE_SUSPECTED are trusted (safety analysis
runs); a confirmed change is dated back to the last MATCH before the suspicion began (reliable_t), so nothing observed
while the view was in doubt counts as evidence. Vibration and focus loss are reported as quality warnings, never as a
relocation, and never end incidents.
"""
import math
from collections import deque
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

INITIALIZING, VIEW_STABLE, SUSPECTED, VIEW_CHANGED, BLOCKED, RECOVERING, VIEW_UNVERIFIED = (
    "INITIALIZING", "VIEW_STABLE", "VIEW_CHANGE_SUSPECTED", "VIEW_CHANGED", "BLOCKED", "RECOVERING", "VIEW_UNVERIFIED")
STATES = (INITIALIZING, VIEW_STABLE, SUSPECTED, VIEW_CHANGED, BLOCKED, RECOVERING, VIEW_UNVERIFIED)
TRUSTED = {VIEW_STABLE, SUSPECTED}
ALLOWED = {
    INITIALIZING: {VIEW_STABLE, VIEW_CHANGED, BLOCKED},
    VIEW_STABLE: {SUSPECTED},
    SUSPECTED: {VIEW_STABLE, VIEW_CHANGED, BLOCKED},
    VIEW_CHANGED: {RECOVERING, VIEW_UNVERIFIED, BLOCKED},
    BLOCKED: {RECOVERING, VIEW_CHANGED, INITIALIZING},
    RECOVERING: {VIEW_STABLE, VIEW_CHANGED, BLOCKED, VIEW_UNVERIFIED},
    VIEW_UNVERIFIED: {RECOVERING, VIEW_CHANGED, BLOCKED},
}

# Outcome of one check
MATCH, SHIFTED, NO_MATCH, UNOBSERVABLE = "match", "shifted", "no_match", "unobservable"

# Event types, which are also the closure reasons of the incidents they interrupt
CAMERA_VIEW_CHANGED, CAMERA_SCENE_SWITCHED, CAMERA_BLOCKED, CAMERA_VIEW_UNVERIFIED = (
    "camera_view_changed", "camera_scene_switched", "camera_blocked", "camera_view_unverified")
EVENT_TYPES = (CAMERA_VIEW_CHANGED, CAMERA_SCENE_SWITCHED, CAMERA_BLOCKED, CAMERA_VIEW_UNVERIFIED)

_PROBE = np.array([[0, 0], [1, 0], [0, 1], [1, 1], [0.5, 0.5]], np.float32)  # corners and centre, normalised


@dataclass
class ViewSettings:
    """Defaults were set on synthetic transformations of the demo clips and procedural scenes (tests/test_view_monitor.py),
    not on deployment footage; every one can be overridden per camera (view_monitor: in the runtime configuration)."""
    enabled: bool = True
    geometry: bool = True  # False: blockage only (a camera whose view is meant to move; it must have no zones)
    check_interval_s: float = 0.5  # video seconds between checks; a check costs about 2-4 ms
    width: int = 320  # analysis width in pixels (the height keeps the aspect ratio)
    init_s: float = 2.0  # stable observation needed to establish (or verify) a reference
    confirm_s: float = 5.0  # a view change must persist this long before incidents are interrupted
    blocked_confirm_s: float = 5.0  # likewise for blockage
    recover_s: float = 3.0  # the registered view must be seen continuously this long before monitoring resumes
    unverified_after_s: float = 10.0  # a different but steady view for this long becomes VIEW_UNVERIFIED (a candidate)
    max_shift: float = 0.02  # tolerated displacement of corners/centre, share of the image width (zone error)
    min_inliers: int = 20  # RANSAC inliers needed for a geometric match
    blank_std: float = 6.0  # grey-level standard deviation below which the image is uniform (covered, black, white)
    structure_ratio: float = 0.25  # features and relative sharpness both below this share of the reference: blocked
    # Before a reference exists there is nothing to compare with, so absolute floors decide whether a view may become
    # one: a covered lens with a light leak measured std 7.8 (and ~130 noise features: equalisation amplifies noise);
    # the demo scenes 40-68, the synthetic test scene 29. A very dark scene therefore cannot seed a reference.
    min_reference_std: float = 12.0
    min_features: int = 40
    focus_ratio: float = 0.5  # relative sharpness below this share of the reference while matching: focus warning
    jitter_shift: float = 0.008  # spread (std) of matched displacement above this: vibration warning
    snapshots: bool = True  # keep small grey evidence images of view events (analysis width, no colour)


@dataclass
class Fingerprint:
    """A view: a small grey image and its ORB features. The image is the only thing stored; features are derived."""
    gray: np.ndarray
    kp: np.ndarray = None  # (N, 2) float32 positions
    des: np.ndarray = None
    std: float = 0.0
    sharp: float = 0.0  # Laplacian variance relative to contrast (std^2): independent of brightness and gain
    n: int = 0

    def to_png(self) -> bytes:
        return cv2.imencode(".png", self.gray)[1].tobytes()

    @classmethod
    def from_png(cls, data: bytes) -> "Fingerprint":
        return fingerprint(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE))


_orb = None
_clahe = None


def _tools():
    global _orb, _clahe
    if _orb is None:
        # 300 features over 3 scales: 1.5 ms at 320 x 180 (500 over 5 scales: 2.3 ms, no better on the demo clips)
        _orb = cv2.ORB_create(nfeatures=300, scaleFactor=1.2, nlevels=3, edgeThreshold=15, patchSize=21, fastThreshold=10)
        _clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    return _orb, _clahe


def small_gray(frame, width) -> np.ndarray:
    h, w = frame.shape[:2]
    if w != width:
        frame = cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)
    return frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def fingerprint(gray) -> Fingerprint:
    orb, clahe = _tools()
    std = float(gray.std())
    sharp = float(cv2.Laplacian(gray, cv2.CV_32F).var()) / (std * std + 1.0)
    fp = Fingerprint(gray, np.zeros((0, 2), np.float32), None, std, sharp, 0)
    if std < 1.0:
        return fp
    kps, des = orb.detectAndCompute(clahe.apply(gray), None)  # equalised: features survive lighting changes
    if des is not None:
        fp.kp, fp.des, fp.n = np.float32([k.pt for k in kps]), des, len(kps)
    return fp


@dataclass
class Match:
    inliers: int
    shift: float | None = None  # largest displacement of corners/centre, share of width; None: no fit
    dx: float = 0.0  # camera pan, share of the width: + the camera turned right (the scene moved left in the image)
    dy: float = 0.0  # camera tilt, share of the height: + the camera tilted down (the scene moved up)
    angle: float = 0.0  # rotation of the scene in the image, degrees (OpenCV sign: + counter-clockwise)
    scale: float = 1.0  # zoom factor: > 1 zoomed in
    spread: float = 0.0  # share of the image area spanned by the inliers

    @property
    def fitted(self):
        return self.shift is not None


_matcher = cv2.BFMatcher(cv2.NORM_HAMMING)


def match(cur: Fingerprint, ref: Fingerprint, min_inliers=20) -> Match:
    """Fit a similarity transform from the current view to the reference."""
    if cur.des is None or ref.des is None or cur.n < 8 or ref.n < 8:
        return Match(0)
    pairs = _matcher.knnMatch(cur.des, ref.des, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.8 * p[1].distance]
    if len(good) < min(min_inliers, 8):
        return Match(len(good))
    src = cur.kp[[m.queryIdx for m in good]]
    dst = ref.kp[[m.trainIdx for m in good]]
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0, maxIters=500,
                                         confidence=0.99)
    n = int(inl.sum()) if inl is not None else 0
    if M is None or n < min_inliers:
        return Match(n)
    h, w = cur.gray.shape
    probe = _PROBE * [w, h]
    moved = probe @ M[:, :2].T + M[:, 2]
    d = np.hypot(*(moved - probe).T) / w
    pts = src[inl.ravel() == 1]
    spread = float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 1]) / (w * h)) if len(pts) else 0.0
    # M maps current -> reference: where the current image centre lies in the reference is where the camera now points
    a, b = float(M[0, 0]), float(M[1, 0])
    return Match(n, float(d.max()), float((moved[4, 0] - probe[4, 0]) / w), float((moved[4, 1] - probe[4, 1]) / h),
                 float(-math.degrees(math.atan2(b, a))), float(1.0 / max(math.hypot(a, b), 1e-6)), spread)


def movement(m: Match, max_shift) -> list[str]:
    """Plain-language components of a fitted camera movement (largest first)."""
    parts = [("pan", abs(m.dx)), ("tilt", abs(m.dy)), ("rotation", abs(math.radians(m.angle)) * 0.6),
             ("zoom", abs(m.scale - 1.0) * 0.6)]  # rotation and zoom as approximate corner displacement
    out = [k for k, v in sorted(parts, key=lambda p: -p[1]) if v >= max_shift * 0.5]
    return out or ["small shift"]


@dataclass
class Check:
    t: float
    outcome: str
    std: float
    sharp: float
    features: int
    ref: Match | None = None
    cont: Match | None = None  # continuity with the previous check
    note: str = ""

    def brief(self) -> dict:
        d = {"t": round(self.t, 3), "outcome": self.outcome, "std": round(self.std, 1), "sharpness": round(self.sharp, 3),
             "features": self.features}
        if self.ref is not None:
            d["reference"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in asdict(self.ref).items()}
        if self.cont is not None:
            d["continuity_inliers"] = self.cont.inliers
        if self.note:
            d["note"] = self.note
        return d


@dataclass
class Transition:
    previous: str
    state: str
    t: float
    cause: str
    kind: str | None = None  # an event type when monitoring stops being trusted (or None)
    reliable_t: float | None = None  # last check that matched the registered view
    suspected_t: float | None = None  # first check of the persistent change
    evidence: dict = field(default_factory=dict)


class ViewMonitor:
    """One camera. Not thread-safe: the camera's processing thread owns it."""

    def __init__(self, settings: ViewSettings | None = None, reference: Fingerprint | None = None):
        self.s = settings or ViewSettings()
        self.reference = reference
        self.state = INITIALIZING
        self.since = None  # video time the current state began
        self.last_check_t = self.first_t = None
        self.reliable_t = None  # last check that matched the reference (or, while bootstrapping, was observable)
        self.streak = []  # checks since the current suspicion / recovery / candidate began
        self.prev = None  # previous check's fingerprint (continuity)
        self.prev_check = None
        self.boot = []  # (t, gray) while establishing a reference
        self.candidate = None  # Fingerprint of a steady different view (VIEW_UNVERIFIED)
        self.recent = deque(maxlen=40)  # recent checks, for instability warnings and evidence
        self.last_reliable_gray = self.last_gray = None
        self.disturbances = 0  # suspicions that cleared (transient disturbances)
        self.trusted_since = None
        self.suspect_after_gap = False  # the current suspicion began at a stream discontinuity
        self.checks = 0
        self.warnings = []

    # ------------------------------------------------------------------ queries
    @property
    def trusted(self) -> bool:
        """A suspicion that began right after a stream gap (reconnect, loop restart) is not trusted: the camera may have
        come back on another view, so nothing is analysed until it matches again (or the change is confirmed)."""
        return self.state in TRUSTED and not (self.state == SUSPECTED and self.suspect_after_gap)

    @property
    def bootstrapping(self) -> bool:
        """No reference yet: the first view is assumed to be the one the zones were drawn on, as before view monitoring."""
        return self.state == INITIALIZING and self.reference is None

    @property
    def unsettled(self) -> bool:
        """Bootstrapping for more than 5 x init_s without a steady view (a moving camera): zones cannot be trusted."""
        return self.bootstrapping and self.last_check_t is not None and \
            self.last_check_t - self.first_t > 5 * max(self.s.init_s, 1.0)

    def due(self, t, discontinuity=False) -> bool:
        return self.last_check_t is None or discontinuity or t - self.last_check_t >= self.s.check_interval_s - 1e-6

    def snapshot(self) -> dict:
        last = self.prev_check
        return {"state": self.state, "trusted": self.trusted, "since_t": None if self.since is None else round(self.since, 3),
                "reliable_t": None if self.reliable_t is None else round(self.reliable_t, 3), "checks": self.checks,
                "transient_disturbances": self.disturbances, "warnings": list(self.warnings),
                "last_check": last.brief() if last else None}

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, frame, t, discontinuity=False) -> tuple[Check, Fingerprint]:
        gray = small_gray(frame, self.s.width)
        fp = fingerprint(gray)
        c = Check(t, MATCH, fp.std, fp.sharp, fp.n)
        ref = self.reference
        if fp.std < self.s.blank_std:
            c.outcome, c.note = UNOBSERVABLE, "uniform image (covered, dark or blank)"
            return c, fp
        if ref is not None and fp.n < self.s.structure_ratio * ref.n and fp.sharp < self.s.structure_ratio * ref.sharp:
            c.outcome, c.note = UNOBSERVABLE, "structure lost (covered, out of focus or obstructed)"
            return c, fp
        if ref is None and (fp.std < self.s.min_reference_std or fp.n < self.s.min_features):
            # nothing to compare with: absolute floors, so an obstructed image can never become the reference
            c.outcome, c.note = UNOBSERVABLE, "too little contrast or structure to establish a reference (covered?)"
            return c, fp
        if ref is not None and self.s.geometry:
            c.ref = match(fp, ref, self.s.min_inliers)
            if not c.ref.fitted:
                c.outcome = NO_MATCH
            elif c.ref.shift > self.s.max_shift:
                c.outcome = SHIFTED
        # continuity is only needed to type a change (cut or movement) and to see a new view settle: not while matching
        if self.prev is not None and not discontinuity and self.s.geometry and ref is not None and \
                (c.outcome != MATCH or not self.trusted):
            c.cont = match(fp, self.prev, self.s.min_inliers)
        return c, fp

    def observe(self, frame, t, discontinuity=False) -> list[Transition]:
        """Check one frame (call when due()). Returns the state transitions it caused, in order."""
        if not self.s.enabled:
            return []
        c, fp = self.evaluate(frame, t, discontinuity)
        if self.state == VIEW_STABLE:
            self.suspect_after_gap = discontinuity  # used if this check starts a suspicion
        self.checks += 1
        self.last_check_t, self.last_gray = t, fp.gray
        if self.first_t is None:
            self.first_t = t
        out = self._step(c, fp)
        self.recent.append(c)
        self._warn()
        if c.outcome != UNOBSERVABLE:
            self.prev = fp
        self.prev_check = c
        if self.since is None:
            self.since = t
        return out

    # ------------------------------------------------------------------ state machine
    def _go(self, state, t, cause, kind=None, evidence=None) -> Transition:
        assert state in ALLOWED[self.state], (self.state, state)
        tr = Transition(self.state, state, t, cause, kind, self.reliable_t,
                        self.streak[0].t if self.streak else t, evidence or {})
        if state in TRUSTED and self.state not in TRUSTED:
            self.trusted_since = t
        self.state, self.since = state, t
        self.streak = []  # evidence never carries over into a new state; callers start the new state's streak
        return tr

    def _evidence(self, checks) -> dict:
        refs = [c.ref for c in checks if c.ref is not None and c.ref.fitted]
        out = {"checks": len(checks), "outcomes": {o: sum(c.outcome == o for c in checks) for o in
                                                    (MATCH, SHIFTED, NO_MATCH, UNOBSERVABLE)},
               "span_s": round(checks[-1].t - checks[0].t, 3) if checks else 0.0,
               "median_inliers": int(np.median([c.ref.inliers for c in checks if c.ref is not None] or [0])),
               "first": checks[0].brief() if checks else None, "last": checks[-1].brief() if checks else None}
        if refs:
            m = refs[-1]
            out["transform"] = {"shift": round(m.shift, 4), "dx": round(m.dx, 4), "dy": round(m.dy, 4),
                                "angle_deg": round(m.angle, 2), "scale": round(m.scale, 4), "inliers": m.inliers,
                                "movement": movement(m, self.s.max_shift)}
        return out

    def _quality(self, checks) -> str:
        """Evidence quality of a confirmed event: how consistent the checks were and how strong the fit."""
        bad = [c for c in checks if c.outcome != MATCH]
        share = len(bad) / max(1, len(checks))
        if share >= 0.9 and len(checks) >= 5:
            return "high"
        return "medium" if share >= 0.7 else "low"

    def _step(self, c: Check, fp: Fingerprint) -> list[Transition]:
        s, st, t = self.s, self.state, c.t
        out = []
        if st == INITIALIZING:
            return self._initialize(c, fp)
        if st == VIEW_STABLE:
            if c.outcome == MATCH:
                self._reliable(c, fp)
            else:
                out.append(self._go(SUSPECTED, t, f"check outcome {c.outcome}"))
                self.streak = [c]
            return out
        if st == SUSPECTED:
            if c.outcome == MATCH:
                self.disturbances += 1
                self.streak = []
                self._reliable(c, fp)
                out.append(self._go(VIEW_STABLE, t, "transient disturbance cleared"))
                return out
            self.streak.append(c)
            return out + self._confirm(c)
        if st in (BLOCKED, VIEW_CHANGED, VIEW_UNVERIFIED):
            return self._untrusted(c, fp)
        if st == RECOVERING:
            if c.outcome == MATCH:
                self.streak.append(c)
                if t - self.streak[0].t >= s.recover_s:
                    self._reliable(c, fp)
                    ev = self._evidence(self.streak)
                    self.streak, self.candidate = [], None
                    out.append(self._go(VIEW_STABLE, t, "registered view seen again for the recovery window", evidence=ev))
                return out
            back = BLOCKED if c.outcome == UNOBSERVABLE else self.recover_from
            out.append(self._go(back, t, f"recovery interrupted ({c.outcome})"))
            self.streak = [c]
            return out
        return out

    def _reliable(self, c, fp):
        self.reliable_t = c.t
        self.last_reliable_gray = fp.gray

    def _initialize(self, c, fp) -> list[Transition]:
        s, t = self.s, c.t
        if c.outcome == UNOBSERVABLE:
            self.boot = []
            self.streak = [x for x in self.streak if x.outcome == UNOBSERVABLE] + [c]
            if t - self.streak[0].t >= s.blocked_confirm_s:
                ev = self._evidence(self.streak)
                return [self._go(BLOCKED, t, c.note or "unobservable", CAMERA_BLOCKED, ev)]
            return []
        if self.reference is not None:  # verify the stored reference before trusting anything
            if c.outcome == MATCH:
                self.streak = [x for x in self.streak if x.outcome == MATCH] + [c]
                if t - self.streak[0].t >= s.init_s:
                    self._reliable(c, fp)
                    ev = self._evidence(self.streak)
                    self.streak = []
                    return [self._go(VIEW_STABLE, t, "registered reference view verified", evidence=ev)]
                return []
            self.streak = [x for x in self.streak if x.outcome != MATCH] + [c]
            if t - self.streak[0].t >= s.confirm_s:
                ev = self._evidence(self.streak)
                return [self._go(VIEW_CHANGED, t, "the view at start does not match the registered reference",
                                 CAMERA_VIEW_UNVERIFIED, ev)]
            return []
        # bootstrap: the first steady, observable view becomes revision 1
        self.streak = []
        self.reliable_t = t
        if self.boot and s.geometry:
            m = match(fp, self.boot[0][2], s.min_inliers)
            if not m.fitted or m.shift > s.max_shift:
                self.boot = []  # still settling (moving, cutting): start again
        self.boot.append((t, fp.gray, fp))
        if t - self.boot[0][0] >= s.init_s and len(self.boot) >= 3:
            self.reference = fingerprint(np.median(np.stack([b[1] for b in self.boot]), axis=0).astype(np.uint8))
            self.boot = []
            self._reliable(c, fp)
            return [self._go(VIEW_STABLE, t, "reference established from the first steady view (temporal median)",
                             evidence={"reference_features": self.reference.n})]
        return []

    def _confirm(self, c) -> list[Transition]:
        s, t, k = self.s, c.t, self.streak
        unobs = sum(x.outcome == UNOBSERVABLE for x in k)
        span = t - k[0].t
        if unobs * 2 >= len(k):
            if span >= s.blocked_confirm_s:
                ev = self._evidence(k)
                ev["evidence_quality"] = self._quality(k)
                return [self._go(BLOCKED, t, k[-1].note or k[0].note or "unobservable", CAMERA_BLOCKED, ev)]
            return []
        if span < s.confirm_s:
            return []
        ev = self._evidence(k)
        ev["evidence_quality"] = self._quality(k)
        first = k[0]
        # A cut: the first bad check shares nothing with the check before it, and nothing since was a measurable shift.
        # (A whip pan faster than one check interval looks the same and is reported as a scene switch.)
        cut = first.outcome == NO_MATCH and first.cont is not None and not first.cont.fitted and \
            not any(x.outcome == SHIFTED for x in k)
        self.recover_from = VIEW_CHANGED
        if cut:
            return [self._go(VIEW_CHANGED, t, "abrupt scene transition (no continuity with the previous view)",
                             CAMERA_SCENE_SWITCHED, ev)]
        what = ", ".join(ev["transform"]["movement"]) if "transform" in ev else "registered view no longer recognised"
        return [self._go(VIEW_CHANGED, t, f"camera view changed ({what})", CAMERA_VIEW_CHANGED, ev)]

    recover_from = VIEW_CHANGED

    def _untrusted(self, c, fp) -> list[Transition]:
        s, st, t = self.s, self.state, c.t
        if c.outcome == MATCH and self.reference is not None:
            self.recover_from = st
            tr = self._go(RECOVERING, t, "registered view seen again")
            self.streak = [c]
            return [tr]
        if st == BLOCKED:
            if c.outcome == UNOBSERVABLE:
                self.streak = []
                return []
            if self.reference is None:  # blocked while bootstrapping: start again, this check being the first
                return [self._go(INITIALIZING, t, "observable again; establishing a reference")] + self._initialize(c, fp)
            if not s.geometry:
                self.recover_from = BLOCKED
                tr = self._go(RECOVERING, t, "observable again")
                self.streak = [c]
                return [tr]
            self.streak = [x for x in self.streak if x.outcome != UNOBSERVABLE] + [c]
            if t - self.streak[0].t >= s.confirm_s:
                ev = self._evidence(self.streak)
                ev["evidence_quality"] = self._quality(self.streak)
                self.streak = []
                return [self._go(VIEW_CHANGED, t, "observable again, but not the registered view", CAMERA_VIEW_CHANGED, ev)]
            return []
        if c.outcome == UNOBSERVABLE:
            self.streak = [x for x in self.streak if x.outcome == UNOBSERVABLE] + [c]
            if t - self.streak[0].t >= s.blocked_confirm_s:
                ev = self._evidence(self.streak)
                self.streak = []
                self.candidate = None
                return [self._go(BLOCKED, t, c.note, CAMERA_BLOCKED, ev)]
            return []
        steady = c.cont is not None and c.cont.fitted and c.cont.shift <= s.max_shift
        if st == VIEW_CHANGED:
            if not steady:
                self.streak = [c]
                return []
            self.streak = [x for x in self.streak if x.outcome != UNOBSERVABLE] + [c]
            if t - self.streak[0].t >= s.unverified_after_s:
                self.candidate = fp
                ev = self._evidence(self.streak)
                self.streak = []
                return [self._go(VIEW_UNVERIFIED, t, "steady view that is not the registered reference: needs an operator "
                                 "to revalidate (accept it as a new reference revision) or restore the camera", evidence=ev)]
            return []
        # VIEW_UNVERIFIED: a further change makes it VIEW_CHANGED again
        if self.candidate is not None:
            m = match(fp, self.candidate, s.min_inliers)
            if not m.fitted or m.shift > s.max_shift:
                self.candidate = None
                return [self._go(VIEW_CHANGED, t, "the unverified view changed again")]
        return []

    def accept(self, ref: Fingerprint, t) -> Transition:
        """An operator accepted a new reference (or confirmed the current one): the only way the reference changes."""
        prev = self.state
        self.reference, self.candidate, self.streak, self.boot = ref, None, [], []
        self.reliable_t = self.trusted_since = t
        self.state, self.since = VIEW_STABLE, t
        return Transition(prev, VIEW_STABLE, t, "operator accepted a reference view")

    def current(self) -> Fingerprint | None:
        """The view now (for an operator to accept): the candidate if there is one, else the last observable check."""
        return self.candidate or self.prev

    # ------------------------------------------------------------------ quality warnings
    def _warn(self):
        """Quality warnings over the checks since the view last became trusted (an earlier change is not vibration)."""
        w = []
        if self.unsettled:
            w.append("no steady view yet: no reference can be established (moving camera?); zones are not used")
        if self.state not in TRUSTED:
            self.warnings = w
            return
        since = self.trusted_since if self.trusted_since is not None else -math.inf
        ok = [c for c in list(self.recent)[-20:] if c.t >= since and c.outcome in (MATCH, SHIFTED) and c.ref is not None
              and c.ref.fitted]
        if len(ok) >= 8 and float(np.std([c.ref.shift for c in ok])) > self.s.jitter_shift:
            w.append("vibration: the view is shaking")
        last = [c for c in list(self.recent)[-20:] if c.t >= since]
        flips = sum(1 for a, b in zip(last, last[1:]) if (a.outcome == MATCH) != (b.outcome == MATCH))
        if flips >= 6:
            w.append("unstable view: repeated changes")
        ref = self.reference
        m = [c for c in last[-10:] if c.outcome == MATCH]
        if ref is not None and len(m) >= 6 and all(c.sharp < self.s.focus_ratio * ref.sharp for c in m):
            w.append("focus degraded")
        self.warnings = w
