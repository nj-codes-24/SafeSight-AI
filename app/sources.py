"""Video sources for the gallery: the demo clips, uploaded videos and the webcam.

Thumbnails are real frames taken from each clip with OpenCV, written once to data/cache/thumbnails and reused.
Nothing here loads the model or starts monitoring.
"""
import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
UPLOADS = DEMO / "uploads"
CACHE = ROOT / "data" / "cache" / "thumbnails"
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Factual one-line descriptions of the bundled demo clips (what is in the footage, not what the model finds).
DESCRIPTIONS = {
    "track_work_day": "Daytime track maintenance at a railway platform. A small crew in hi-vis and hard hats works on the rails "
                      "close to the camera.",
    "roadworks_night": "Night roadworks under floodlights. A jackhammer crew works in an excavation while people walk past "
                       "in the background.",
    "ballast_train": "A hand-held camera moves alongside a ballast train while workers in hi-vis walk the track bed.",
    "helmet_put_on": "Close-up of a worker who starts without head protection and then puts on a hard hat.",
    "framing_bare_head": "Two workers behind timber framing on a building site, without hard hats.",
}


@dataclass
class Source:
    key: str
    kind: str  # "demo" | "upload" | "webcam"
    title: str
    path: Path | None = None
    meta: dict = field(default_factory=dict)

    @property
    def stem(self):
        return self.path.stem if self.path else "WEBCAM"

    @property
    def name(self):
        return self.path.name if self.path else "Webcam"

    @property
    def capture(self):
        return str(self.path) if self.path else 0


def demo_sources():
    out = []
    manifest = DEMO / "demo_clips.json"
    if manifest.exists():
        for c in json.loads(manifest.read_text(encoding="utf-8")):
            p = DEMO / c["file"]
            if p.exists():
                artist = re.sub(r"<[^>]+>", "", c.get("artist", "")).strip()
                out.append(Source(f"demo:{c['file']}", "demo", c["title"], p,
                                  {"license": c.get("license", ""), "artist": artist, "source_page": c.get("source_page", "")}))
    return out


def upload_sources():
    if not UPLOADS.exists():
        return []
    files = sorted((p for p in UPLOADS.iterdir() if p.suffix.lower() in VIDEO_EXT), key=lambda p: p.stat().st_mtime, reverse=True)
    return [Source(f"upload:{p.name}", "upload", p.stem.replace("_", " ").replace("-", " "), p) for p in files]


WEBCAM = Source("webcam:0", "webcam", "Webcam", None, {"device": 0})


def all_sources():
    return demo_sources() + upload_sources() + [WEBCAM]


def find(key):
    return next((s for s in all_sources() if s.key == key), None)


@st.cache_data(show_spinner=False)
def video_info(path: str, mtime: float):
    cap = cv2.VideoCapture(path)
    info = {"frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0), "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)}
    cap.release()
    info["duration"] = info["frames"] / info["fps"] if info["fps"] else 0
    return info


def info(src):
    return video_info(str(src.path), src.path.stat().st_mtime) if src.path else {}


def thumbnail_path(path: Path, width=960):
    """First suitable frame: skip the first few frames and any that are near-black or flat. Cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"{path.stem}_{int(path.stat().st_mtime)}_{width}.jpg"
    if out.exists():
        return out
    cap = cv2.VideoCapture(str(path))
    best, chosen = None, None
    for i in range(90):
        ok, f = cap.read()
        if not ok:
            break
        if i < 8 or i % 4:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if best is None:
            best = f
        if g.mean() > 45 and g.std() > 30:
            chosen = f
            break
    cap.release()
    frame = chosen if chosen is not None else best
    if frame is None:
        return None
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return out


@st.cache_data(show_spinner=False)
def _data_uri(path: str, mtime: float):
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def data_uri(path: Path | None):
    return _data_uri(str(path), path.stat().st_mtime) if path and path.exists() else None


def thumb_uri(src, width=960):
    return data_uri(thumbnail_path(src.path, width)) if src.path else None


@st.cache_data(show_spinner=False, max_entries=512)
def _evidence_thumb(path: str, mtime: float):
    im = cv2.imread(path)
    if im is None:
        return None
    h, w = im.shape[:2]
    im = cv2.resize(im, (320, int(h * 320 / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else None


def evidence_thumb(path):
    p = Path(path) if path else None
    return _evidence_thumb(str(p), p.stat().st_mtime) if p and p.exists() else None


def last_sessions(sessions, rows):
    """source file name -> (last session dict, incident count) from the real database."""
    out = {}
    counts = {}
    for r in rows:
        counts[r["session_id"]] = counts.get(r["session_id"], 0) + 1
    for s in sessions:  # oldest first, so the last write wins
        out[s["source"]] = (s, counts.get(s["session_id"], 0))
    return out
