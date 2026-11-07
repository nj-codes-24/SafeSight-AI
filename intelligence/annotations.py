"""Evaluation labels (docs/product_research/17_ANNOTATION_PROTOCOL.md): validate, lock, and convert to scoring inputs.

A label file describes one clip: intervals per hazard (monitorable, uncertain, unobservable, unusable, not_applicable)
and events (violation, uncertain, not_applicable). `scoring_inputs` turns them into what event_metrics needs, applying
the pre-registered rules: primary vs optional episodes, ignore regions, context regions and monitorable seconds.
"""
import hashlib
import json
from datetime import date
from pathlib import Path

from intelligence.taxonomy import HAZARDS

SCHEMA = "safesight.labels/1.0"
SCHEMA_1_1 = "safesight.labels/1.1"  # adds optional identity anchors on events: [{t, x, y}] normalised (protocol §12 A3)
SCHEMAS = (SCHEMA, SCHEMA_1_1)
INTERVAL_STATES = {"monitorable", "uncertain", "unobservable", "unusable", "not_applicable"}
EVENT_KINDS = {"violation", "uncertain", "not_applicable"}
OBSERVABILITY = {"clear", "partial", "low"}
REQUIREMENT = {"evident", "assumed", None}
CONFIDENCE = {"high", "medium", "low", None}  # the annotator's own confidence in an event (optional; protocol §12 A6)
STATUSES = ["provisional", "reviewed", "adjudicated", "verified"]
MIN_EPISODE_S = 1.0  # shorter violations are optional: the pipeline needs ~0.5 s of agreeing evidence by design
MERGE_GAP_S = 30.0  # same worker, same hazard, gap below the incident cooldown: one episode


def validate(lab: dict) -> dict:
    def need(cond, msg):
        if not cond:
            raise ValueError(f"{lab.get('clip_id', '?')}: {msg}")

    need(lab.get("schema") in SCHEMAS, f"schema must be {SCHEMA}")
    for k in ("label_set", "clip_id", "file", "sha256", "fps", "duration_s", "status", "annotators", "intervals", "events"):
        need(k in lab, f"missing {k}")
    need(lab["status"] in STATUSES, f"status must be one of {STATUSES}")
    dur = lab["duration_s"]
    for i, iv in enumerate(lab["intervals"]):
        need(iv["hazard"] in HAZARDS, f"interval {i}: unknown hazard {iv['hazard']}")
        need(iv["state"] in INTERVAL_STATES, f"interval {i}: state must be one of {sorted(INTERVAL_STATES)}")
        need(0 <= iv["start_s"] < iv["end_s"] <= dur + 0.05, f"interval {i}: times outside the clip or reversed")
    by_h = {}
    for iv in lab["intervals"]:
        by_h.setdefault(iv["hazard"], []).append(iv)
    for h, ivs in by_h.items():
        ivs = sorted(ivs, key=lambda x: x["start_s"])
        for a, b in zip(ivs, ivs[1:]):
            need(a["end_s"] <= b["start_s"] + 1e-6, f"{h}: intervals overlap at {b['start_s']} s")
    ids = set()
    for e in lab["events"]:
        need(e["id"] not in ids, f"duplicate event id {e['id']}")
        ids.add(e["id"])
        need(e["hazard"] in HAZARDS, f"{e['id']}: unknown hazard")
        need(e["kind"] in EVENT_KINDS, f"{e['id']}: kind must be one of {sorted(EVENT_KINDS)}")
        need(0 <= e["start_s"] <= e["end_s"] <= dur + 0.05, f"{e['id']}: times outside the clip or reversed")
        need(e.get("observability", "clear") in OBSERVABILITY, f"{e['id']}: bad observability")
        need(e.get("requirement") in REQUIREMENT, f"{e['id']}: bad requirement")
        need(e.get("start_unc_s", 0) >= 0 and e.get("end_unc_s", 0) >= 0, f"{e['id']}: negative uncertainty")
        need(e.get("confidence") in CONFIDENCE, f"{e['id']}: confidence must be one of {sorted(c for c in CONFIDENCE if c)}")
        if e["kind"] == "violation" and e["hazard"].startswith("PPE."):
            need(e.get("requirement") in ("evident", "assumed"), f"{e['id']}: a PPE violation needs a requirement basis")
        for a in e.get("anchors") or []:
            need(lab["schema"] == SCHEMA_1_1, f"{e['id']}: anchors need schema {SCHEMA_1_1}")
            need(set(a) <= {"t", "x", "y", "note"} and 0 <= a.get("x", -1) <= 1 and 0 <= a.get("y", -1) <= 1,
                 f"{e['id']}: an anchor is {{t, x, y}} with x and y normalised to 0-1")
            need(e["start_s"] - 2 <= a["t"] <= e["end_s"] + 2, f"{e['id']}: anchor time outside the event")
    return lab


def load_set(folder) -> dict:
    """clip_id -> validated labels, for every *.json in the folder."""
    out = {}
    for p in sorted(Path(folder).glob("*.json")):
        lab = validate(json.loads(p.read_text(encoding="utf-8")))
        out[lab["clip_id"]] = lab
    return out


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def lock_path(folder) -> Path:
    """<folder>.lock.json next to the folder. Not with_suffix: a version such as 'set-v1.1' would lose its '.1' and
    overwrite the lock of 'set-v1'."""
    folder = Path(folder)
    return folder.parent / f"{folder.name}.lock.json"


def lock(folder, note="") -> dict:
    """Hash every label file; write <folder>.lock.json next to the folder. Labels must validate first."""
    folder = Path(folder)
    labels = load_set(folder)
    files = {p.name: _sha(p) for p in sorted(folder.glob("*.json"))}
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in files.items()).encode()).hexdigest().upper()
    statuses = sorted({lab["status"] for lab in labels.values()})
    manifest = {"label_set": folder.name, "locked_on": date.today().isoformat(), "files": files, "combined_sha256": combined,
                "statuses": statuses, "ground_truth": statuses == ["verified"], "note": note}
    lock_path(folder).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def verify_lock(folder) -> dict:
    folder = Path(folder)
    manifest = json.loads(lock_path(folder).read_text(encoding="utf-8"))
    if manifest["label_set"] != folder.name:
        raise ValueError(f"{lock_path(folder).name} locks {manifest['label_set']}, not {folder.name}")
    now = {p.name: _sha(p) for p in sorted(folder.glob("*.json"))}
    if now != manifest["files"]:
        changed = sorted(set(now.items()) ^ set(manifest["files"].items()))
        raise ValueError(f"labels changed since they were locked: {[c[0] for c in changed]}")
    return manifest


def _merge(events):
    """Merge same-worker episodes of the same kind separated by less than the cooldown (one alert covers both). An
    uncertain stretch next to a violation stays separate: it is not part of the violation."""
    out = []
    for e in sorted(events, key=lambda x: (x.get("worker") or "", x.get("zone") or "", x["kind"], x["start_s"])):
        prev = out[-1] if out else None
        if prev and prev.get("worker") and prev.get("worker") == e.get("worker") and prev.get("zone") == e.get("zone") \
                and prev["kind"] == e["kind"] and e["start_s"] - prev["end_s"] < MERGE_GAP_S:
            prev["end_s"] = max(prev["end_s"], e["end_s"])
            prev["end_unc_s"] = max(prev.get("end_unc_s", 0), e.get("end_unc_s", 0))
            prev["merged"] = prev.get("merged", [prev["id"]]) + [e["id"]]
            prev["anchors"] = (prev.get("anchors") or []) + (e.get("anchors") or [])
        else:
            out.append(dict(e))
    return out


def scoring_inputs(lab: dict, hazard: str, include_assumed=True) -> dict:
    """Episodes (with optional and context flags), ignore regions, context regions and monitorable seconds."""
    episodes = []
    for e in _merge([e for e in lab["events"] if e["hazard"] == hazard]):
        dur = e["end_s"] - e["start_s"]
        primary = (e["kind"] == "violation" and e.get("observability", "clear") in ("clear", "partial") and dur >= MIN_EPISODE_S
                   and (include_assumed or e.get("requirement") != "assumed"))
        episodes.append({"id": e["id"], "hazard": hazard, "zone": e.get("zone"), "start_s": e["start_s"], "end_s": e["end_s"],
                         "start_unc_s": e.get("start_unc_s", 0.0), "end_unc_s": e.get("end_unc_s", 0.0),
                         "optional": not primary and e["kind"] != "not_applicable", "context": e["kind"] == "not_applicable",
                         "kind": e["kind"], "observability": e.get("observability"), "requirement": e.get("requirement"),
                         "worker": e.get("worker"), "anchors": e.get("anchors") or []})
    ivs = [iv for iv in lab["intervals"] if iv["hazard"] == hazard]
    ignore = [(iv["start_s"], iv["end_s"]) for iv in ivs if iv["state"] in ("uncertain", "unobservable", "unusable")]
    context = [(iv["start_s"], iv["end_s"]) for iv in ivs if iv["state"] == "not_applicable"]
    covered = sorted((iv["start_s"], iv["end_s"]) for iv in ivs)
    gaps, t = [], 0.0
    for a, b in covered:  # time without any interval is not evaluated: treat like unobservable
        if a > t + 1e-6:
            gaps.append((t, a))
        t = max(t, b)
    if t < lab["duration_s"] - 1e-6:
        gaps.append((t, lab["duration_s"]))
    return {"episodes": episodes, "ignore": ignore + gaps, "context": context,
            "monitorable_s": sum(iv["end_s"] - iv["start_s"] for iv in ivs if iv["state"] == "monitorable"),
            "context_s": sum(b - a for a, b in context)}
