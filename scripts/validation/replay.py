"""Deterministic replay of the post-detector logic on recorded model traces (scripts/validation/record_traces.py).

The detector and tracker outputs are fixed by the trace, so two versions of the incident logic can be compared on
exactly the same inputs, on a CPU, in seconds. `legacy` is the frozen M2 logic (scripts/validation/legacy_m2/);
`current` is the product code in inference/.

    python scripts/validation/replay.py c01 --logic legacy --why          close reasons for every incident
    python scripts/validation/replay.py c01 --logic legacy --watch 7      per-frame states of one track
"""
import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TRACES = ROOT / "reports" / "validation" / "traces"


def load_trace(clip_id):
    with gzip.open(TRACES / f"{clip_id}.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


class TraceDetector:
    """Stands in for inference.detector.Detector: returns the recorded tracks and applies the frozen head thresholds
    exactly as Detector.track does. reset() cannot restart a recorded tracker, so a replayed reset is not supported."""

    def __init__(self, trace, detection_cls):
        self.frames, self.i, self.Detection = trace["frames"], 0, detection_cls

    def reset(self):
        pass

    def track(self, frame, person_conf=0.35, ppe_conf=0.3, no_helmet_conf=None):
        persons, heads = self.frames[self.i]
        self.i += 1
        thr = {"no_helmet": no_helmet_conf or ppe_conf, "helmet": ppe_conf}
        return ([(p[0], np.array(p[1:5], float), p[5]) for p in persons],
                [self.Detection(np.array(h[:4], float), h[4], h[5]) for h in heads if h[4] >= thr.get(h[5], 1.1)])


def pipeline_module(logic):
    if logic == "legacy":
        from scripts.validation.legacy_m2 import ppe_association, tracker
    else:
        from inference import ppe_association, tracker
    return tracker, ppe_association


def replay(clip_id, logic="current", cfg=None, zones=None, ppe_policy=None, watch=None, why=False):
    """Returns (incidents, extras). incidents: one dict per incident with open and close video times and, with
    why=True and the legacy logic, the reason it closed. extras: per-frame states of the watched track."""
    from database.database import IncidentDB
    from intelligence.risk import load_policy

    trace = load_trace(clip_id)
    tracker, ppe = pipeline_module(logic)
    if zones is None:
        zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"].get(clip_id, [])
    events, frames_log = {}, []

    def listener(event, iid, kind, track_id, zone, video_t, **info):
        e = events.setdefault(iid, {"incident_id": iid, "type": kind, "worker_id": track_id, "zone": zone})
        e["t" if event == "opened" else "t_end"] = round(video_t, 3)
        if event != "opened":
            e.update({k: v for k, v in info.items() if v is not None})

    tmp = Path(tempfile.mkdtemp(prefix="ssreplay_"))
    db = IncidentDB(tmp / "r.db")
    kw = dict(zones=zones, db=db, policy=load_policy(), evidence_dir=tmp / "ev", listener=listener, annotate=False)
    if logic != "legacy" and ppe_policy is not None:
        kw["ppe_policy"] = ppe_policy
    p = tracker.Pipeline(TraceDetector(trace, ppe.Detection), trace["fps"], cfg, clip_id, **kw)
    reason = {"now": "state change (compliant vote or zone exit)"}
    if why and logic == "legacy":
        close, expire = p.incidents.close, p._expire

        def tagged_close(kind, track_id, video_t, zone=None):
            key = (kind, track_id, zone)
            if key in p.incidents.open:
                events.setdefault(p.incidents.open[key], {})["why"] = reason["now"]
            return close(kind, track_id, video_t, zone)

        def tagged_expire(fi, t):
            reason["now"] = "track lost (lost_track_seconds)"
            try:
                expire(fi, t)
            finally:
                reason["now"] = "state change (compliant vote or zone exit)"

        p.incidents.close, p._expire = tagged_close, tagged_expire
    frame = np.zeros((trace["height"], trace["width"], 3), np.uint8)
    for fi in range(len(trace["frames"])):
        p.process(frame)
        if watch is not None:
            st = p.helmets.state(watch) if watch in p.last_seen else None
            frames_log.append((round(fi / p.fps, 2), watch in p.stats.tracked, st[0] if st else None,
                               [k for k in p.incidents.open if k[1] == watch]))
    if why and logic == "legacy":
        reason["now"] = "end of stream"
    p.finish(clip_id)
    rows = {r["incident_id"]: r for r in db.rows()}
    life = {r["incident_id"]: r for r in db.lifecycle()}
    out = []
    for iid, e in events.items():
        if iid in rows:
            lr = life.get(iid, {})
            out.append({**e, "confidence": rows[iid]["confidence"],
                        **{k: lr.get(k) for k in ("group_id", "end_reason", "classification", "observed_s", "unobserved_s",
                                                  "exposure_s", "tracks", "relation") if lr}})
    if logic != "legacy":
        frames_log = {"groups": db.groups(), "notifications": db.notifications(), "events": db.events(),
                      "ppe": {r["category"]: r["worker_seconds"] for r in db.ppe_observations()}, "watch": frames_log,
                      "boxes": track_boxes(trace)}
    db.close()
    return sorted(out, key=lambda x: x["t"]), frames_log


def track_boxes(trace):
    """track id -> {frame index: box}: lets the scorer check which worker an alert was about (identity-aware matching)."""
    out = {}
    for fi, (persons, _) in enumerate(trace["frames"]):
        for p in persons:
            out.setdefault(p[0], {})[fi] = p[1:5]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--logic", default="current", choices=["legacy", "current"])
    ap.add_argument("--why", action="store_true")
    ap.add_argument("--watch", type=int)
    a = ap.parse_args()
    inc, log = replay(a.clip, a.logic, watch=a.watch, why=a.why)
    for e in inc:
        print(json.dumps(e))
    for row in log:
        print(row)


if __name__ == "__main__":
    main()
