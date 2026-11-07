"""M2 evaluation of the frozen model through the headless runtime, scored against a locked label set.

    python scripts/validation/run_evaluation.py run   [--labels m2-provisional-v1]   frozen manifest + runtime pass -> eval.db
    python scripts/validation/run_evaluation.py score [--labels m2-provisional-v1]   labels + eval.db -> reports/validation/*

`run` refuses to start if the labels differ from their lock. It runs every evaluated clip through the same runtime that
would run on site (offline file mode: every frame, batched inference) into a separate database under
reports/validation/eval_runs/. `score` never runs the model: it reads that database, the labels and
reports/validation/error_causes.json (causes assigned after inspecting each error) and writes the reports.
"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_OFFLINE", "true")
from intelligence.annotations import MERGE_GAP_S, MIN_EPISODE_S, load_set, scoring_inputs, verify_lock  # noqa: E402
from intelligence.event_metrics import evaluate, summarise  # noqa: E402

VAL = ROOT / "reports" / "validation"
RUNS = VAL / "eval_runs"
TOLERANCE_S, LATE_S, BOOT_N = 2.0, 3.0, 4000
TYPE_TO_HAZARD = {"NO_HELMET": "PPE.HEAD.MISSING", "ZONE_INTRUSION": "ZONE.ENTRY"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except OSError:
        return None


def frozen_manifest(label_set, lock, labels, run_dir):
    from runtime import config as rconfig

    cfg_path = ROOT / "models" / "runtime_config.json"
    saved = json.loads(cfg_path.read_text())
    model = ROOT / "models" / "best.pt"
    code = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for d in ("inference", "intelligence", "runtime", "database")
            for p in sorted((ROOT / d).glob("*.py"))}
    from intelligence.risk import load_policy

    pol = load_policy()
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "M2 baseline: frozen M5 through the headless runtime, scored against a locked label set",
        "git": {"head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
                "working_tree": "uncommitted changes present (see code_sha256)" if git("status", "--porcelain") else "clean"},
        "model": {"file": "models/best.pt", "sha256": sha(model), "frozen_record": "models/model_config.yaml",
                  "licence": "research only: trained partly on SH17 (CC BY-NC-SA 4.0); Ultralytics AGPL-3.0"},
        "detector": {"imgsz": 640, "floor_confidence": 0.10, "classes": ["person", "helmet", "no_helmet"]},
        "thresholds": {k: saved.get(k, v) for k, v in rconfig.PIPELINE_DEFAULTS.items() if k != "zones"},
        "tracker": {"file": "inference/bytetrack_safesight.yaml", "sha256": sha(ROOT / "inference" / "bytetrack_safesight.yaml")},
        "runtime_config": {"file": "models/runtime_config.json", "sha256": sha(cfg_path), "zones": saved.get("zones", {})},
        "risk_policy": {"version": pol["version"], "status": pol["status"]},
        "runtime": {"backend": "batched", "source_mode": "file, realtime false (every frame, media time)", "max_fps": None,
                    "annotate": "evidence frames only", "database": str((run_dir / "eval.db").relative_to(ROOT))},
        "incident_logic": {"confirmation": "multi-frame vote (HelmetStateTracker) / debounced foot point (ZoneMonitor)",
                           "cooldown_s": saved.get("cooldown_seconds", 30.0), "lost_track_dedup": "one box height"},
        "scoring": {"tolerance_s": TOLERANCE_S, "late_after_s": LATE_S, "min_episode_s": MIN_EPISODE_S,
                    "merge_gap_s": MERGE_GAP_S, "bootstrap": {"unit": "source_group", "n": BOOT_N, "seed": 0},
                    "rules": "docs/product_research/17_ANNOTATION_PROTOCOL.md section 10"},
        "labels": {"set": label_set, "combined_sha256": lock["combined_sha256"], "statuses": lock["statuses"],
                   "ground_truth": lock["ground_truth"]},
        "clips": [{"clip_id": c, "file": lab["file"], "sha256": lab["sha256"], "split": lab["split"],
                   "source_group": lab["source_group"]} for c, lab in labels.items()],
        "code_sha256": code,
    }


def run(label_set):
    from runtime import config as rconfig
    from runtime.service import Runtime

    folder = VAL / "annotations" / label_set
    lock = verify_lock(folder)
    labels = load_set(folder)
    for lab in labels.values():
        if sha(ROOT / lab["file"]) != lab["sha256"]:
            raise SystemExit(f"{lab['clip_id']}: video file differs from its labelled hash")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{label_set}_{stamp}"
    run_dir.mkdir(parents=True)
    man = frozen_manifest(label_set, lock, labels, run_dir)
    app_zones = man["runtime_config"]["zones"]
    cams = [{"id": c, "site": lab["source_group"], "source": {"type": "file", "path": lab["file"], "realtime": False},
             "processing": {"max_fps": None, "queue_size": 4, "annotate": False},
             **({"zones_from_app": c} if c in app_zones else {})} for c, lab in labels.items()]
    cfg = rconfig.parse({"runtime": {"database": str(run_dir / "eval.db"), "evidence_dir": str(run_dir / "evidence"),
                                     "status_file": str(run_dir / "status.json"), "log_file": str(run_dir / "runtime.log")},
                         "inference": {"backend": "batched"}, "cameras": cams}, app_zones)
    from runtime import logs

    logs.setup(cfg.log_file, "INFO")
    t0 = datetime.now(timezone.utc)
    rt = Runtime(cfg)
    rt.start()
    rt.wait(exit_when_done=True)
    stuck = rt.stop()
    man["run"] = {"started_utc": t0.isoformat(timespec="seconds"),
                  "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stuck_cameras": stuck,
                  "inference": rt.backend.stats(),
                  "per_clip": {cid: {"session_id": w.session_id, "end_reason": w.end_reason, **(w.summary or {}),
                                     "frames": w.health.snapshot()["frames"], "state": w.health.snapshot()["state"]}
                               for cid, w in rt.workers.items()}}
    (run_dir / "evaluation_manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    if not (VAL / "evaluation_manifest.json").exists():  # the first (M2 baseline) manifest is a historical record: kept
        (VAL / "evaluation_manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    (RUNS / "LATEST").write_text(run_dir.name, encoding="utf-8")
    print(f"run complete: {run_dir}")


def predictions(db_path):
    import sqlite3

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    q = ("SELECT i.incident_id, i.incident_type, i.camera_id, i.worker_id, i.zone, i.video_time_s, i.evidence_path, i.confidence,"
         " c.opened_t, c.closed_t, a.hazard_code, a.risk_level, a.exposure_s FROM incidents i"
         " LEFT JOIN incident_context c USING (incident_id) LEFT JOIN risk_assessments a USING (incident_id)")
    life = {}
    if con.execute("SELECT name FROM sqlite_master WHERE name='incident_lifecycle'").fetchone():  # runs made after M2.1
        for r in con.execute("SELECT * FROM incident_lifecycle"):
            life[r["incident_id"]] = dict(r)
    out = {}
    for r in con.execute(q):
        h = r["hazard_code"] or TYPE_TO_HAZARD[r["incident_type"]]
        h = TYPE_TO_HAZARD.get(r["incident_type"], h) if h not in TYPE_TO_HAZARD.values() else h
        lr = life.get(r["incident_id"], {})
        path = json.loads(lr["path"]) if lr.get("path") else []
        out.setdefault(r["camera_id"], []).append({
            "type": TYPE_TO_HAZARD[r["incident_type"]], "hazard": h, "t": r["opened_t"] if r["opened_t"] is not None else r["video_time_s"],
            "t_end": r["closed_t"], "zone": r["zone"], "worker_id": r["worker_id"], "incident_id": r["incident_id"],
            "risk": r["risk_level"], "confidence": r["confidence"], "evidence": r["evidence_path"],
            "classification": lr.get("classification"), "end_reason": lr.get("end_reason"), "group_id": lr.get("group_id"),
            "boxes": {p[0]: p[1:] for p in path}})
    con.close()
    return out


def state_at(lab, hazard, t):
    for iv in lab["intervals"]:
        if iv["hazard"] == hazard and iv["start_s"] - 1e-6 <= t <= iv["end_s"] + 1e-6:
            return iv["state"]
    return "not labelled"


def score(label_set, run_name=None, out_dir=VAL, identity=False, overwrite=False):
    """Scores one run against one locked label set. A run made with another label set may be rescored (labels do not
    change what the model does) only if every labelled video is byte-identical to the one that run processed.
    identity=True uses identity-aware matching (labels with anchors; runs that store worker paths). Existing result
    files are never replaced unless overwrite=True: historical results stay as they were reported."""
    if (out_dir / "baseline_metrics.json").exists() and not overwrite:
        raise SystemExit(f"{out_dir} already holds results; choose a new --out (or pass --overwrite deliberately)")
    folder = VAL / "annotations" / label_set
    lock = verify_lock(folder)
    labels = load_set(folder)
    run_dir = RUNS / (run_name or (RUNS / "LATEST").read_text(encoding="utf-8").strip())
    man = json.loads((run_dir / "evaluation_manifest.json").read_text(encoding="utf-8"))
    if man["labels"]["combined_sha256"] != lock["combined_sha256"]:
        ran = {c["clip_id"]: c["sha256"] for c in man["clips"]}
        if any(ran.get(cid) != lab["sha256"] for cid, lab in labels.items()):
            raise SystemExit("the run was made on different videos from these labels")
        print(f"note: rescoring run {run_dir.name} (made with {man['labels']['set']}) against {label_set}")
    out_dir.mkdir(parents=True, exist_ok=True)
    preds = predictions(run_dir / "eval.db")
    causes = json.loads((VAL / "error_causes.json").read_text(encoding="utf-8")) if (VAL / "error_causes.json").exists() else {}
    hazards = ["PPE.HEAD.MISSING", "ZONE.ENTRY"]
    per_clip, fa_rows, miss_rows, lat_rows, outcomes = [], [], [], [], []
    totals = {}
    for cid, lab in labels.items():
        for h in hazards:
            if lab["scope"].get(h) != "evaluated":
                continue
            for variant, include_assumed in (("all", True), ("evident_only", False)):
                if variant == "evident_only" and not h.startswith("PPE."):
                    continue
                si = scoring_inputs(lab, h, include_assumed)
                p = [x for x in preds.get(cid, []) if x["type"] == h]
                r = evaluate(si["episodes"], p, lab["duration_s"], TOLERANCE_S, si["ignore"], si["context"], si["monitorable_s"],
                             si["context_s"], LATE_S, identity=identity)
                row = {"clip_id": cid, "split": lab["split"], "source_group": lab["source_group"], "hazard": h, "variant": variant,
                       "camera_id": lab.get("camera_id") or cid, "site_id": lab.get("site_id") or lab["source_group"],
                       "monitorable_s": round(si["monitorable_s"], 1), "context_s": round(si["context_s"], 1),
                       **{k: r[k] for k in ("episodes", "predictions", "true_positives", "missed", "false_alarms", "duplicates",
                                            "context_false_alarms", "unscorable", "optional_episodes", "optional_detected",
                                            "late_detections", "duplicates_same_group", "ended_resolved",
                                            "ended_unknown_outcome", "premature_resolutions")}}
                totals.setdefault((h, variant), []).append(row)
                if variant != "all":
                    continue
                per_clip.append(row)
                for kind, items in (("false_alarm", r["false_alarm_predictions"]), ("context_false_alarm", r["context_false_alarm_predictions"]),
                                    ("duplicate", r["duplicate_predictions"]), ("unscorable", r["unscorable_predictions"])):
                    for x in items:
                        c = causes.get(x["incident_id"], {})
                        fa_rows.append({"incident_id": x["incident_id"], "clip_id": cid, "split": lab["split"], "hazard": h,
                                        "category": kind, "t_s": round(x["t"], 2), "t_end_s": x["t_end"], "worker_id": x["worker_id"],
                                        "zone": x["zone"], "risk": x["risk"], "confidence": x["confidence"],
                                        "label_state_at_t": state_at(lab, h, x["t"]), "evidence": x["evidence"],
                                        **{k: c.get(k, "") for k in ("cause", "detail", "fix", "note")}})
                for ep in r["missed_episodes"]:
                    c = causes.get(ep["id"], {})
                    near = [round(x["t"], 1) for x in p if abs(x["t"] - ep["start_s"]) < 30]
                    miss_rows.append({"event_id": ep["id"], "clip_id": cid, "split": lab["split"], "hazard": h, "start_s": ep["start_s"],
                                      "end_s": ep["end_s"], "worker": ep["worker"], "observability": ep["observability"],
                                      "requirement": ep["requirement"], "alerts_within_30s": near,
                                      **{k: c.get(k, "") for k in ("cause", "detail", "fix", "note")}})
                found = {m["episode"] for m in r["matches"] + r["optional_matches"]}
                outcomes += [{"clip_id": cid, "hazard": h, "observability": ep["observability"], "optional": bool(ep.get("optional")),
                              "detected": i in found} for i, ep in enumerate(si["episodes"]) if ep["kind"] == "violation"]
                for kind, ms in (("required", r["matches"]), ("optional", r["optional_matches"])):
                    for m in ms:
                        ep = si["episodes"][m["episode"]]
                        lat_rows.append({"clip_id": cid, "split": lab["split"], "hazard": h, "event_id": ep["id"], "episode": kind,
                                         "onset_s": ep["start_s"], "first_alert_s": round(m["prediction"]["t"], 2),
                                         "latency_s": m["latency_s"], "late": m["latency_s"] > LATE_S,
                                         "true_duration_s": round(ep["end_s"] - ep["start_s"], 2),
                                         "duration_error_s": m.get("duration_error_s"), "end_outcome": m.get("end_outcome"),
                                         "end_reason": m["prediction"].get("end_reason"),
                                         "premature_resolution": m.get("premature_resolution"),
                                         "incident_id": m["prediction"]["incident_id"]})

    def agg(rows):
        return summarise(rows, "source_group", BOOT_N)

    metrics = {}
    for (h, variant), rows in totals.items():
        for split in ("all", "held-out", "development"):
            sel = [r for r in rows if split == "all" or r["split"] == split]
            if sel:
                metrics.setdefault(h, {}).setdefault(variant, {})[split] = agg(sel)
    # Per camera and per site (primary variant, all splits): one camera's or site's numbers never hide in a pool
    by_unit = {}
    for (h, variant), rows in totals.items():
        if variant != "all":
            continue
        for unit in ("camera_id", "site_id"):
            for u in sorted({r[unit] for r in rows}):
                sel = [r for r in rows if r[unit] == u]
                by_unit.setdefault(unit, {}).setdefault(h, {})[u] = {"split": sorted({r["split"] for r in sel}), **agg(sel)}
    unscorable_states = {}
    for r in fa_rows:
        if r["category"] == "unscorable":
            k = unscorable_states.setdefault(r["hazard"], {})
            k[r["label_state_at_t"]] = k.get(r["label_state_at_t"], 0) + 1
    lat = [r["latency_s"] for r in lat_rows if r["episode"] == "required"]
    scoring_code = {f: sha(ROOT / f) for f in ("intelligence/annotations.py", "intelligence/event_metrics.py",
                                               "scripts/validation/run_evaluation.py")}
    out = {"label_set": label_set, "labels_sha256": lock["combined_sha256"], "labels_status": lock["statuses"],
           "ground_truth": lock["ground_truth"], "run": run_dir.name, "model_sha256": man["model"]["sha256"],
           "scored_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scoring_code_sha256": scoring_code,
           "matcher": "identity-aware" if identity else "time only",
           "WARNING": None if lock["ground_truth"] else "PROVISIONAL: labels are an AI first pass without independent human "
                                                        "review. These numbers are not a validated measurement.",
           "metrics": metrics, "metrics_by_camera": by_unit.get("camera_id", {}), "metrics_by_site": by_unit.get("site_id", {}),
           "unscorable_by_label_state": unscorable_states,
           "latency_required_episodes_s": {"n": len(lat), "median": sorted(lat)[len(lat) // 2] if lat else None,
                                           "max": max(lat) if lat else None},
           "end_outcome_note": "ended_resolved counts matched incidents that ended on positive evidence; ended_unknown_outcome "
                               "those that ended because observation stopped (lost, camera interrupted or view changed, "
                               "session end), which are never resolutions. premature_resolutions: resolved while the "
                               "labelled violation continued. Per match in detection_latency.csv",
           "robustness": robustness(outcomes, per_clip), "tracking_proxy": tracking_proxy(labels, man), "scope_note":"Only built hazards with a configuration that makes them "
           "evaluable: PPE.HEAD.MISSING on all clips; ZONE.ENTRY only on the two clips with configured (demo) zones, where it "
           "measures geometric zone-entry detection, not real restricted-area violations."}
    (out_dir / "baseline_metrics.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    write_csv(out_dir / "per_clip_metrics.csv", per_clip)
    write_csv(out_dir / "false_alarm_analysis.csv", fa_rows)
    write_csv(out_dir / "missed_event_analysis.csv", miss_rows)
    write_csv(out_dir / "detection_latency.csv", lat_rows)
    hz_rows = []
    for h, vs in metrics.items():
        for variant, splits in vs.items():
            for split, m in splits.items():
                hz_rows.append({"hazard": h, "variant": variant, "split": split, **{k: (json.dumps(v) if isinstance(v, (list, tuple, dict)) else v)
                                                                                   for k, v in m.items()}})
    write_csv(out_dir / "per_hazard_metrics.csv", hz_rows)
    print(json.dumps({h: {s: {k: m[k] for k in ("episodes", "true_positives", "missed", "false_alarms", "duplicates",
                                                  "context_false_alarms", "unscorable", "optional_detected", "optional_episodes",
                                                  "monitorable_hours", "precision", "recall")} for s, m in vs["all"].items()}
                      for h, vs in metrics.items()}, indent=1))


def robustness(outcomes, per_clip):
    """Recall by labelled observability and false alarms by reviewed scene condition (clip_review.json). Slices with
    fewer than 10 positives, or under 0.1 monitorable hours, are marked insufficient instead of given a rate."""
    review = json.loads((VAL / "clip_review.json").read_text(encoding="utf-8")) if (VAL / "clip_review.json").exists() else {}
    recording = {r["clip_id"]: r["recording"] for r in csv.DictReader(open(VAL / "clip_manifest.csv", encoding="utf-8"))}

    def cond(cid, key):
        v = review.get(recording.get(cid, cid), {}).get(key, "")
        return v.split(" (")[0].split(",")[0].split(";")[0] or "unknown"

    rec = {}
    for o in outcomes:
        s = rec.setdefault(f"{o['hazard']} / {o['observability']}", {"episodes": 0, "detected": 0})
        s["episodes"] += 1
        s["detected"] += o["detected"]
    for s in rec.values():
        s["recall"] = round(s["detected"] / s["episodes"], 3) if s["episodes"] >= 10 else "insufficient (n < 10)"
    fa = {}
    for key in ("lighting", "distance", "camera_motion"):
        for r in per_clip:
            s = fa.setdefault(key, {}).setdefault(f"{r['hazard']} / {cond(r['clip_id'], key)}",
                                                  {"clips": 0, "false_alarms": 0, "monitorable_s": 0.0})
            s["clips"] += 1
            s["false_alarms"] += r["false_alarms"]
            s["monitorable_s"] += r["monitorable_s"]
    for slices in fa.values():
        for s in slices.values():
            h = s["monitorable_s"] / 3600
            s["false_alarms_per_hour"] = round(s["false_alarms"] / h, 1) if h >= 0.1 else "insufficient (< 0.1 h)"
            s["monitorable_s"] = round(s["monitorable_s"], 1)
    return {"note": "Every episode here comes from at most a few recordings, so slices are confounded with recording.",
            "recall_by_observability": rec, "false_alarms_by_condition": fa}


def tracking_proxy(labels, man):
    rows = []
    for cid, lab in labels.items():
        n = lab.get("people", {}).get("distinct_workers")
        pc = man["run"]["per_clip"].get(cid, {})
        if isinstance(n, int) and n > 0:
            rows.append({"clip_id": cid, "people_labelled": n, "track_ids": pc.get("track_ids"),
                         "confirmed_tracks": pc.get("confirmed_tracks"),
                         "ids_per_person": round(pc.get("track_ids", 0) / n, 2) if pc.get("track_ids") is not None else None})
    return {"note": "Proxy only: labelled distinct people vs track IDs issued. Identity ground truth does not exist, so ID "
                    "switches, HOTA and IDF1 cannot be measured.", "clips": rows}


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run", "score"])
    ap.add_argument("--labels", default="m2-provisional-v1")
    ap.add_argument("--run", help="score this run folder under eval_runs/ instead of the latest")
    ap.add_argument("--out", help="write the reports here (default reports/validation/)")
    ap.add_argument("--identity", action="store_true", help="identity-aware matching (intelligence/event_metrics.py)")
    ap.add_argument("--overwrite", action="store_true", help="allow replacing existing result files in --out")
    a = ap.parse_args()
    if a.stage == "run":
        return run(a.labels)
    score(a.labels, a.run, ROOT / a.out if a.out else VAL, a.identity, a.overwrite)


if __name__ == "__main__":
    main()
